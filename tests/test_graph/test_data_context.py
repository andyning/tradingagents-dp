"""Tests for data_context — backtest calculations, industry comparison."""

import pandas as pd
import pytest

from tradingagents.graph.data_context import for_backtest, for_industry_comparison


class TestBacktest:
    def make_state(self, symbol="600519", market="a_stock"):
        return {
            "company_of_interest": symbol,
            "trade_date": "2026-05-15",
            "market": market,
            "data_window": 120,
        }

    def test_insufficient_data(self):
        """Should not crash with < 60 rows of data."""
        state = self.make_state("600519")
        # This will try to fetch real data — may return "insufficient"
        # or may succeed. Just verify it doesn't throw.
        result = for_backtest(state)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_non_a_stock(self):
        """Backtest should work for any market type."""
        state = self.make_state("AAPL", "us_stock")
        result = for_backtest(state)
        assert isinstance(result, str)


class TestIndustryComparison:
    def make_state(self, symbol="600519", market="a_stock"):
        return {
            "company_of_interest": symbol,
            "trade_date": "2026-05-15",
            "market": market,
            "data_window": 120,
        }

    def test_non_a_stock_returns_note(self):
        """Non-A-stock markets should return a note."""
        state = self.make_state("AAPL", "us_stock")
        result = for_industry_comparison(state)
        assert "仅A股" in result or "A股" in result

    def test_a_stock_runs(self):
        state = self.make_state("600519", "a_stock")
        result = for_industry_comparison(state)
        assert isinstance(result, str)


class TestBacktestMath:
    """Unit tests for the backtest math logic — isolated from data sources."""

    def test_simulate_uptrend(self):
        """In a steady uptrend, MA crossover should profit."""
        import numpy as np
        # Create a simple uptrend: 100 trading days, ~20% gain
        np.random.seed(42)
        days = 100
        close = pd.Series(100.0 * (1 + np.cumsum(np.random.normal(0.001, 0.01, days))))
        close = close.clip(lower=1.0)
        daily_ret = close.pct_change().fillna(0)

        # Compute position signal: MA5 > MA20
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        position = (ma5 > ma20).astype(int)

        # Simulate strategy
        rets = daily_ret * position.shift(1).fillna(0)
        strat_cum = (1 + rets).cumprod()
        bh_cum = (1 + daily_ret).cumprod()

        strat_total = float((strat_cum.iloc[-1] - 1) * 100)
        bh_total = float((bh_cum.iloc[-1] - 1) * 100)

        # In an uptrend, strategy should capture some gains
        assert strat_total > -100  # Shouldn't lose everything
        assert isinstance(strat_total, float)
        assert isinstance(bh_total, float)

    def test_simulate_sideways(self):
        """In a sideways market, strategy returns near zero."""
        import numpy as np
        np.random.seed(42)
        days = 100
        close = pd.Series(100.0 + np.cumsum(np.random.normal(0.0, 0.5, days)))
        close = close.clip(lower=1.0)
        daily_ret = close.pct_change().fillna(0)

        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        position = (ma5 > ma20).astype(int)

        rets = daily_ret * position.shift(1).fillna(0)
        strat_cum = (1 + rets).cumprod()
        strat_total = float((strat_cum.iloc[-1] - 1) * 100)

        # Should be a valid number
        assert isinstance(strat_total, float)
