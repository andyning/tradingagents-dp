"""Unified exception hierarchy for TradingAgents."""


class TradingAgentsError(Exception):
    """Base exception for all TradingAgents errors."""


# ---- data errors ----

class DataError(TradingAgentsError):
    """Base exception for data layer errors."""


class DataSourceError(DataError):
    """A specific data source failed (retryable)."""

    def __init__(self, source: str, detail: str = ""):
        self.source = source
        self.detail = detail
        super().__init__(f"[{source}] {detail}" if detail else f"[{source}] request failed")


class AllSourcesExhausted(DataError):
    """All fallback sources have been exhausted."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        super().__init__(f"All data sources exhausted for '{endpoint}'")


class SchemaValidationError(DataError):
    """Data failed Pydantic schema validation."""

    def __init__(self, endpoint: str, detail: str = ""):
        self.endpoint = endpoint
        self.detail = detail
        super().__init__(f"Schema validation failed for '{endpoint}': {detail}")


class EmptyDataError(DataError):
    """Data source returned empty data."""

    def __init__(self, source: str, symbol: str):
        self.source = source
        self.symbol = symbol
        super().__init__(f"[{source}] returned empty data for '{symbol}'")


# ---- LLM errors ----

class LLMError(TradingAgentsError):
    """Base exception for LLM errors."""


class LLMConnectionError(LLMError):
    """Failed to connect to LLM provider."""


class LLMRateLimitError(LLMError):
    """LLM provider rate limit exceeded."""


class LLMResponseError(LLMError):
    """LLM returned an invalid or empty response."""


class StructuredOutputError(LLMResponseError):
    """Failed to parse structured output from LLM response."""


# ---- graph errors ----

class GraphError(TradingAgentsError):
    """Base exception for LangGraph pipeline errors."""


class NodeExecutionError(GraphError):
    """A graph node failed during execution."""


class DebateTimeoutError(GraphError):
    """Debate exceeded maximum rounds without convergence."""


# ---- backtesting errors ----

class BacktestError(TradingAgentsError):
    """Base exception for backtesting errors."""


class InsufficientDataError(BacktestError):
    """Not enough historical data for backtesting."""
