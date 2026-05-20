"""Yahoo Finance data source via yfinance library.

QD uses yfinance, not direct HTTP.  We do the same — the library handles
cookie/crumb auth, rate limiting, and regional restrictions internally.

Key endpoints (via yfinance):
- Chart (K-line): yf.Ticker(symbol).history(start=..., end=..., interval=...)
- Quote:          yf.Ticker(symbol).info / fast_info
- News:           yf.Ticker(symbol).news
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from tradingagents.logging import get_logger

logger = get_logger(__name__)

# ── Interval mapping ───────────────────────────────────────────────────
_INTERVAL_MAP = {
    "daily": "1d", "1d": "1d", "day": "1d",
    "weekly": "1wk", "1wk": "1wk", "week": "1wk",
    "monthly": "1mo", "1mo": "1mo", "month": "1mo",
}


# ── symbol helpers ─────────────────────────────────────────────────────

def _yf_symbol(symbol: str, market: str = "us_stock") -> str:
    """Normalize symbol for Yahoo Finance."""
    s = symbol.strip().upper()
    if market == "a_stock":
        s = s.replace(".SH", "").replace(".SZ", "")
        if s.startswith(("6", "9")):
            return f"{s}.SS"
        return f"{s}.SZ"
    if market == "hk_stock":
        s = s.replace(".HK", "").replace("HK.", "").lstrip("0") or "0"
        s = s.zfill(4)
        return f"{s}.HK"
    return s


# ── K-line ─────────────────────────────────────────────────────────────

def fetch_kline(
    symbol: str,
    market: str = "us_stock",
    interval: str = "1d",
    start_date: str = "",
    end_date: str = "",
    count: int = 500,
    timeout: float = 30,
) -> list[dict]:
    """Fetch K-line via yfinance. Returns list of OHLCV dicts."""
    import yfinance as yf
    ysym = _yf_symbol(symbol, market)
    yi = _INTERVAL_MAP.get(str(interval).lower(), "1d")
    try:
        t = yf.Ticker(ysym)
        df = t.history(start=start_date or None, end=end_date or None,
                       interval=yi, auto_adjust=False)
        if df.empty:
            return []
        df = df.reset_index()
        rows = []
        for _, row in df.iterrows():
            try:
                dt = row.get("Date") or row.get("index")
                if dt is None:
                    continue
                rows.append({
                    "date": str(dt)[:19],
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                    "amount": round(float(row["Close"]) * int(row["Volume"]), 2),
                })
            except (ValueError, KeyError):
                continue
        # Apply date filters (yfinance sometimes returns extra data)
        if start_date:
            st = pd.Timestamp(start_date)
            rows = [r for r in rows if pd.Timestamp(r["date"][:10]) >= st]
        if end_date:
            ed = pd.Timestamp(end_date)
            rows = [r for r in rows if pd.Timestamp(r["date"][:10]) <= ed]
        return rows
    except Exception:
        logger.debug("yfinance kline failed for %s", ysym, exc_info=True)
        return []


# ── Quote ──────────────────────────────────────────────────────────────

def fetch_quote(symbol: str, market: str = "us_stock", timeout: float = 15) -> Optional[dict]:
    """Fetch real-time quote via yfinance."""
    import yfinance as yf
    ysym = _yf_symbol(symbol, market)
    try:
        t = yf.Ticker(ysym)
        info = t.info
        if not info:
            return None
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName") or "",
            "price": info.get("currentPrice") or info.get("regularMarketPrice", 0.0),
            "change_pct": info.get("regularMarketChangePercent", 0.0),
            "open": info.get("regularMarketOpen") or info.get("open", 0.0),
            "high": info.get("regularMarketDayHigh") or info.get("dayHigh", 0.0),
            "low": info.get("regularMarketDayLow") or info.get("dayLow", 0.0),
            "pre_close": info.get("previousClose") or info.get("regularMarketPreviousClose", 0.0),
            "volume": int(info.get("regularMarketVolume") or info.get("volume", 0)),
            "pe": info.get("trailingPE"),
            "pb": info.get("priceToBook"),
            "market_cap": info.get("marketCap"),
            "turnover": 0.0,
            "amount": 0.0,
            "timestamp": datetime.now(),
        }
    except Exception:
        logger.debug("yfinance quote failed for %s", ysym, exc_info=True)
        return None


def quote_to_df(raw: Optional[dict]) -> pd.DataFrame:
    if not raw or raw.get("price", 0) == 0:
        return pd.DataFrame()
    return pd.DataFrame([{
        "symbol": raw["symbol"],
        "name": raw["name"],
        "price": raw["price"],
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


# ── DataSource-compatible class ────────────────────────────────────────

class YahooSource:
    """yfinance-based Yahoo Finance source. All markets."""

    name = "yahoo"

    def __init__(self, market: str = "us_stock"):
        self._market = market

    def kline_daily(self, symbol: str, start_date: str = "", end_date: str = "",
                    adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(symbol, self._market, "1d", start_date, end_date)
        return _kline_df(rows, start_date, end_date)

    def kline_weekly(self, symbol: str, start_date: str = "", end_date: str = "",
                     adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(symbol, self._market, "1wk", start_date, end_date)
        return _kline_df(rows, start_date, end_date)

    def kline_monthly(self, symbol: str, start_date: str = "", end_date: str = "",
                      adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(symbol, self._market, "1mo", start_date, end_date)
        return _kline_df(rows, start_date, end_date)

    def quote(self, symbol: str) -> pd.DataFrame:
        return quote_to_df(fetch_quote(symbol, self._market))

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        return self.quote(symbol)

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        import yfinance as yf
        ysym = _yf_symbol(symbol, self._market)
        try:
            t = yf.Ticker(ysym)
            items = t.news[:limit]
            rows = [{"title": n.get("title", ""), "source": n.get("publisher", ""),
                     "url": n.get("link", ""), "summary": n.get("summary", "")}
                    for n in items]
            return pd.DataFrame(rows)
        except Exception:
            return pd.DataFrame()

    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        import yfinance as yf
        ysym = _yf_symbol(symbol, self._market)
        try:
            t = yf.Ticker(ysym)
            df = t.insider_transactions
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    # Unsupported
    balance_sheet = lambda self, s: pd.DataFrame()
    income_statement = lambda self, s: pd.DataFrame()
    cash_flow = lambda self, s: pd.DataFrame()
    fund_flow = lambda self, s, days=30: pd.DataFrame()
    northbound_flow = lambda self, days=30: pd.DataFrame()
    dragon_tiger_board = lambda self, s, days=30: pd.DataFrame()
    lockup_expiry = lambda self, s, months=6: pd.DataFrame()
    profit_forecast = lambda self, s: pd.DataFrame()
    hot_stocks = lambda self, limit=20: pd.DataFrame()
    technical_indicators = lambda self, s, sd="", ed="": pd.DataFrame()


# ── helpers ────────────────────────────────────────────────────────────

def _kline_df(rows: list[dict], start_date: str, end_date: str) -> pd.DataFrame:
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
