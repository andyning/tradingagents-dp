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


# Shared persistent Futu connection
_futu_ctx = None
_futu_lock = threading.Lock()
_FUTU_DOWN = False  # Fast-fail flag
_FUTU_DOWN_SINCE = 0.0  # Timestamp when marked DOWN (for TTL-based retry)
_FUTU_DOWN_TTL = 60  # Seconds before auto-retry


def _get_shared_futu():
    """Get or create a persistent Futu OpenQuoteContext. Auto-retries after TTL."""
    global _futu_ctx, _FUTU_DOWN, _FUTU_DOWN_SINCE
    if _FUTU_DOWN:
        if time.time() - _FUTU_DOWN_SINCE < _FUTU_DOWN_TTL:
            return None
        # TTL expired — allow one retry
        _FUTU_DOWN = False
        logger.debug("Futu DOWN TTL expired, retrying connection")
    if _futu_ctx is not None:
        try:
            return _futu_ctx
        except Exception:
            _futu_ctx = None
    with _futu_lock:
        if _FUTU_DOWN:
            return None
        if _futu_ctx is not None:
            return _futu_ctx
        # Pre-check: is port 11111 even open? (avoids OpenQuoteContext's endless retry)
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        port_open = s.connect_ex(("127.0.0.1", 11111)) == 0
        s.close()
        if not port_open:
            _FUTU_DOWN = True
            _FUTU_DOWN_SINCE = time.time()
            logger.debug("Futu port 11111 not open — fast-failing (%ds TTL)", _FUTU_DOWN_TTL)
            return None
        try:
            from futu import OpenQuoteContext
            _futu_ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
            logger.debug("Futu persistent connection established")
            return _futu_ctx
        except Exception:
            _FUTU_DOWN = True
            _FUTU_DOWN_SINCE = time.time()
            logger.debug("Futu unavailable — fast-failing (%ds TTL)", _FUTU_DOWN_TTL)
            return None


def _reset_futu_flag():
    """Reset the fast-fail flag (called on Refresh)."""
    global _FUTU_DOWN
    _FUTU_DOWN = False


class FutuSource(DataSource):
    """Futu OpenD adapter — uses persistent shared connection."""

    name = "futu"

    def __init__(self, market: str = "a_stock"):
        self.market = market

    def _get_ctx(self):
        """Get the shared persistent Futu connection."""
        return _get_shared_futu()

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
        ctx = self._get_ctx()
        if ctx is None:
            return pd.DataFrame()
        try:
            from futu import KLType, AuType

            ktype_map = {"K_DAY": KLType.K_DAY, "K_WEEK": KLType.K_WEEK, "K_MON": KLType.K_MON}
            au_map = {"qfq": AuType.QFQ, "hfq": AuType.HFQ, "none": AuType.NONE}

            futu_sym = _futu_symbol(symbol, self.market)
            ret, df, page_req_key = ctx.request_history_kline(
                futu_sym,
                start=start_date,
                end=end_date,
                ktype=ktype_map.get(ktype, KLType.K_DAY),
                autype=au_map.get(adjust, AuType.QFQ),
                max_count=500,
            )
            if ret != 0:
                logger.warning("Futu K-line failed: ret=%s symbol=%s", ret, futu_sym)
                return pd.DataFrame()
            if df is None or df.empty:
                logger.warning("Futu K-line empty: symbol=%s", futu_sym)
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
        # Connection stays open — shared persistent

    # ---- Quote ----

    def quote(self, symbol: str) -> pd.DataFrame:
        ctx = self._get_ctx()
        if ctx is None:
            return pd.DataFrame()
        try:
            futu_sym = _futu_symbol(symbol, self.market)
            ret, df = ctx.get_market_snapshot([futu_sym])
            if ret != 0 or df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()
        # Connection stays open — shared persistent

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
        """Get capital flow data from Futu (主力资金流向)."""
        ctx = self._get_ctx()
        if ctx is None:
            return pd.DataFrame()
        try:
            futu_sym = _futu_symbol(symbol, self.market)
            ret, df = ctx.get_capital_flow(futu_sym)
            if ret != 0 or df is None or df.empty:
                return pd.DataFrame()
            df = df.tail(days).copy()
            df["symbol"] = symbol
            return df
        except Exception:
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
