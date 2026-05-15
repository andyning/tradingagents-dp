"""Test retry/fallback chain logic."""

import pandas as pd
import pytest

from tradingagents.data.retry import with_fallback
from tradingagents.exceptions import AllSourcesExhausted
from tradingagents.data.schema import KLineRow


def test_first_source_succeeds():
    def good_source(**kwargs):
        return pd.DataFrame([{
            "date": "2025-01-15", "open": 10.0, "high": 11.0,
            "low": 9.5, "close": 10.5, "volume": 1000000, "amount": 1e7,
        }])

    result = with_fallback(
        "test", "kline",
        sources=[("primary", good_source)],
        cache=False,
    )
    assert len(result) == 1


def test_fallback_to_second():
    def failing_source(**kwargs):
        raise RuntimeError("boom")

    def backup_source(**kwargs):
        return pd.DataFrame([{
            "date": "2025-01-15", "open": 10.0, "high": 11.0,
            "low": 9.5, "close": 10.5, "volume": 1000000, "amount": 1e7,
        }])

    result = with_fallback(
        "test", "kline",
        sources=[("primary", failing_source), ("backup", backup_source)],
        cache=False,
    )
    assert len(result) == 1


def test_all_fail():
    def always_fail(**kwargs):
        raise RuntimeError("nope")

    with pytest.raises(AllSourcesExhausted):
        with_fallback(
            "test", "kline",
            sources=[("a", always_fail), ("b", always_fail)],
            cache=False,
        )


def test_empty_dataframe_triggers_fallback():
    def empty_source(**kwargs):
        return pd.DataFrame()

    def good_source(**kwargs):
        return pd.DataFrame([{
            "date": "2025-01-15", "open": 10.0, "high": 11.0,
            "low": 9.5, "close": 10.5, "volume": 1000000, "amount": 1e7,
        }])

    result = with_fallback(
        "test", "kline",
        sources=[("empty", empty_source), ("good", good_source)],
        cache=False,
    )
    assert len(result) == 1
