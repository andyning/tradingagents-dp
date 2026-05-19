"""Yahoo Finance HTTP data source.

Free, no auth.  May be blocked in mainland China — keep as middle-tier
fallback rather than primary source for CN/HK markets.

Yahoo requires a session cookie + crumb for API access.  We replicate
the flow that the yfinance library uses internally.

Key endpoints:
- Chart (K-line): GET https://query2.finance.yahoo.com/v8/finance/chart/{symbol}
- Quote summary:  GET https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from tradingagents.logging import get_logger

logger = get_logger(__name__)

from tradingagents.data.http import get_http_session as _get_http_session

_crumb: Optional[str] = None
_last_request = 0.0
_MIN_INTERVAL = 3.0  # Yahoo rate-limits aggressively


def _get_session() -> requests.Session:
    global _crumb
    sess = _get_http_session()
    if _crumb is None:
        # Obtain cookie + crumb (same flow as yfinance library)
        try:
            # Step 1: get cookie from fc.yahoo.com
            sess.get("https://fc.yahoo.com/", timeout=10)
            # Step 2: get crumb
            crumb_resp = sess.get(
                "https://query2.finance.yahoo.com/v1/test/getcrumb",
                timeout=10,
            )
            if crumb_resp.status_code == 200:
                _crumb = crumb_resp.text.strip()
                logger.debug("Yahoo crumb obtained: %s", _crumb[:8] if _crumb else "empty")
        except Exception:
            logger.debug("Yahoo crumb flow failed — API calls may get 403")
    return sess


def _rate_limit():
    global _last_request
    elapsed = time.monotonic() - _last_request
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request = time.monotonic()


# ── symbol helpers ─────────────────────────────────────────────────────

def _yf_symbol(symbol: str, market: str = "us_stock") -> str:
    """Normalize symbol for Yahoo Finance.

    A-stock: 600519 → 600519.SS  (Shanghai) / 000001 → 000001.SZ (Shenzhen)
    HK:      00700  → 0700.HK
    US:      AAPL   → AAPL
    """
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


# ── Chart / K-line ─────────────────────────────────────────────────────

_INTERVAL_MAP = {
    "daily": "1d", "1d": "1d", "day": "1d",
    "weekly": "1wk", "1wk": "1wk", "week": "1wk",
    "monthly": "1mo", "1mo": "1mo", "month": "1mo",
    "1h": "1h", "60min": "1h", "60": "1h",
    "30min": "30m", "30": "30m",
    "15min": "15m", "15": "15m",
    "5min": "5m", "5": "5m",
    "1min": "1m", "1": "1m",
}


def fetch_kline(
    symbol: str,
    market: str = "us_stock",
    interval: str = "1d",
    start_date: str = "",
    end_date: str = "",
    count: int = 500,
    timeout: float = 20,
) -> list[dict]:
    """Fetch K-line data from Yahoo Finance chart API.

    Returns list of dicts: date, open, high, low, close, volume.
    """
    ysym = _yf_symbol(symbol, market)
    yi = _INTERVAL_MAP.get(str(interval).lower(), "1d")

    # Build period/range
    _rate_limit()
    sess = _get_session()
    global _crumb
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ysym}"
    params = {
        "interval": yi,
        "range": _range_for_interval(yi, count),
        "includePrePost": "false",
    }
    if _crumb:
        params["crumb"] = _crumb

    try:
        resp = sess.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        result = (data.get("chart") or {}).get("result")
        if not result:
            return []
        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote = chart.get("indicators", {}).get("quote", [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        # Adjustments
        adj = chart.get("indicators", {}).get("adjclose", [{}])
        adjclose = (adj[0].get("adjclose") or []) if adj else []

        rows = []
        for i, ts in enumerate(timestamps):
            try:
                dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                c = closes[i] if i < len(closes) and closes[i] is not None else None
                if c is None:
                    continue
                factor = 1.0
                if adjclose and i < len(adjclose) and adjclose[i] is not None and c != 0:
                    factor = adjclose[i] / c

                rows.append({
                    "date": dt,
                    "open": _safe(opens[i]) * factor if i < len(opens) else 0.0,
                    "high": _safe(highs[i]) * factor if i < len(highs) else 0.0,
                    "low": _safe(lows[i]) * factor if i < len(lows) else 0.0,
                    "close": _safe(c) * factor,
                    "volume": int(_safe(volumes[i])) if i < len(volumes) else 0,
                    "amount": _safe(c) * factor * _safe(volumes[i]),
                })
            except (ValueError, IndexError):
                continue

        # Filter by date range
        if start_date:
            st = pd.Timestamp(start_date)
            rows = [r for r in rows if pd.Timestamp(r["date"][:10]) >= st]
        if end_date:
            ed = pd.Timestamp(end_date)
            rows = [r for r in rows if pd.Timestamp(r["date"][:10]) <= ed]

        return rows

    except Exception:
        logger.debug("Yahoo kline failed for %s", ysym, exc_info=True)
        return []


# ── Quote ──────────────────────────────────────────────────────────────

def fetch_quote(symbol: str, market: str = "us_stock", timeout: float = 15) -> Optional[dict]:
    """Fetch real-time quote from Yahoo Finance."""
    ysym = _yf_symbol(symbol, market)
    _rate_limit()
    sess = _get_session()
    global _crumb
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ysym}"
    params = {
        "modules": "price,summaryDetail,defaultKeyStatistics",
        "ssl": "true",
    }
    if _crumb:
        params["crumb"] = _crumb

    try:
        resp = sess.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        result = (data.get("quoteSummary") or {}).get("result")
        if not result:
            return None
        r = result[0]

        price = r.get("price") or {}
        summary = r.get("summaryDetail") or {}
        stats = r.get("defaultKeyStatistics") or {}

        def _get(*paths):
            for path in paths:
                parts = path.split(".")
                val = r
                for p in parts:
                    val = (val or {}).get(p)
                if val is not None:
                    return val
            return None

        return {
            "symbol": symbol,
            "name": _get("price.shortName", "quoteType.shortName", "price.longName") or "",
            "price": _safe(_get("regularMarketPrice.raw", "price.regularMarketPrice.raw")),
            "change_pct": _safe(_get("regularMarketChangePercent.raw",
                                      "price.regularMarketChangePercent.raw")),
            "open": _safe(_get("regularMarketOpen.raw", "price.regularMarketOpen.raw")),
            "high": _safe(_get("regularMarketDayHigh.raw", "price.regularMarketDayHigh.raw")),
            "low": _safe(_get("regularMarketDayLow.raw", "price.regularMarketDayLow.raw")),
            "pre_close": _safe(_get("previousClose.raw", "price.previousClose.raw",
                                    "regularMarketPreviousClose.raw",
                                    "summaryDetail.previousClose.raw")),
            "volume": int(_safe(_get("regularMarketVolume.raw", "price.regularMarketVolume.raw"))),
            "pe": _safe(_get("trailingPE.raw", "summaryDetail.trailingPE.raw")),
            "pb": _safe(_get("priceToBook.raw", "defaultKeyStatistics.priceToBook.raw")),
            "market_cap": _safe(_get("marketCap.raw", "price.marketCap.raw",
                                     "defaultKeyStatistics.marketCap.raw")),
            "turnover": 0.0,
            "amount": 0.0,
            "timestamp": datetime.now(),
        }
    except Exception:
        logger.debug("Yahoo quote failed for %s", ysym, exc_info=True)
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
    """HTTP-based Yahoo Finance source. All markets."""

    name = "yahoo"

    def __init__(self, market: str = "us_stock"):
        self._market = market

    # K-line ------------------------------------------------------------

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

    # Quote --------------------------------------------------------------

    def quote(self, symbol: str) -> pd.DataFrame:
        return quote_to_df(fetch_quote(symbol, self._market))

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        return self.quote(symbol)

    # Financial statements — limited via quoteSummary API ---------------
    balance_sheet = lambda self, s: pd.DataFrame()
    income_statement = lambda self, s: pd.DataFrame()
    cash_flow = lambda self, s: pd.DataFrame()

    # News — need different approach than yfinance's .news attribute ----
    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        # Yahoo Finance news RSS
        try:
            ysym = _yf_symbol(symbol, self._market)
            _rate_limit()
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ysym}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return pd.DataFrame()
            # Simple XML extraction
            import re
            titles = re.findall(r"<title>(.*?)</title>", resp.text)
            links = re.findall(r"<link>(.*?)</link>", resp.text)
            pubdates = re.findall(r"<pubDate>(.*?)</pubDate>", resp.text)
            # Skip the first title (channel title)
            rows = []
            for i, t in enumerate(titles[1:limit+1], start=1):
                rows.append({
                    "title": t,
                    "source": "Yahoo Finance",
                    "url": links[i] if i < len(links) else "",
                    "publish_time": pubdates[i-1] if i-1 < len(pubdates) else "",
                    "summary": t,
                })
            return pd.DataFrame(rows)
        except Exception:
            return pd.DataFrame()

    # Insider transactions ----------------------------------------------
    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        # Yahoo's insider transactions endpoint is rate-limited; skip for now
        return pd.DataFrame()

    # Unsupported — fall through ----------------------------------------
    fund_flow = lambda self, s, days=30: pd.DataFrame()
    northbound_flow = lambda self, days=30: pd.DataFrame()
    dragon_tiger_board = lambda self, s, days=30: pd.DataFrame()
    lockup_expiry = lambda self, s, months=6: pd.DataFrame()
    profit_forecast = lambda self, s: pd.DataFrame()
    hot_stocks = lambda self, limit=20: pd.DataFrame()
    technical_indicators = lambda self, s, sd="", ed="": pd.DataFrame()


# ── helpers ────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _range_for_interval(interval: str, count: int) -> str:
    """Map interval to a sensible Yahoo range covering `count` bars."""
    if interval in ("1m", "2m", "5m", "15m", "30m"):
        # Yahoo max for minute bars: 7d for 1m, 60d for 5m+
        return "7d" if interval == "1m" else "60d"
    if interval in ("1h", "60m"):
        return "730d"  # 2y
    # Daily/weekly/monthly
    if count <= 100:
        return "6mo"
    if count <= 250:
        return "1y"
    if count <= 500:
        return "2y"
    if count <= 1250:
        return "5y"
    return "10y"


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
