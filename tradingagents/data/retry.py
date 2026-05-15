"""Exponential backoff retry + multi-source fallback chain.

Every data fetch is executed through `with_fallback`, which tries each
source in order, applying retries per source and Pydantic validation on
the result.  If all sources fail, `AllSourcesExhausted` is raised.
"""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

import pandas as pd
from pydantic import BaseModel, ValidationError

from tradingagents.data.cache import get_cached, set_cache_miss, set_cached
from tradingagents.exceptions import AllSourcesExhausted, DataSourceError, SchemaValidationError
from tradingagents.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
RETRY_BACKOFF = (1, 2, 4)  # seconds
MAX_RETRIES = 3


def with_fallback(
    symbol: str,
    endpoint: str,
    sources: list[tuple[str, Callable[..., pd.DataFrame]]],
    schema: type[BaseModel] | None = None,
    params: dict[str, Any] | None = None,
    cache: bool = True,
    cache_ttl_hours: int = 4,
) -> pd.DataFrame:
    """Try each source in order until one returns valid data.

    Args:
        symbol: Stock symbol (for cache key and error messages)
        endpoint: Logical endpoint name (e.g. "kline_daily")
        sources: Ordered list of (source_name, callable) pairs.
                 Each callable must accept ``**params`` and return a DataFrame.
        schema: Optional Pydantic model for row-level validation.
        params: Kwargs forwarded to each source callable.
        cache: Whether to use / update the local Parquet cache.
        cache_ttl_hours: Max age for cached data.
    """
    params = params or {}

    # Check cache first
    if cache:
        cached = get_cached(symbol, endpoint, params, max_age_hours=cache_ttl_hours)
        if cached is not None:
            return cached

    last_error: Exception | None = None

    for source_name, fetch_fn in sources:
        for attempt in range(MAX_RETRIES + 1):
            try:
                df = fetch_fn(**params)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[%s] %s attempt %d failed: %s",
                    source_name, endpoint, attempt + 1, exc,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF[attempt])
                    continue
                break  # all retries exhausted for this source

            # Validate
            if df is None or (hasattr(df, "empty") and df.empty):
                last_error = DataSourceError(source_name, "returned empty DataFrame")
                logger.warning("[%s] %s returned empty data", source_name, endpoint)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF[attempt])
                    continue
                break

            if schema is not None:
                try:
                    df = _validate_df(df, schema, source_name, endpoint)
                except SchemaValidationError as exc:
                    last_error = exc
                    logger.warning(str(exc))
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_BACKOFF[attempt])
                        continue
                    break

            # Success
            logger.info("[%s] %s returned %d rows", source_name, endpoint, len(df))
            if cache:
                set_cached(symbol, endpoint, params, df)
            return df

        # Source exhausted — try next
        logger.warning("[%s] %s exhausted, trying next source", source_name, endpoint)

    # Cache the miss so we don't retry every analyst
    if cache:
        set_cache_miss(symbol, endpoint, params)
    raise AllSourcesExhausted(
        f"{endpoint} for {symbol}"
    ) from last_error


def _validate_df(
    df: pd.DataFrame,
    schema: type[BaseModel],
    source: str,
    endpoint: str,
) -> pd.DataFrame:
    """Validate each row against a Pydantic schema.

    Rows that fail validation are dropped. If ALL rows fail, raises
    SchemaValidationError so the fallback chain can try the next source.
    """
    valid_rows = []
    errors = 0
    for idx, row in df.iterrows():
        try:
            schema.model_validate(row.to_dict())
            valid_rows.append(row)
        except ValidationError:
            errors += 1

    if not valid_rows:
        raise SchemaValidationError(endpoint, f"all {len(df)} rows failed validation")

    if errors:
        logger.debug(
            "[%s] %s: %d/%d rows failed schema validation",
            source, endpoint, errors, len(df),
        )

    return pd.DataFrame(valid_rows).reset_index(drop=True)
