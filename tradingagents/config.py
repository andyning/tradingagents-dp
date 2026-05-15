"""Unified configuration via Pydantic Settings.

Reads from .env file, environment variables, and defaults (in priority order).
"""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


_TRADINGAGENTS_HOME = Path.home() / ".tradingagents"


class Settings(BaseSettings):
    """TradingAgents configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- paths ----
    results_dir: Path = _TRADINGAGENTS_HOME / "results"
    data_cache_dir: Path = _TRADINGAGENTS_HOME / "cache"
    memory_log_path: Path = _TRADINGAGENTS_HOME / "memory" / "trading_memory.md"
    memory_log_max_entries: Optional[int] = None

    # ---- LLM ----
    llm_provider: str = "deepseek"
    llm_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str = ""
    deep_think_model: str = "deepseek-reasoner"
    quick_think_model: str = "deepseek-chat"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 8192

    # ---- pipeline ----
    analysis_depth: str = "medium"  # "light" | "medium" | "deep"
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    max_recur_limit: int = 100
    output_language: str = "Chinese"

    # ---- checkpoint ----
    checkpoint_enabled: bool = False

    # ---- data sources ----
    a_stock_primary: str = "baostock"
    a_stock_secondary: str = "efinance"
    hk_stock_primary: str = "efinance"
    hk_stock_secondary: str = "yfinance"
    us_stock_primary: str = "yfinance"
    us_stock_secondary: str = "efinance"

    # ---- backtesting ----
    backtest_initial_cash: float = 100_000.0
    backtest_commission: float = 0.00025
    backtest_slippage: float = 0.001
    backtest_benchmark: str = "000300.SH"

    # ---- web ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ---- debug ----
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "console"  # "console" | "json"


# Global singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the global Settings singleton, creating it on first access."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings singleton (useful for testing)."""
    global _settings
    _settings = None
