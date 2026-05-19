"""Data source integration tests — HTTP-based data fetching.

Tests each HTTP data source with real endpoints.
Marked as 'integration' — requires network access.
"""

import pandas as pd
import pytest

from tradingagents.data.http.tencent import TencentSource, fetch_quote, fetch_kline, normalize_cn_code, normalize_hk_code
from tradingagents.data.http.eastmoney import EastmoneySource, fetch_snapshot, fetch_kline as em_fetch_kline
from tradingagents.data.http.eastmoney import _a_secid, _hk_secid
from tradingagents.data.http.yahoo import YahooSource, fetch_kline as yf_fetch_kline


@pytest.mark.integration
class TestTencentSource:
    """A-stock and HK stock via Tencent Finance HTTP."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.src = TencentSource(market="a_stock")
        self.src_hk = TencentSource(market="hk_stock")

    def test_kline_daily(self):
        df = self.src.kline_daily("600519", "2025-01-01", "2025-05-01")
        assert not df.empty, "Should return K-line data"
        assert "date" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert len(df) > 10, f"Expected >10 trading days, got {len(df)}"

    def test_kline_daily_adjust(self):
        df = self.src.kline_daily("000001", "2024-06-01", "2024-07-01", adjust="qfq")
        assert not df.empty

    def test_multiple_symbols(self):
        for sym in ["600519", "000001", "300750"]:
            df = self.src.kline_daily(sym, "2025-04-01", "2025-05-01")
            assert not df.empty, f"No data for {sym}"

    def test_kline_weekly(self):
        df = self.src.kline_weekly("600519", "2024-01-01", "2024-12-31")
        assert not df.empty

    def test_kline_monthly(self):
        df = self.src.kline_monthly("600519", "2024-01-01", "2024-12-31")
        assert not df.empty

    def test_quote(self):
        df = self.src.quote("600519")
        assert not df.empty, "Should return quote data"
        assert "price" in df.columns

    def test_hk_kline(self):
        df = self.src_hk.kline_daily("00700", "2025-01-01", "2025-05-01")
        assert not df.empty, f"Should return HK K-line data"

    def test_hk_quote(self):
        df = self.src_hk.quote("00700")
        assert not df.empty, f"Should return HK quote"


@pytest.mark.integration
class TestEastmoneySource:
    """Eastmoney HTTP source — A/HK/US stocks."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.src = EastmoneySource(market="a_stock")
        self.src_hk = EastmoneySource(market="hk_stock")

    def test_kline_daily(self):
        df = self.src.kline_daily("600519", "2025-01-01", "2025-05-01")
        assert not df.empty, "Should return K-line data"

    def test_quote(self):
        df = self.src.quote("600519")
        assert not df.empty, "Should return quote data"

    def test_financial_summary(self):
        df = self.src.financial_summary("600519")
        assert not df.empty

    def test_fund_flow(self):
        df = self.src.fund_flow("600519", days=10)
        assert isinstance(df, pd.DataFrame)

    def test_hot_stocks(self):
        df = self.src.hot_stocks(limit=10)
        assert isinstance(df, pd.DataFrame)

    def test_northbound_flow(self):
        df = self.src.northbound_flow(days=10)
        assert isinstance(df, pd.DataFrame)

    def test_dragon_tiger_board(self):
        df = self.src.dragon_tiger_board("600519", days=90)
        assert isinstance(df, pd.DataFrame)

    def test_lockup_expiry(self):
        df = self.src.lockup_expiry("600519", months=6)
        assert isinstance(df, pd.DataFrame)

    def test_profit_forecast(self):
        df = self.src.profit_forecast("600519")
        assert isinstance(df, pd.DataFrame)

    def test_insider_transactions(self):
        df = self.src.insider_transactions("600519")
        assert isinstance(df, pd.DataFrame)

    def test_hk_kline(self):
        df = self.src_hk.hk_kline_daily("00700", "2025-01-01", "2025-05-01")
        assert not df.empty

    def test_news(self):
        df = self.src.news("600519", limit=10)
        assert isinstance(df, pd.DataFrame)


@pytest.mark.integration
class TestYahooSource:
    """Yahoo Finance HTTP source — US/HK/A-stock."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.src_us = YahooSource(market="us_stock")
        self.src_hk = YahooSource(market="hk_stock")
        self.src_a = YahooSource(market="a_stock")

    def test_us_kline(self):
        df = self.src_us.kline_daily("AAPL", "2025-01-01", "2025-05-01")
        if df.empty:
            pytest.skip("Yahoo Finance blocked in mainland China")

    def test_hk_kline(self):
        df = self.src_hk.kline_daily("0700", "2025-01-01", "2025-05-01")
        if df.empty:
            pytest.skip("Yahoo Finance blocked in mainland China")

    def test_us_quote(self):
        df = self.src_us.quote("AAPL")
        if df.empty:
            pytest.skip("Yahoo Finance blocked in mainland China")

    def test_us_news(self):
        df = self.src_us.news("AAPL", limit=10)
        assert isinstance(df, pd.DataFrame)
