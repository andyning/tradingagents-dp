"""Tencent Finance HTTP data source.

Free, no auth, always available in China.
Provides A-share and HK stock K-line + real-time quotes.

Endpoints:
- Quote:  GET https://qt.gtimg.cn/q={code}
- K-line: GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{period},,,{count},{adj}
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from typing import Optional

import pandas as pd
import requests

from tradingagents.logging import get_logger

logger = get_logger(__name__)

# ── shared session with retry-friendly headers ─────────────────────────
from tradingagents.data.http import resilient_session

_last_request = 0.0
_MIN_INTERVAL = 0.15  # seconds between requests

_TENCENT_HOST = "web.ifzq.gtimg.cn"


def _get_session():
    return resilient_session(_TENCENT_HOST)


def _rate_limit():
    global _last_request
    elapsed = time.monotonic() - _last_request
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request = time.monotonic()


# ── symbol helpers ─────────────────────────────────────────────────────

def normalize_cn_code(symbol: str) -> str:
    """Normalize A-share symbol to Tencent internal format (sh600519 / sz000001)."""
    s = symbol.strip().upper()
    # Already normalized
    if re.match(r"^(SH|SZ)\d{6}$", s):
        return s.lower()
    # With suffix
    if re.match(r"^\d{6}\.(SH|SZ)$", s):
        code, market = s.split(".")
        return f"{market.lower()}{code}"
    # Bare code
    if re.match(r"^\d{6}$", s):
        prefix = "sh" if s.startswith("6") else "sz"
        return f"{prefix}{s}"
    return s.lower()


def normalize_hk_code(symbol: str) -> str:
    """Normalize HK stock symbol to Tencent internal format (hk00700)."""
    s = symbol.strip().upper()
    if s.startswith("HK."):
        s = s[3:]
    s = s.replace(".HK", "").strip()
    # Pad to 5 digits
    if s.isdigit():
        s = s.zfill(5)
    return f"hk{s}"


# ── quote ──────────────────────────────────────────────────────────────

def fetch_quote(code: str, timeout: float = 10) -> Optional[dict]:
    """Fetch real-time quote from Tencent.

    Returns dict with keys: symbol, name, last, change, change_pct,
    high, low, open, pre_close, volume, amount, turnover, pe, pb,
    market_cap, timestamp.
    """
    _rate_limit()
    url = f"https://qt.gtimg.cn/q={code}"
    try:
        resp = _get_session().get(
            url,
            headers={"Referer": "https://qt.gtimg.cn/"},
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.text
        if not text or "~" not in text:
            return None

        # Extract the payload between =" and trailing "
        # Format: v_sh600519="1~name~code~last~prev~open~..."
        match = re.search(r'="(.*)"', text)
        if not match:
            return None
        parts = match.group(1).split("~")
        if len(parts) < 40:
            return None

        def _f(i, default=None):
            try:
                return parts[i]
            except IndexError:
                return default

        def _float(i, default=0.0):
            try:
                return float(parts[i])
            except (ValueError, IndexError):
                return default

        return {
            "symbol": _f(2, ""),
            "name": _f(1, ""),
            "last": _float(3),
            "change": _float(31),
            "change_pct": _float(32),
            "high": _float(33),
            "low": _float(34),
            "open": _float(5),
            "pre_close": _float(4),
            "volume": int(_float(6)),
            "amount": _float(37) * 10000 if _float(37) else 0.0,  # 万->元
            "turnover": _float(38),
            "pe": _float(39) if _float(39) else None,
            "pb": _float(46) if _float(46) else None,
            "market_cap": _float(45) if _float(45) else None,  # 亿
            "timestamp": datetime.now(),
        }
    except Exception:
        logger.debug("Tencent quote failed for %s", code, exc_info=True)
        return None


def quote_to_dataframe(raw: Optional[dict]) -> pd.DataFrame:
    """Convert Tencent quote dict to DataFrame matching schema.Quote."""
    if not raw or raw.get("last", 0) == 0:
        return pd.DataFrame()
    return pd.DataFrame([{
        "symbol": raw["symbol"],
        "name": raw["name"],
        "price": raw["last"],
        "change_pct": raw.get("change_pct", 0.0),
        "volume": raw.get("volume", 0),
        "amount": raw.get("amount", 0.0),
        "high": raw.get("high", 0.0),
        "low": raw.get("low", 0.0),
        "open": raw.get("open", 0.0),
        "pre_close": raw.get("pre_close", 0.0),
        "turnover": raw.get("turnover", 0.0),
        "pe": raw.get("pe"),
        "pb": raw.get("pb"),
        "market_cap": raw.get("market_cap"),
        "timestamp": raw.get("timestamp", datetime.now()),
    }])


# ── K-line ─────────────────────────────────────────────────────────────

# Adjustment mapping
_ADJUST_MAP = {"qfq": "qfq", "hfq": "hfq", "none": "", "": ""}


def fetch_kline(
    code: str,
    period: str = "day",
    count: int = 500,
    adjust: str = "qfq",
    timeout: float = 15,
) -> list[dict]:
    """Fetch historical K-line from Tencent.

    Args:
        code: Tencent-format code (sh600519 / hk00700)
        period: day / week / month
        count: number of bars
        adjust: qfq / hfq / none / ""

    Returns list of dicts with keys: date, open, close, high, low, volume.
    """
    _rate_limit()
    adj = _ADJUST_MAP.get(adjust, "qfq")
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{code},{period},,,{int(count)},{adj}"}

    try:
        resp = _get_session().get(
            url,
            params=params,
            headers={"Referer": "https://gu.qq.com/"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            return []

        inner = data.get("data", {}).get(code)
        if not inner:
            return []

        # Find the right key — varies by market and adjustment
        # A-stock: qfqday, hfqday, day
        # HK: day, week, m1
        key = None
        period_lower = period.lower()
        for candidate in [f"qfq{period_lower}", period_lower, f"hfq{period_lower}"]:
            if candidate in inner:
                key = candidate
                break
        # Also try prefix match for other variations (e.g. qfqday vs day for HK)
        if key is None:
            for k in inner:
                if period_lower in k.lower():
                    key = k
                    break

        if key is None:
            return []

        rows_raw = inner[key]
        if not rows_raw:
            return []

        # Each row: [timestamp_str, open, close, high, low, volume]
        results = []
        for row in rows_raw:
            try:
                ts = str(row[0])
                date_str = ts[:10] if len(ts) >= 10 else ts
                results.append({
                    "date": date_str,
                    "open": float(row[1]),
                    "close": float(row[2]),
                    "high": float(row[3]),
                    "low": float(row[4]),
                    "volume": int(float(row[5])),
                    "amount": round(float(row[2]) * float(row[5]), 2),
                })
            except (ValueError, IndexError, TypeError):
                continue

        return results

    except Exception:
        logger.debug("Tencent kline failed for %s period=%s", code, period, exc_info=True)
        return []


# ── DataSource-compatible class ────────────────────────────────────────

class TencentSource:
    """HTTP-based source matching the DataSource interface.

    Supports A-share (sh600519) and HK stock (hk00700).
    """

    name = "tencent"

    def __init__(self, market: str = "a_stock"):
        self._market = market

    def _to_code(self, symbol: str) -> str:
        if self._market == "hk_stock":
            return normalize_hk_code(symbol)
        return normalize_cn_code(symbol)

    # K-line -------------------------------------------------------------

    def kline_daily(
        self, symbol: str, start_date: str = "", end_date: str = "",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        rows = fetch_kline(self._to_code(symbol), "day", 500, adjust)
        return _rows_to_df(rows, start_date, end_date)

    def kline_weekly(
        self, symbol: str, start_date: str = "", end_date: str = "",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        rows = fetch_kline(self._to_code(symbol), "week", 300, adjust)
        return _rows_to_df(rows, start_date, end_date)

    def kline_monthly(
        self, symbol: str, start_date: str = "", end_date: str = "",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        rows = fetch_kline(self._to_code(symbol), "month", 200, adjust)
        return _rows_to_df(rows, start_date, end_date)

    # Quote --------------------------------------------------------------

    def quote(self, symbol: str) -> pd.DataFrame:
        return quote_to_dataframe(fetch_quote(self._to_code(symbol)))

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        # Tencent quote already contains PE, PB, market_cap
        return self.quote(symbol)

    # Unsupported — return empty so fallback proceeds --------------------
    balance_sheet = lambda self, s: pd.DataFrame()
    income_statement = lambda self, s: pd.DataFrame()
    cash_flow = lambda self, s: pd.DataFrame()
    news = lambda self, s, limit=20: pd.DataFrame()
    fund_flow = lambda self, s, days=30: pd.DataFrame()
    northbound_flow = lambda self, days=30: pd.DataFrame()
    dragon_tiger_board = lambda self, s, days=30: pd.DataFrame()
    lockup_expiry = lambda self, s, months=6: pd.DataFrame()
    profit_forecast = lambda self, s: pd.DataFrame()
    hot_stocks = lambda self, limit=20: pd.DataFrame()
    insider_transactions = lambda self, s: pd.DataFrame()
    technical_indicators = lambda self, s, sd="", ed="": pd.DataFrame()


# ── helpers ────────────────────────────────────────────────────────────

def _rows_to_df(rows: list[dict], start_date: str, end_date: str) -> pd.DataFrame:
    """Convert kline rows to DataFrame, optionally filtering by date range."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        if start_date:
            df = df[df["date"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["date"] <= pd.Timestamp(end_date)]
        df = df.sort_values("date").reset_index(drop=True)
    return df
