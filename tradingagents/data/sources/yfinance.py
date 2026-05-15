"""Yahoo Finance data source — US/HK stock primary, A-stock fallback.

Free, no registration. Provides global market data.
Best for: US stocks, HK stocks. Also works for A-stock as fallback.
"""

from __future__ import annotations

import pandas as pd

from tradingagents.data.sources.base import DataSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)


# yfinance symbol format for different markets
def _yf_symbol(symbol: str, market: str = "a_stock") -> str:
    """Convert ticker to yfinance format."""
    s = symbol.strip().upper()
    if market == "a_stock":
        if s.startswith("6"):
            return f"{s}.SS"
        return f"{s}.SZ"
    elif market == "hk_stock":
        # HK stocks: pad to 4 digits + .HK
        return f"{s:0>4}.HK"
    elif market == "us_stock":
        return s
    return s


class YFinanceSource(DataSource):
    """Yahoo Finance adapter."""

    name = "yfinance"

    def __init__(self, market: str = "a_stock"):
        self.market = market

    def _ticker(self, symbol: str):
        import yfinance as yf
        return yf.Ticker(_yf_symbol(symbol, self.market))

    # ---- K-line ----

    def kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            df = t.history(start=start_date, end=end_date)
            if df.empty:
                return pd.DataFrame()
            df = df.reset_index()
            df = df.rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            df["symbol"] = symbol
            df["amount"] = df.get("close", 0) * df.get("volume", 0)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            for col in ("open", "high", "low", "close", "volume", "amount"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()

    def kline_weekly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            df = t.history(start=start_date, end=end_date, interval="1wk")
            if df.empty:
                return pd.DataFrame()
            df = df.reset_index()
            df = df.rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            df["symbol"] = symbol
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            return df
        except Exception:
            return pd.DataFrame()

    def kline_monthly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            df = t.history(start=start_date, end=end_date, interval="1mo")
            if df.empty:
                return pd.DataFrame()
            df = df.reset_index()
            df = df.rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            df["symbol"] = symbol
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Quote ----

    def quote(self, symbol: str) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            info = t.info
            if not info:
                return pd.DataFrame()
            df = pd.DataFrame([{
                "symbol": symbol,
                "name": info.get("shortName", ""),
                "price": info.get("currentPrice") or info.get("regularMarketPrice", 0),
                "pe": info.get("trailingPE"),
                "pb": info.get("priceToBook"),
                "market_cap": info.get("marketCap"),
            }])
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Financials ----

    def balance_sheet(self, symbol: str) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            df = t.balance_sheet
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.T.reset_index()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    def income_statement(self, symbol: str) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            df = t.financials
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.T.reset_index()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    def cash_flow(self, symbol: str) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            df = t.cashflow
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.T.reset_index()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        return self.quote(symbol)

    # ---- Insider Transactions ----

    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            df = t.insider_transactions
            if df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Remaining methods return empty ----

    def technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        try:
            t = self._ticker(symbol)
            news = t.news[:limit] if t.news else []
            if not news:
                return pd.DataFrame()
            rows = [{"title": n.get("title", ""), "source": n.get("publisher", ""),
                     "url": n.get("link", ""), "summary": n.get("summary", "")} for n in news]
            return pd.DataFrame(rows)
        except Exception:
            return pd.DataFrame()

    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def northbound_flow(self, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def dragon_tiger_board(self, symbol: str, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def lockup_expiry(self, symbol: str, months: int = 6) -> pd.DataFrame:
        return pd.DataFrame()

    def profit_forecast(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def hot_stocks(self, limit: int = 20) -> pd.DataFrame:
        return pd.DataFrame()

    def concept_blocks(self) -> pd.DataFrame:
        return pd.DataFrame()

    def industry_comparison(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()
