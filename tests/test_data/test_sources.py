"""Data source integration tests — actual data fetching.

Tests each data source with real endpoints.
Marked as 'integration' — requires network access.
"""

import pandas as pd
import pytest

from tradingagents.data.sources.baostock import BaostockSource
from tradingagents.data.sources.efinance import EfinanceSource
from tradingagents.data.sources.akshare import AkshareSource
from tradingagents.data.sources.yfinance import YFinanceSource


@pytest.mark.integration
class TestBaostockSource:
    """A-stock K-line and financial data — primary source."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.src = BaostockSource()

    def test_kline_daily(self):
        """Fetch daily K-line for 贵州茅台 (600519)."""
        df = self.src.kline_daily("600519", "2025-01-01", "2025-05-01")
        assert not df.empty, "Should return K-line data"
        assert "date" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert len(df) > 10, f"Expected >10 trading days, got {len(df)}"
        # Verify data quality
        assert df["close"].notna().all(), "close should not have NaN"
        assert (df["high"] >= df["low"]).all(), "all highs should be >= lows"

    def test_kline_daily_adjust(self):
        """Test forward-adjustment."""
        df = self.src.kline_daily("000001", "2024-06-01", "2024-07-01", adjust="qfq")
        assert not df.empty

    def test_multiple_symbols(self):
        """Test different A-stock tickers (Shanghai & Shenzhen)."""
        for sym in ["600519", "000001", "300750"]:
            df = self.src.kline_daily(sym, "2025-04-01", "2025-05-01")
            assert not df.empty, f"No data for {sym}"

    def test_kline_weekly(self):
        """Fetch weekly K-line."""
        df = self.src.kline_weekly("600519", "2024-01-01", "2024-12-31")
        assert not df.empty

    def test_kline_monthly(self):
        """Fetch monthly K-line."""
        df = self.src.kline_monthly("600519", "2024-01-01", "2024-12-31")
        assert not df.empty


@pytest.mark.integration
class TestEfinanceSource:
    """Multi-market efinance source."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.src = EfinanceSource()

    def test_kline_daily(self):
        """Fetch A-stock K-line."""
        df = self.src.kline_daily("600519", "2025-01-01", "2025-05-01")
        assert not df.empty, "Should return K-line data"

    def test_quote(self):
        """Fetch real-time quote."""
        df = self.src.quote("600519")
        assert not df.empty, "Should return quote data"
        assert "symbol" in df.columns

    def test_financial_summary(self):
        """Fetch financial summary (PE/PB etc.)."""
        df = self.src.financial_summary("600519")
        assert not df.empty


@pytest.mark.integration
class TestAkshareSource:
    """Special A-stock data (dragon tiger, lockup, etc.)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.src = AkshareSource()

    def test_dragon_tiger_board(self):
        """Fetch dragon tiger board data."""
        df = self.src.dragon_tiger_board("600519", days=90)
        # Dragon tiger may be empty if the stock didn't appear
        # Just test it doesn't throw
        assert isinstance(df, pd.DataFrame)

    def test_lockup_expiry(self):
        """Fetch lockup expiry data."""
        df = self.src.lockup_expiry("600519", months=6)
        assert isinstance(df, pd.DataFrame)

    def test_fund_flow(self):
        """Fetch capital flow data."""
        df = self.src.fund_flow("600519", days=10)
        assert isinstance(df, pd.DataFrame)

    def test_hot_stocks(self):
        """Fetch hot stocks list."""
        df = self.src.hot_stocks(limit=10)
        assert isinstance(df, pd.DataFrame)

    def test_northbound_flow(self):
        """Fetch northbound capital flow."""
        df = self.src.northbound_flow(days=10)
        assert isinstance(df, pd.DataFrame)


@pytest.mark.integration
class TestYFinanceSource:
    """Yahoo Finance source — US/HK and fallback."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.src_us = YFinanceSource(market="us_stock")
        self.src_hk = YFinanceSource(market="hk_stock")
        self.src_a = YFinanceSource(market="a_stock")

    def test_us_kline(self):
        """Fetch US stock K-line (may be blocked in mainland China)."""
        df = self.src_us.kline_daily("AAPL", "2025-01-01", "2025-05-01")
        if df.empty:
            pytest.skip("yfinance blocked in mainland China")

    def test_hk_kline(self):
        """Fetch HK stock K-line (may be blocked in mainland China)."""
        df = self.src_hk.kline_daily("0700", "2025-01-01", "2025-05-01")
        if df.empty:
            pytest.skip("yfinance blocked in mainland China")

    def test_us_quote(self):
        """Fetch US stock quote (may be blocked in mainland China)."""
        df = self.src_us.quote("AAPL")
        if df.empty:
            pytest.skip("yfinance blocked in mainland China")

    def test_us_financials(self):
        """Fetch US stock financial statements."""
        df_bs = self.src_us.balance_sheet("AAPL")
        assert isinstance(df_bs, pd.DataFrame)

        df_income = self.src_us.income_statement("AAPL")
        assert isinstance(df_income, pd.DataFrame)
