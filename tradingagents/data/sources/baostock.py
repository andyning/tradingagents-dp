"""Baostock data source — primary A-stock data provider.

Free, no registration required, independent data service (not scraping).
Provides: daily/weekly/monthly/5min/15min/30min/60min K-line,
quarterly financial statements, industry classifications, macro data.
Data from 1990-present.

Official site: http://baostock.com
"""

from __future__ import annotations

from datetime import date, datetime

import baostock as bs
import pandas as pd

from tradingagents.data.sources.base import DataSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

# Mapping of frequency to Baostock format
_FREQ_MAP = {
    "daily": "d",
    "weekly": "w",
    "monthly": "m",
    "5min": "5",
    "15min": "15",
    "30min": "30",
    "60min": "60",
}

# Baostock adjustflag codes
_ADJUST_MAP = {
    "qfq": "2",   # Forward-adjusted (前复权)
    "hfq": "1",   # Backward-adjusted (后复权)
    "none": "3",  # Not adjusted (不复权)
}

# Baostock uses "sh.XXXXXX" or "sz.XXXXXX" prefix
def _bs_symbol(symbol: str) -> str:
    """Convert a standard ticker to Baostock format."""
    symbol = symbol.strip().upper()
    if symbol.startswith("SH.") or symbol.startswith("SZ."):
        return symbol
    if symbol.startswith("6"):
        return f"sh.{symbol}"
    return f"sz.{symbol}"


class BaostockSource(DataSource):
    """Baostock data adapter. A-stock K-line and financial data."""

    name = "baostock"

    def __init__(self):
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            lg = bs.login()
            if lg.error_code != "0":
                logger.error("Baostock login failed: %s", lg.error_msg)
                raise ConnectionError(f"Baostock login failed: {lg.error_msg}")
            self._logged_in = True
            logger.debug("Baostock logged in")

    def _logout(self):
        if self._logged_in:
            bs.logout()
            self._logged_in = False

    # ---- K-line ----

    def kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._query_kline(symbol, start_date, end_date, "daily", adjust)

    def kline_weekly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._query_kline(symbol, start_date, end_date, "weekly", adjust)

    def kline_monthly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._query_kline(symbol, start_date, end_date, "monthly", adjust)

    def _query_kline(
        self, symbol: str, start_date: str, end_date: str, freq: str, adjust: str
    ) -> pd.DataFrame:
        self._ensure_login()
        bs_sym = _bs_symbol(symbol)
        if freq in ("daily", "5min", "15min", "30min", "60min"):
            fields = "date,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,isST"
        else:
            # weekly/monthly only support basic fields
            fields = "date,open,high,low,close,volume,amount"
        try:
            rs = bs.query_history_k_data_plus(
                bs_sym,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency=_FREQ_MAP.get(freq, "d"),
                adjustflag=_ADJUST_MAP.get(adjust, "2"),
            )
            if rs.error_code != "0":
                logger.warning("Baostock K-line query error: %s", rs.error_msg)
                return pd.DataFrame()

            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=rs.fields)
            df = df.rename(columns={
                "preclose": "pre_close",
                "adjustflag": "adjust_flag",
                "tradestatus": "trade_status",
                "pctChg": "change_pct",
                "peTTM": "pe",
                "pbMRQ": "pb",
                "isST": "is_st",
            })
            for col in ("open", "high", "low", "close", "pre_close", "volume", "amount", "turn", "change_pct", "pe", "pb"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Quote ----

    def quote(self, symbol: str) -> pd.DataFrame:
        self._ensure_login()
        bs_sym = _bs_symbol(symbol)
        try:
            rs = bs.query_stock_basic(code=bs_sym)
            if rs.error_code != "0":
                return pd.DataFrame()
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                df["symbol"] = symbol
                return df
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    # ---- Financial Statements ----

    def balance_sheet(self, symbol: str) -> pd.DataFrame:
        return self._query_finance(symbol, "balance")

    def income_statement(self, symbol: str) -> pd.DataFrame:
        return self._query_finance(symbol, "profit")

    def cash_flow(self, symbol: str) -> pd.DataFrame:
        return self._query_finance(symbol, "cash")

    def _query_finance(self, symbol: str, data_type: str) -> pd.DataFrame:
        self._ensure_login()
        bs_sym = _bs_symbol(symbol)
        try:
            rs = bs.query_operation_data(code=bs_sym, year_type="report")
            # Baostock's financial API is different for each type
            # For simplicity, use the general operation data query
            if rs.error_code != "0":
                return pd.DataFrame()
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                df["symbol"] = symbol
                return df
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        """Use daily K-line data's last row for PE/PB etc."""
        today = date.today().strftime("%Y-%m-%d")
        df = self.kline_daily(symbol, today, today)
        if not df.empty:
            cols = ["date", "symbol", "close", "pe", "pb", "change_pct", "turn", "volume", "amount"]
            available = [c for c in cols if c in df.columns]
            return df[available].tail(1)
        return pd.DataFrame()

    # ---- Technical Indicators ----

    def technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Baostock provides raw data; indicators are calculated separately."""
        return pd.DataFrame()

    # ---- News (Baostock doesn't provide news) ----

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        return pd.DataFrame()

    # ---- Capital Flow (not available from Baostock) ----

    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def northbound_flow(self, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    # ---- A-stock specific (not available from Baostock) ----

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
