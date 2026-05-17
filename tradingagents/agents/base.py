"""Base agent class — framework-independent agent abstraction.

Agents receive state, render a Jinja2 prompt, call the LLM, and
return a dict update to the LangGraph state.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader

from tradingagents.config import get_settings
from tradingagents.llm.client import DeepSeekClient, get_llm_client
from tradingagents.logging import get_logger

logger = get_logger(__name__)


def _get_prompts_dir() -> Path:
    """Resolve the prompts directory (handles PyInstaller _MEIPASS)."""
    meipass = getattr(_sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "tradingagents" / "agents" / "prompts"
        if candidate.is_dir():
            return candidate
    return Path(__file__).parent / "prompts"


# Jinja2 environment for prompt templates
_PROMPTS_DIR = _get_prompts_dir()
_jinja_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=False,
)


def render_prompt(template_name: str, **kwargs) -> str:
    """Render a Jinja2 prompt template with the given variables."""
    template = _jinja_env.get_template(template_name)
    return template.render(**kwargs).strip()


def _language_instruction() -> str:
    lang = get_settings().output_language
    if lang.lower() == "chinese":
        return "Write your entire report in Chinese (Simplified). Use professional financial terminology."
    return ""


def _market_label(market: str) -> str:
    return {"a_stock": "A-stock", "hk_stock": "Hong Kong", "us_stock": "US"}.get(market, market)


class Agent:
    """Base agent that renders a prompt, calls the LLM, and returns a state update.

    Subclasses override ``_process`` to transform the LLM response into
    the appropriate state dict update.
    """

    template: str = ""
    mode: str = "quick"  # LLM mode: "quick" or "deep"

    def __init__(self):
        self._llm: DeepSeekClient | None = None

    @property
    def llm(self) -> DeepSeekClient:
        if self._llm is None:
            self._llm = get_llm_client(self.mode)
        return self._llm

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the agent: render prompt → call LLM → return state update."""
        variables = self._prepare(state)
        prompt = render_prompt(self.template, **variables)
        response = self.llm.chat([{"role": "user", "content": prompt}])
        return self._process(response.content or "", state)

    def _prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        """Build template variables from the graph state.

        Override to add agent-specific variables.
        """
        return {
            "symbol": state.get("company_of_interest", ""),
            "trade_date": state.get("trade_date", ""),
            "market": _market_label(state.get("market", "a_stock")),
            "language_instruction": _language_instruction(),
        }

    def _process(self, content: str, state: dict[str, Any]) -> dict[str, Any]:
        """Transform LLM output into a state update. Override in subclasses."""
        raise NotImplementedError


def tool_to_openai_schema(fn: Callable) -> dict[str, Any]:
    """Convert a Python function to an OpenAI-compatible tool schema.

    Infers parameter types from the function signature. For production use,
    prefer explicit schema definitions.
    """
    import inspect

    sig = inspect.signature(fn)
    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        py_type = param.annotation if param.annotation is not inspect.Parameter.empty else str
        json_type = "string"
        if py_type is int:
            json_type = "integer"
        elif py_type is float:
            json_type = "number"
        elif py_type is bool:
            json_type = "boolean"

        properties[name] = {"type": json_type, "description": f"Parameter: {name}"}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (fn.__doc__ or f"Call {fn.__name__}").strip().split("\n")[0],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
