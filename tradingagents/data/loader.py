"""Backtesting data loader.

Loads historical data for backtesting, supporting:
- Single symbol or portfolio of symbols
- Date range specification
- Market selection (A-stock / HK / US)
- Incremental data updates (append-only by default)

Data is stored locally as Parquet files for fast reload.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from tradingagents.config import get_settings
from tradingagents.data import a_stock, hk_stock, us_stock
from tradingagents.logging import get_logger

logger = get_logger(__name__)

_MARKET_MODULES = {
    "a_stock": a_stock,
    "hk_stock": hk_stock,
    "us_stock": us_stock,
}


def load_history(
    symbol: str,
    start_date: str,
    end_date: str,
    market: str = "a_stock",
    frequency: str = "daily",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """Load historical K-line data for backtesting.

    Checks local Parquet cache first, then fetches from remote sources
    if needed. Data is stored in the cache directory for future reuse.
    """
    # Check local storage
    local = _load_local(symbol, frequency, market)
    req_start = pd.Timestamp(start_date)
    req_end = pd.Timestamp(end_date)

    if not local.empty:
        local["date"] = pd.to_datetime(local["date"])
        local_start = local["date"].min()
        local_end = local["date"].max()

        # If local covers the requested range, return the slice
        if local_start <= req_start and local_end >= req_end:
            mask = (local["date"] >= req_start) & (local["date"] <= req_end)
            return local[mask].reset_index(drop=True)

        # If partially covered, only fetch the missing range
        if local_end < req_end:
            missing_start = (local_end + timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info("Fetching %s from %s to %s", symbol, missing_start, end_date)
        else:
            missing_start = start_date
    else:
        missing_start = start_date

    # Fetch from remote
    mod = _MARKET_MODULES.get(market, a_stock)
    if frequency == "daily":
        df = mod.get_kline_daily(symbol, missing_start, end_date, adjust)
    elif frequency == "weekly":
        df = mod.get_kline_daily(symbol, missing_start, end_date, adjust)
        # Convert to weekly
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df = df.resample("W").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum", "amount": "sum",
            }).dropna().reset_index()
    elif frequency == "monthly":
        df = mod.get_kline_daily(symbol, missing_start, end_date, adjust)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df = df.resample("M").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum", "amount": "sum",
            }).dropna().reset_index()
    else:
        raise ValueError(f"Unknown frequency: {frequency}")

    if df.empty:
        return local  # return what we have locally, even if partial

    # Merge with local and save
    df["date"] = pd.to_datetime(df["date"])
    merged = pd.concat([local, df], ignore_index=True)
    merged = merged.drop_duplicates(subset=["date"]).sort_values("date")
    _save_local(symbol, merged, frequency, market)

    mask = (merged["date"] >= req_start) & (merged["date"] <= req_end)
    return merged[mask].reset_index(drop=True)


def load_portfolio(
    symbols: list[str],
    start_date: str,
    end_date: str,
    market: str = "a_stock",
    frequency: str = "daily",
) -> dict[str, pd.DataFrame]:
    """Load history for multiple symbols. Returns {symbol: DataFrame}."""
    result = {}
    for sym in symbols:
        try:
            df = load_history(sym, start_date, end_date, market, frequency)
            result[sym] = df
        except Exception as exc:
            logger.warning("Failed to load %s: %s", sym, exc)
            result[sym] = pd.DataFrame()
    return result


# ---- internal helpers ----

def _storage_path(symbol: str, frequency: str, market: str) -> Path:
    settings = get_settings()
    base = settings.data_cache_dir / "history" / market / frequency
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{symbol}.parquet"


def _load_local(symbol: str, frequency: str, market: str) -> pd.DataFrame:
    path = _storage_path(symbol, frequency, market)
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            pass
    return pd.DataFrame()


def _save_local(symbol: str, df: pd.DataFrame, frequency: str, market: str) -> None:
    path = _storage_path(symbol, frequency, market)
    try:
        df.to_parquet(path, index=False)
    except Exception as exc:
        logger.warning("Failed to save local data for %s: %s", symbol, exc)
