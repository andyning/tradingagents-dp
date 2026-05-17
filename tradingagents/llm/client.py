"""DeepSeek LLM client — the sole LLM backend.

DeepSeek API is OpenAI-compatible, so we use the `openai` SDK.
Supports two reasoning modes:
  - quick:  standard chat completion (deepseek-chat)
  - deep:   reasoning with extended thinking (deepseek-reasoner)
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from tradingagents.config import get_settings
from tradingagents.exceptions import (
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponseError,
    StructuredOutputError,
)
from tradingagents.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = (1, 2, 4)  # seconds

# Global token accumulator (shared across all client instances)
_total_tokens_in = 0
_total_tokens_out = 0


def token_stats() -> dict[str, int]:
    return {"tokens_in": _total_tokens_in, "tokens_out": _total_tokens_out, "total": _total_tokens_in + _total_tokens_out}


def reset_token_stats() -> None:
    global _total_tokens_in, _total_tokens_out
    _total_tokens_in = 0
    _total_tokens_out = 0


class DeepSeekClient:
    """DeepSeek LLM client backed by the OpenAI SDK."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        mode: str = "quick",
    ):
        settings = get_settings()
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.llm_base_url
        self.model = model or (
            settings.quick_think_model if mode == "quick" else settings.deep_think_model
        )
        self.temperature = temperature if mode == "quick" else 0.0
        self.max_tokens = max_tokens
        self.mode = mode
        self._client: OpenAI | None = None
        self.last_tokens_in: int = 0
        self.last_tokens_out: int = 0

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                max_retries=0,  # we handle retries ourselves
            )
        return self._client

    # ---- public API ----

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        json_mode: bool = False,
    ) -> ChatCompletionMessage:
        """Send a chat completion request with retry logic.

        Returns the assistant message from the API response.
        """
        kwargs = self._build_kwargs(tools, tool_choice, json_mode)
        return self._request_with_retry(messages, kwargs)

    def structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        schema_name: str = "response",
    ) -> dict[str, Any]:
        """Request structured JSON output conforming to a JSON Schema.

        Uses OpenAI's `response_format` with `json_schema` mode when the
        target model supports it; otherwise falls back to prompting + parsing.
        """
        # DeepSeek models support JSON mode but not strict schema in response_format.
        # We inject the schema into the system prompt and use JSON mode.
        system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        schema_instruction = (
            f"\n\nOutput must be valid JSON conforming to this schema:\n"
            f"```json\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n```\n"
            f"Respond with ONLY the JSON object, no other text."
        )
        if messages and messages[0]["role"] == "system":
            messages = messages.copy()
            messages[0] = {**messages[0], "content": system + schema_instruction}
        else:
            messages = [{"role": "system", "content": schema_instruction}] + messages

        msg = self.chat(messages, json_mode=True)

        try:
            return json.loads(msg.content or "")
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code fences
            content = msg.content or ""
            if "```json" in content:
                block = content.split("```json", 1)[1].split("```", 1)[0]
                try:
                    return json.loads(block)
                except json.JSONDecodeError:
                    pass
            raise StructuredOutputError(
                f"Failed to parse structured output for schema '{schema_name}'"
            )

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, Any]] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> ChatCompletionMessage:
        """Stream a chat completion, optionally calling `on_token` per chunk.

        Falls back to non-streaming internally if the model doesn't support it.
        Accumulates tool call deltas and returns the final assembled message.
        """
        kwargs = self._build_kwargs(tools, stream=True)
        return self._stream_with_retry(messages, kwargs, on_token)

    def invoke_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_map: dict[str, Callable[..., str]],
        *,
        max_rounds: int = 5,
    ) -> dict[str, Any]:
        """Agentic tool-use loop: call the LLM, execute any tool calls, repeat.

        Returns the final text response and collected tool results.
        """
        msgs = list(messages)
        tool_results: dict[str, Any] = {}

        for _ in range(max_rounds):
            response = self.chat(msgs, tools=tools)

            if response.content:
                # Model provided a text response alongside or instead of tool calls
                pass

            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls:
                return {"content": response.content, "tool_results": tool_results}

            # Append assistant message
            msgs.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                if name in tool_map:
                    try:
                        result = tool_map[name](**args)
                    except Exception as e:
                        result = f"Tool error: {e}"
                else:
                    result = f"Unknown tool: {name}"
                tool_results[name] = result
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                })

        return {"content": response.content, "tool_results": tool_results}

    # ---- internal ----

    def _build_kwargs(
        self,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        json_mode: bool = False,
        stream: bool = False,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs

    def _request_with_retry(
        self, messages: list[dict[str, str]], kwargs: dict[str, Any]
    ) -> ChatCompletionMessage:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(messages=messages, **kwargs)
                choice = resp.choices[0]
                msg = choice.message
                # Track tokens globally
                if resp.usage:
                    global _total_tokens_in, _total_tokens_out
                    _total_tokens_in += resp.usage.prompt_tokens or 0
                    _total_tokens_out += resp.usage.completion_tokens or 0
                    self.last_tokens_in = resp.usage.prompt_tokens or 0
                    self.last_tokens_out = resp.usage.completion_tokens or 0
                logger.debug(
                    "LLM call succeeded",
                    model=self.model,
                    mode=self.mode,
                    tokens_used=resp.usage.total_tokens if resp.usage else None,
                    finish_reason=choice.finish_reason,
                )
                return msg
            except Exception as exc:
                last_error = exc
                if self._is_rate_limit(exc):
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BACKOFF[attempt]
                        logger.warning("Rate limited, retrying in %ds", delay)
                        time.sleep(delay)
                        continue
                    raise LLMRateLimitError(str(exc)) from exc
                if self._is_connection_error(exc):
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BACKOFF[attempt]
                        logger.warning("Connection error, retrying in %ds", delay)
                        time.sleep(delay)
                        continue
                    raise LLMConnectionError(str(exc)) from exc
                if self._is_auth_error(exc):
                    raise LLMResponseError(str(exc)) from exc
                if attempt < MAX_RETRIES:
                    delay = RETRY_BACKOFF[attempt]
                    logger.warning("LLM error (attempt %d), retrying in %ds: %s", attempt + 1, delay, exc)
                    time.sleep(delay)
                    continue
                raise LLMResponseError(str(exc)) from exc
        raise LLMResponseError(str(last_error)) if last_error else LLMResponseError("max retries exceeded")

    def _stream_with_retry(
        self,
        messages: list[dict[str, str]],
        kwargs: dict[str, Any],
        on_token: Callable[[str], None] | None,
    ) -> ChatCompletionMessage:
        # For simplicity, use non-streaming + on_token callback
        # DeepSeek doesn't fully support streaming with tool calls
        msg = self._request_with_retry(messages, {**kwargs, "stream": False})
        if on_token and msg.content:
            on_token(msg.content)
        return msg

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "rate" in msg and ("limit" in msg or "429" in msg)

    @staticmethod
    def _is_connection_error(exc: Exception) -> bool:
        from httpx import ConnectError, ReadError, RemoteProtocolError
        if isinstance(exc, (ConnectError, ReadError, RemoteProtocolError)):
            return True
        msg = str(exc).lower()
        return any(kw in msg for kw in ("connection", "timeout", "refused", "reset"))

    @staticmethod
    def _is_auth_error(exc: Exception) -> bool:
        """401 or authentication failures — never retry these."""
        msg = str(exc).lower()
        return any(kw in msg for kw in ("401", "authentication", "invalid api key", "invalid_request_error"))


# ---- module-level convenience ----

_client_cache: dict[str, DeepSeekClient] = {}


def get_llm_client(mode: str = "quick") -> DeepSeekClient:
    """Return a cached DeepSeekClient for the given mode."""
    if mode not in _client_cache:
        settings = get_settings()
        model = settings.quick_think_model if mode == "quick" else settings.deep_think_model
        _client_cache[mode] = DeepSeekClient(model=model, mode=mode)
    return _client_cache[mode]


def clear_client_cache() -> None:
    """Clear cached LLM clients (useful for testing)."""
    _client_cache.clear()
