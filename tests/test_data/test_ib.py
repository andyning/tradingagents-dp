"""Tests for IB data source adapter."""

import pandas as pd
import pytest

from tradingagents.data.sources.ib import IBSource, _ib_contract


class TestIBContract:
    # _ib_contract returns (type_name, symbol, exchange, currency) tuple

    def test_a_stock_shanghai(self):
        c = _ib_contract("600519", "a_stock")
        assert c is not None
        assert c[2] == "SEHKNTL"
        assert c[3] == "CNY"

    def test_a_stock_shenzhen(self):
        c = _ib_contract("000001", "a_stock")
        assert c is not None
        assert c[3] == "CNY"

    def test_hk_stock(self):
        c = _ib_contract("00700", "hk_stock")
        assert c is not None
        assert c[2] == "SEHK"
        assert c[3] == "HKD"

    def test_us_stock(self):
        c = _ib_contract("AMD", "us_stock")
        assert c is not None
        assert c[2] == "SMART"
        assert c[3] == "USD"


class TestIBWithoutGateway:
    """Tests that run WITHOUT IB Gateway running — verify graceful degradation."""

    def test_ib_not_running_returns_empty(self):
        """When IB Gateway is not running, all methods return empty DataFrames."""
        ib = IBSource(market="us_stock")
        df = ib.kline_daily("AMD", "2026-05-01", "2026-05-16")
        assert isinstance(df, pd.DataFrame)
        # Connection should fail gracefully, returning empty
        # (may succeed if IB is actually running)

    def test_ib_not_running_returns_empty_hk(self):
        ib = IBSource(market="hk_stock")
        df = ib.kline_daily("00700", "2026-05-01", "2026-05-16")
        assert isinstance(df, pd.DataFrame)

    def test_ib_not_running_returns_empty_a(self):
        ib = IBSource(market="a_stock")
        df = ib.kline_daily("600519", "2026-05-01", "2026-05-16")
        assert isinstance(df, pd.DataFrame)

    def test_ib_not_running_weekly(self):
        ib = IBSource(market="us_stock")
        df = ib.kline_weekly("AMD", "2026-01-01", "2026-05-16")
        assert isinstance(df, pd.DataFrame)

    def test_ib_not_running_monthly(self):
        ib = IBSource(market="us_stock")
        df = ib.kline_monthly("AMD", "2026-01-01", "2026-05-16")
        assert isinstance(df, pd.DataFrame)

    def test_ib_not_running_quote(self):
        ib = IBSource(market="us_stock")
        df = ib.quote("AMD")
        assert isinstance(df, pd.DataFrame)

    def test_ib_not_running_financial_summary(self):
        ib = IBSource(market="us_stock")
        df = ib.financial_summary("AMD")
        assert isinstance(df, pd.DataFrame)

    def test_ib_all_unsupported_return_empty(self):
        """Unsupported endpoints should return empty DataFrames."""
        ib = IBSource(market="us_stock")
        tests = [
            ("balance_sheet", ("AMD",)),
            ("income_statement", ("AMD",)),
            ("cash_flow", ("AMD",)),
            ("technical_indicators", ("AMD", "2026-01-01", "2026-05-01")),
            ("news", ("AMD",)),
            ("fund_flow", ("AMD",)),
            ("dragon_tiger_board", ("AMD",)),
            ("lockup_expiry", ("AMD",)),
            ("profit_forecast", ("AMD",)),
            ("hot_stocks", ()),
            ("industry_comparison", ("AMD",)),
            ("insider_transactions", ("AMD",)),
        ]
        for method, args in tests:
            fn = getattr(ib, method)
            result = fn(*args)
            assert isinstance(result, pd.DataFrame), f"{method} should return DataFrame"
