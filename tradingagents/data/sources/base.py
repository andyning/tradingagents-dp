"""Abstract base class for data source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataSource(ABC):
    """Base class for all data source adapters.

    Each source implements a standard set of endpoints.  Methods that are
    not supported by a specific source should return ``pd.DataFrame()``
    (empty) so the fallback chain can proceed to the next source.
    """

    name: str = "base"

    # ---- K-line ----

    def kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """Daily K-line data. Returns DataFrame with standard OHLCV columns."""
        raise NotImplementedError

    def kline_weekly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        raise NotImplementedError

    def kline_monthly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        raise NotImplementedError

    # ---- Real-time Quote ----

    def quote(self, symbol: str) -> pd.DataFrame:
        """Real-time or latest price quote."""
        raise NotImplementedError

    # ---- Financials ----

    def balance_sheet(self, symbol: str) -> pd.DataFrame:
        raise NotImplementedError

    def income_statement(self, symbol: str) -> pd.DataFrame:
        raise NotImplementedError

    def cash_flow(self, symbol: str) -> pd.DataFrame:
        raise NotImplementedError

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        """Key financial indicators (PE, PB, ROE, etc.)."""
        raise NotImplementedError

    # ---- Technical Indicators ----

    def technical_indicators(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Calculated technical indicators (MA, MACD, RSI, Bollinger)."""
        raise NotImplementedError

    # ---- News ----

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        raise NotImplementedError

    # ---- Capital Flow ----

    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Main force capital flow."""
        raise NotImplementedError

    def northbound_flow(self, days: int = 30) -> pd.DataFrame:
        """Northbound (沪深港通) capital flow."""
        raise NotImplementedError

    # ---- A-stock specific ----

    def dragon_tiger_board(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Dragon Tiger Board (龙虎榜)."""
        raise NotImplementedError

    def lockup_expiry(self, symbol: str, months: int = 6) -> pd.DataFrame:
        """Upcoming share lockup expiry (限售解禁)."""
        raise NotImplementedError

    def profit_forecast(self, symbol: str) -> pd.DataFrame:
        """Analyst profit forecast."""
        raise NotImplementedError

    def hot_stocks(self, limit: int = 20) -> pd.DataFrame:
        """Current hot / trending stocks."""
        raise NotImplementedError

    def concept_blocks(self) -> pd.DataFrame:
        """Concept / sector block data."""
        raise NotImplementedError

    def industry_comparison(self, symbol: str) -> pd.DataFrame:
        """Industry peer comparison."""
        raise NotImplementedError

    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        """Insider trading / major shareholder transactions."""
        raise NotImplementedError
