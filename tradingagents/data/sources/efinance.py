"""efinance data source — multi-market secondary provider.

Free, no registration, supports A-stock / HK / US markets.
Provides: K-line, real-time quotes, financial info, fund flow.
Based on eastmoney data.

GitHub: https://github.com/Micro-sheep/efinance
"""

from __future__ import annotations

import pandas as pd

from tradingagents.data.sources.base import DataSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)


def _ef_symbol(symbol: str) -> str:
    """Convert ticker to efinance format. efinance uses plain codes like '600519'."""
    return symbol.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".HK", "").replace(".SS", "")


class EfinanceSource(DataSource):
    """efinance adapter. Supports A-stock, HK stock, and US stock."""

    name = "efinance"

    # ---- K-line ----

    def kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        try:
            import efinance as ef
            klt = {"qfq": 1, "hfq": 2, "none": 0}.get(adjust, 1)
            df = ef.stock.get_quote_history(
                _ef_symbol(symbol),
                beg=start_date.replace("-", ""),
                end=end_date.replace("-", ""),
                klt=klt,
            )
            if df is None or df.empty:
                return pd.DataFrame()
            # efinance column names (Chinese)
            col_map = {
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "涨跌幅": "change_pct",
                "换手率": "turn",
            }
            df = df.rename(columns=col_map)
            df["symbol"] = symbol
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            for col in ("open", "high", "low", "close", "volume", "amount", "change_pct", "turn"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()

    def kline_weekly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        # efinance doesn't natively support weekly; aggregate from daily
        df = self.kline_daily(symbol, start_date, end_date, adjust)
        if df.empty or "date" not in df.columns:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        weekly = df.resample("W").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum", "amount": "sum",
        }).dropna()
        weekly["symbol"] = symbol
        return weekly.reset_index()

    def kline_monthly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        df = self.kline_daily(symbol, start_date, end_date, adjust)
        if df.empty or "date" not in df.columns:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        monthly = df.resample("M").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum", "amount": "sum",
        }).dropna()
        monthly["symbol"] = symbol
        return monthly.reset_index()

    # ---- Real-time Quote ----

    def quote(self, symbol: str) -> pd.DataFrame:
        try:
            import efinance as ef
            info = ef.stock.get_base_info(_ef_symbol(symbol))
            if info is None:
                return pd.DataFrame()
            # Returns a Series; convert to single-row DataFrame
            df = pd.DataFrame([info.to_dict() if hasattr(info, "to_dict") else info])
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Financials ----

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        try:
            import efinance as ef
            info = ef.stock.get_base_info(_ef_symbol(symbol))
            if info is None:
                return pd.DataFrame()
            df = pd.DataFrame([info.to_dict() if hasattr(info, "to_dict") else info])
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Capital Flow ----

    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame:
        try:
            import efinance as ef
            df = ef.stock.get_latest_quote(_ef_symbol(symbol))
            if df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- News (efinance doesn't provide news natively) ----

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        return pd.DataFrame()

    # ---- Not supported by efinance ----

    def balance_sheet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def income_statement(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def cash_flow(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
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

    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()
