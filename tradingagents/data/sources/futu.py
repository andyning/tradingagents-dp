"""Futu OpenAPI data source — free, no account needed.

Requires Futu OpenD running locally (default: localhost:11111).
Download: https://www.futunn.com/download/OpenAPI

Free tier (no account): 100 subscriptions, 100 K-line requests.
Supports A-shares (SH/SZ), HK stocks, and US stocks.
"""

from __future__ import annotations

import threading
import time
from datetime import date

import pandas as pd

from tradingagents.data.sources.base import DataSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

# Symbol format conversion
def _futu_symbol(symbol: str, market: str) -> str:
    s = symbol.strip().upper()
    if market == "a_stock":
        if s.startswith("6"):
            return f"SH.{s}"
        return f"SZ.{s}"
    elif market == "hk_stock":
        return f"HK.{s:0>5}"  # 5-digit, zero-padded
    elif market == "us_stock":
        return f"US.{s}"
    return s


class FutuSource(DataSource):
    """Futu OpenD adapter. Requires OpenD gateway running locally."""

    name = "futu"

    def __init__(self, market: str = "a_stock"):
        self.market = market
        self._ctx = None
        self._lock = threading.Lock()
        self._connected = False

    def _connect(self):
        if self._connected and self._ctx is not None:
            return True
        with self._lock:
            if self._connected:
                return True
            try:
                from futu import OpenQuoteContext, RET_OK
                self._ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
                self._ctx.set_conn_timeout(3)  # 3s timeout — fail fast if OpenD not running
                self._connected = True
                logger.debug("Futu OpenD connected")
                return True
            except Exception:
                self._connected = False
                self._ctx = None
                return False

    def _disconnect(self):
        try:
            if self._ctx:
                self._ctx.close()
        except Exception:
            pass
        self._connected = False
        self._ctx = None

    def __del__(self):
        self._disconnect()

    # ---- K-line ----

    def kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "K_DAY", adjust)

    def kline_weekly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "K_WEEK", adjust)

    def kline_monthly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "K_MON", adjust)

    def _fetch_kline(
        self, symbol: str, start_date: str, end_date: str, ktype: str, adjust: str
    ) -> pd.DataFrame:
        if not self._connect():
            return pd.DataFrame()
        try:
            from futu import KLType, AuType

            ktype_map = {"K_DAY": KLType.K_DAY, "K_WEEK": KLType.K_WEEK, "K_MON": KLType.K_MON}
            au_map = {"qfq": AuType.QFQ, "hfq": AuType.HFQ, "none": AuType.NONE}

            futu_sym = _futu_symbol(symbol, self.market)
            ret, df, _ = self._ctx.request_history_kline(
                futu_sym,
                start=start_date,
                end=end_date,
                ktype=ktype_map.get(ktype, KLType.K_DAY),
                autype=au_map.get(adjust, AuType.QFQ),
                max_count=500,
            )
            if ret != 0 or df is None or df.empty:
                return pd.DataFrame()

            df = df.rename(columns={
                "time_key": "date", "open": "open", "high": "high",
                "low": "low", "close": "close", "volume": "volume",
                "turnover": "amount", "change_rate": "change_pct",
                "turnover_rate": "turn", "pe_ratio": "pe", "pb_ratio": "pb",
            })
            df["symbol"] = symbol
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            for col in ("open","high","low","close","volume","amount","change_pct","turn","pe","pb"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            logger.info("[futu] %s returned %d rows (market=%s)", symbol, len(df), self.market)
            return df
        except Exception as exc:
            logger.debug("Futu K-line failed: %s", exc)
            return pd.DataFrame()

    # ---- Quote ----

    def quote(self, symbol: str) -> pd.DataFrame:
        if not self._connect():
            return pd.DataFrame()
        try:
            futu_sym = _futu_symbol(symbol, self.market)
            ret, df = self._ctx.get_market_snapshot([futu_sym])
            if ret != 0 or df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Financial summary ----
    def financial_summary(self, symbol: str) -> pd.DataFrame:
        return self.quote(symbol)

    # ---- Unsupported by Futu free tier ----
    def balance_sheet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def income_statement(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def cash_flow(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
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

    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()
