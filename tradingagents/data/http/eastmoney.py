"""Eastmoney (东方财富) HTTP data source.

Free, no auth.  The backbone of efinance / akshare — we call the HTTP
APIs directly so we can drop both library dependencies.

Key endpoints:
- K-line:    push2his.eastmoney.com/api/qt/stock/kline/get
- Snapshot:  push2.eastmoney.com/api/qt/stock/get
- Fund flow: push2.eastmoney.com/api/qt/stock/fflow/daykline/get
- News:      np-anotice-stock.eastmoney.com/api/security/ann
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

from tradingagents.data.http import resilient_session

_last_request = 0.0
_MIN_INTERVAL = 0.2

# Eastmoney uses multiple subdomains — probe them independently
_EM_HOSTS = {
    "kline": "push2.eastmoney.com",
    "snapshot": "push2.eastmoney.com",
    "fundflow": "push2.eastmoney.com",
    "clist": "push2.eastmoney.com",
    "kamt": "push2.eastmoney.com",
    "datacenter": "datacenter.eastmoney.com",
    "news": "np-anotice-stock.eastmoney.com",
}


def _get_session(endpoint: str = "kline"):
    host = _EM_HOSTS.get(endpoint, "push2.eastmoney.com")
    return resilient_session(host)


def _rate_limit():
    global _last_request
    elapsed = time.monotonic() - _last_request
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request = time.monotonic()


# ── market / symbol helpers ────────────────────────────────────────────
# Eastmoney secid format: {market_code}.{code}
#   A-share:  1.600519 (SH), 0.000001 (SZ)
#   HK:       116.00700
#   US:       105.AAPL (NASDAQ), 106.BRK.A (NYSE)


def _a_secid(symbol: str) -> str:
    """A-share symbol to Eastmoney secid."""
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "")
    prefix = "1" if s.startswith(("6", "9")) else "0"
    return f"{prefix}.{s}"


def _hk_secid(symbol: str) -> str:
    """HK symbol to Eastmoney secid."""
    s = symbol.strip().upper()
    for pfx in ("HK.", ".HK"):
        s = s.replace(pfx, "")
    return f"116.{s.strip().zfill(5)}"


# ── K-line ─────────────────────────────────────────────────────────────

# Period mapping: (klt, need_minute_pagination)
_KLT_MAP = {
    "day": 101, "daily": 101,
    "week": 102, "weekly": 102,
    "month": 103, "monthly": 103,
    "60": 60, "60min": 60, "1h": 60,
    "30": 30, "30min": 30,
    "15": 15, "15min": 15,
    "5": 5, "5min": 5,
    "1": 1, "1min": 1,
}


def fetch_kline(
    secid: str,
    period: str = "daily",
    count: int = 500,
    adjust: str = "qfq",
    timeout: float = 15,
) -> list[dict]:
    """Fetch K-line from Eastmoney.

    Args:
        secid: Eastmoney secid (e.g. "1.600519")
        period: daily / weekly / monthly / 60min / 30min / 15min / 5min / 1min
        count: max bars to return
        adjust: qfq (forward) / hfq (backward) / "" (none)

    Returns list of dicts: date, open, close, high, low, volume, amount,
                           change_pct, turn, pe (A-stock daily only).
    """
    klt = _KLT_MAP.get(str(period).lower(), 101)
    fqt = {"qfq": 1, "hfq": 2, "none": 0, "": 0}.get(adjust, 1)

    _rate_limit()
    url = "https://push2.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "klt": klt,
        "fqt": fqt,
        "end": "20500101",
        "lmt": min(count, 500),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": (
            "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116,f117"
        ),
    }

    try:
        resp = _get_session("kline").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rc") != 0 or not data.get("data"):
            return []

        klines = data["data"].get("klines") or []
        results = []
        for row_str in klines:
            parts = row_str.split(",")
            if len(parts) < 11:
                continue
            try:
                rec = {
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": int(float(parts[5])),
                    "amount": float(parts[6]),
                    "change_pct": _safe_float(parts[8], 0.0),
                    "turn": _safe_float(parts[10], 0.0),
                }
                # PE — present in daily A-stock K-line data
                if len(parts) >= 13:
                    rec["pe"] = _safe_float(parts[12], None)
                results.append(rec)
            except (ValueError, IndexError):
                continue

        return results

    except Exception:
        logger.debug("Eastmoney kline failed for %s klt=%s", secid, klt, exc_info=True)
        return []


# ── Snapshot / Quote ───────────────────────────────────────────────────

def fetch_snapshot(secid: str, timeout: float = 10) -> Optional[dict]:
    """Fetch real-time snapshot from Eastmoney.

    Returns dict with: symbol, name, price, change_pct, high, low, open,
    pre_close, volume, amount, turnover, pe, pb, market_cap.
    """
    _rate_limit()
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    fields = (
        "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,"
        "f60,f116,f117,f162,f167,f168,f169,f170,f171,f20"
    )
    params = {"secid": secid, "fields": fields}

    try:
        resp = _get_session("snapshot").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("data"):
            return None
        d = data["data"]
        # A-shares (secid 0.x or 1.x): f43 is in 分 (×100)
        # HK stocks (secid 116.x) and US (105.x/106.x): price in native units
        _is_a_share = secid.startswith(("0.", "1."))
        _scale = 100.0 if _is_a_share else 1.0
        raw_price = _safe_float(d.get("f43"), 0.0)
        raw_high = _safe_float(d.get("f44"), 0.0)
        raw_low = _safe_float(d.get("f45"), 0.0)
        raw_open = _safe_float(d.get("f46"), 0.0)
        raw_pre = _safe_float(d.get("f60"), 0.0)
        return {
            "symbol": d.get("f57", ""),
            "name": d.get("f58", ""),
            "price": raw_price / _scale,
            "change_pct": _safe_float(d.get("f170"), 0.0),
            "high": raw_high / _scale,
            "low": raw_low / _scale,
            "open": raw_open / _scale,
            "pre_close": raw_pre / _scale,
            "volume": int(_safe_float(d.get("f47"), 0)),
            "amount": _safe_float(d.get("f48"), 0.0),
            "turnover": _safe_float(d.get("f168"), 0.0),
            "pe": _safe_float(d.get("f162"), None) or _safe_float(d.get("f9"), None),
            "pb": _safe_float(d.get("f167"), None),
            "market_cap": _safe_float(d.get("f20"), None) or _safe_float(d.get("f116"), None),
            "timestamp": datetime.now(),
        }
    except Exception:
        logger.debug("Eastmoney snapshot failed for %s", secid, exc_info=True)
        return None


def snapshot_to_df(raw: Optional[dict]) -> pd.DataFrame:
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


# ── Fund Flow ──────────────────────────────────────────────────────────

def fetch_fund_flow(secid: str, days: int = 30, timeout: float = 15) -> pd.DataFrame:
    """Fetch individual stock fund flow from Eastmoney."""
    _rate_limit()
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": secid,
        "lmt": min(days, 120),
        "fields1": "f1,f2,f3,f7",
        "fields2": (
            "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
        ),
    }

    try:
        resp = _get_session("fundflow").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("data") or not data["data"].get("klines"):
            return pd.DataFrame()

        rows = []
        for row_str in data["data"]["klines"]:
            parts = row_str.split(",")
            if len(parts) < 12:
                continue
            try:
                rows.append({
                    "date": parts[0],
                    "symbol": "",
                    "main_inflow": _safe_float(parts[1], 0.0) / 1e4,
                    "main_inflow_pct": _safe_float(parts[7], 0.0),
                    "super_large_inflow": _safe_float(parts[3], 0.0) / 1e4,
                    "large_inflow": _safe_float(parts[5], 0.0) / 1e4,
                    "medium_inflow": _safe_float(parts[9], 0.0) / 1e4,
                    "small_inflow": _safe_float(parts[11], 0.0) / 1e4,
                })
            except (ValueError, IndexError):
                continue
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Eastmoney fund flow failed for %s", secid, exc_info=True)
        return pd.DataFrame()


# ── News ───────────────────────────────────────────────────────────────

def fetch_news_eastmoney(symbol: str, limit: int = 20, timeout: float = 15) -> pd.DataFrame:
    """Fetch A-stock announcements from Eastmoney."""
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".HK", "")
    _rate_limit()
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "page_size": min(limit, 50),
        "page_index": 1,
        "stock_list": s,
    }
    sess = _get_session("news")
    headers = {"Referer": "https://data.eastmoney.com/"}

    try:
        resp = sess.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("list", [])
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            rows.append({
                "title": it.get("title", ""),
                "source": "eastmoney",
                "url": it.get("url", f"https://data.eastmoney.com/notices/detail/{symbol}/"
                        f"{it.get('notice_date','').replace('-','')}.html"),
                "publish_time": pd.Timestamp(it.get("notice_date")) if it.get("notice_date") else None,
                "summary": (it.get("title", "") or "")[:300],
            })
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Eastmoney news failed for %s", symbol, exc_info=True)
        return pd.DataFrame()


def fetch_news_sina(symbol: str, limit: int = 20, timeout: float = 15) -> pd.DataFrame:
    """Fetch news from Sina Finance (backup)."""
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".HK", "")
    prefix = "sh" if s.startswith("6") else "sz"
    _rate_limit()
    url = (
        f"https://vip.stock.finance.sina.com.cn/corp/go.php/"
        f"vCB_AllNewsStock/symbol/{prefix}{s}.phtml"
    )

    try:
        resp = requests.get(url, timeout=timeout)
        resp.encoding = "gbk"
        text = resp.text
        # Extract news items with simple regex
        pattern = re.compile(
            r"<a\s+href=['\"](.*?)['\"].*?target=['\"]_blank['\"]\s*>(.*?)</a>"
            r"\s*<span\s.*?>(.*?)</span>",
            re.DOTALL,
        )
        matches = pattern.findall(text)
        rows = []
        for href, title, date_str in matches[:limit]:
            title_clean = re.sub(r"<.*?>", "", title).strip()
            if title_clean:
                rows.append({
                    "title": title_clean,
                    "source": "sina",
                    "url": href.strip() if href else "",
                    "publish_time": pd.Timestamp(date_str.strip()) if date_str.strip() else None,
                    "summary": title_clean[:300],
                })
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Sina news failed for %s", symbol, exc_info=True)
        return pd.DataFrame()


# ── Hot stocks ─────────────────────────────────────────────────────────

def fetch_hot_stocks(limit: int = 20, timeout: float = 15) -> pd.DataFrame:
    """Fetch trending stocks from Eastmoney."""
    _rate_limit()
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1,
        "pz": min(limit, 50),
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21",
    }

    try:
        resp = _get_session("clist").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("diff", [])
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            rows.append({
                "symbol": it.get("f12", ""),
                "name": it.get("f14", ""),
                "price": _safe_float(it.get("f2"), 0.0),
                "change_pct": _safe_float(it.get("f3"), 0.0),
                "volume": int(_safe_float(it.get("f5"), 0)),
                "amount": _safe_float(it.get("f6"), 0.0),
                "pe": _safe_float(it.get("f9"), None),
                "pb": _safe_float(it.get("f23"), None),
                "market_cap": _safe_float(it.get("f20"), None),
            })
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Eastmoney hot stocks failed", exc_info=True)
        return pd.DataFrame()


# ── Northbound flow ────────────────────────────────────────────────────

def fetch_northbound_flow(days: int = 30, timeout: float = 15) -> pd.DataFrame:
    """Fetch northbound (北向) capital flow data."""
    _rate_limit()
    url = "https://push2.eastmoney.com/api/qt/kamt.kline/get"
    params = {
        "fields1": "f1,f2,f3,f4",
        "fields2": "f51,f52,f53,f54",
        "klt": 101,
        "lmt": min(days, 60),
        "secid": "90.BK0707",
        "ut": "5eea3edcaed942be9b67b66f9ecc9e5d",
    }

    try:
        resp = _get_session("kamt").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("data"):
            return pd.DataFrame()

        # The northbound data is split across hk2sh, sh2hk, hk2sz, sz2hk keys
        # Each value is a list of "date,net,balance1,balance2" strings
        # We aggregate net inflow across all four channels
        d = data["data"]
        all_rows = {}
        for channel in ("hk2sh", "sh2hk", "hk2sz", "sz2hk"):
            items = d.get(channel) or []
            for row_str in items:
                parts = row_str.split(",")
                if len(parts) < 2:
                    continue
                try:
                    dt = parts[0]
                    net = _safe_float(parts[1], 0.0)
                    if dt in all_rows:
                        all_rows[dt] += net
                    else:
                        all_rows[dt] = net
                except (ValueError, IndexError):
                    continue

        if not all_rows:
            return pd.DataFrame()

        rows = []
        balance = 0.0
        for dt in sorted(all_rows):
            net = all_rows[dt]
            balance += net
            rows.append({
                "date": dt,
                "net_inflow": net,
                "balance": balance,
            })
        return pd.DataFrame(rows)

    except Exception:
        logger.debug("Eastmoney northbound flow failed", exc_info=True)
        return pd.DataFrame()


# ── Dragon Tiger Board ─────────────────────────────────────────────────

def fetch_dragon_tiger(symbol: str, days: int = 30, timeout: float = 15) -> pd.DataFrame:
    """Fetch dragon tiger board (龙虎榜) data."""
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".HK", "")
    _rate_limit()
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    end = date.today().strftime("%Y%m%d")
    start = (date.today() - pd.Timedelta(days=days)).strftime("%Y%m%d")
    params = {
        "pn": 1,
        "pz": 100,
        "po": 0,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f1",
        "fs": f"m:0+t:6,search:{s}",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14",
        "st": start,
        "et": end,
    }

    try:
        resp = _get_session("clist").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            rows.append({
                "date": _parse_em_date(it.get("f13", "")),
                "symbol": it.get("f12", ""),
                "name": it.get("f14", ""),
                "reason": it.get("f8", ""),
                "buy_amount": _safe_float(it.get("f4"), 0.0) / 1e4,
                "sell_amount": _safe_float(it.get("f6"), 0.0) / 1e4,
                "net_amount": _safe_float(it.get("f10"), 0.0) / 1e4,
                "institution_buy": 0.0,
                "institution_sell": 0.0,
            })
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Eastmoney dragon tiger failed for %s", symbol, exc_info=True)
        return pd.DataFrame()


# ── Lockup Expiry ──────────────────────────────────────────────────────

def fetch_lockup_expiry(symbol: str, months: int = 6, timeout: float = 15) -> pd.DataFrame:
    """Fetch lockup expiry (限售解禁) data."""
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "")
    _rate_limit()
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    end = date.today().strftime("%Y-%m-%d")
    params = {
        "reportName": "RPT_LIFTED_OTHERTABLEDET",
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,LIMITED_UNLOCK_DATE,"
                   "UNLOCKED_SHARES,UNLOCKED_RATIO,ACTUAL_TRADING_FLOOR,"
                   "PLACING_MARKET_CAP",
        "quoteColumns": "",
        "filter": f'(SECURITY_CODE="{s}")(LIMITED_UNLOCK_DATE>"{end}")',
        "pageNumber": 1,
        "pageSize": 10,
        "sortTypes": 1,
        "sortColumns": "LIMITED_UNLOCK_DATE",
        "source": "WEB",
        "client": "WEB",
    }

    try:
        resp = _get_session("datacenter").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()
        items = (result.get("result") or {}).get("data") or []
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            rows.append({
                "symbol": it.get("SECURITY_CODE", s),
                "unlock_date": it.get("LIMITED_UNLOCK_DATE", ""),
                "unlock_shares": int(_safe_float(it.get("UNLOCKED_SHARES"), 0)),
                "unlock_ratio": _safe_float(it.get("UNLOCKED_RATIO"), 0.0),
                "unlock_market_value": _safe_float(it.get("PLACING_MARKET_CAP"), 0.0) / 1e4,
            })
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Eastmoney lockup expiry failed for %s", symbol, exc_info=True)
        return pd.DataFrame()


# ── Profit Forecast ────────────────────────────────────────────────────

def fetch_profit_forecast(symbol: str, timeout: float = 15) -> pd.DataFrame:
    """Fetch analyst profit forecast from Eastmoney."""
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "")
    _rate_limit()
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "reportName": "RPT_RESULT_FORECAST_MAIN",
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,FORECAST_YEAR,"
                   "FORECAST_EPS_AVG,FORECAST_NET_PROFIT_AVG,ANALYST_COUNT",
        "filter": f'(SECURITY_CODE="{s}")',
        "pageNumber": 1,
        "pageSize": 10,
        "sortTypes": -1,
        "sortColumns": "FORECAST_YEAR",
        "source": "WEB",
        "client": "WEB",
    }

    try:
        resp = _get_session("datacenter").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        items = (resp.json().get("result") or {}).get("data") or []
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            rows.append({
                "symbol": it.get("SECURITY_CODE", s),
                "year": int(_safe_float(it.get("FORECAST_YEAR"), 0)),
                "forecast_eps": _safe_float(it.get("FORECAST_EPS_AVG"), None),
                "forecast_net_profit": _safe_float(it.get("FORECAST_NET_PROFIT_AVG"), None),
                "analyst_count": int(_safe_float(it.get("ANALYST_COUNT"), 0)),
            })
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Eastmoney profit forecast failed for %s", symbol, exc_info=True)
        return pd.DataFrame()


# ── Insider Transactions ───────────────────────────────────────────────

def fetch_insider_transactions(symbol: str, timeout: float = 15) -> pd.DataFrame:
    """Fetch major shareholder / insider transactions."""
    s = symbol.strip().upper().replace(".SH", "").replace(".SZ", "")
    _rate_limit()
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "reportName": "RPT_SHAREHOLDERS_TRADE_DETAIL",
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,CHANGE_DATE,"
                   "SHAREHD_NAME,CHANGE_REASON,CHANGE_NUM,CHANGE_PROPORTION",
        "filter": f'(SECURITY_CODE="{s}")',
        "pageNumber": 1,
        "pageSize": 20,
        "sortTypes": -1,
        "sortColumns": "CHANGE_DATE",
        "source": "WEB",
        "client": "WEB",
    }

    try:
        resp = _get_session("datacenter").get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        items = (resp.json().get("result") or {}).get("data") or []
        if not items:
            return pd.DataFrame()
        rows = []
        for it in items:
            rows.append({
                "symbol": it.get("SECURITY_CODE", s),
                "date": it.get("CHANGE_DATE", ""),
                "shareholder": it.get("SHAREHD_NAME", ""),
                "reason": it.get("CHANGE_REASON", ""),
                "change_num": int(_safe_float(it.get("CHANGE_NUM"), 0)),
                "change_pct": _safe_float(it.get("CHANGE_PROPORTION"), 0.0),
            })
        return pd.DataFrame(rows)
    except Exception:
        logger.debug("Eastmoney insider txns failed for %s", symbol, exc_info=True)
        return pd.DataFrame()


# ── DataSource-compatible class ────────────────────────────────────────

class EastmoneySource:
    """HTTP-based Eastmoney source covering A-stock, HK, and partial US."""

    name = "eastmoney"

    def __init__(self, market: str = "a_stock"):
        self._market = market

    def _to_secid(self, symbol: str) -> str:
        if self._market == "hk_stock":
            return _hk_secid(symbol)
        if self._market == "us_stock":
            return _us_secid(symbol)
        return _a_secid(symbol)

    # K-line ------------------------------------------------------------

    def kline_daily(self, symbol: str, start_date: str = "", end_date: str = "",
                    adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(self._to_secid(symbol), "daily", 500, adjust)
        return _kline_df(rows, start_date, end_date)

    def kline_weekly(self, symbol: str, start_date: str = "", end_date: str = "",
                     adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(self._to_secid(symbol), "weekly", 300, adjust)
        return _kline_df(rows, start_date, end_date)

    def kline_monthly(self, symbol: str, start_date: str = "", end_date: str = "",
                      adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(self._to_secid(symbol), "monthly", 200, adjust)
        return _kline_df(rows, start_date, end_date)

    # HK-specific K-line entry point (akshare-compat)
    def hk_kline_daily(self, symbol: str, start_date: str = "", end_date: str = "",
                       adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(_hk_secid(symbol), "daily", 500, adjust)
        return _kline_df(rows, start_date, end_date)

    # US-specific K-line entry point
    def us_kline_daily(self, symbol: str, start_date: str = "", end_date: str = "",
                       adjust: str = "qfq") -> pd.DataFrame:
        rows = fetch_kline(_us_secid(symbol), "daily", 500, adjust)
        return _kline_df(rows, start_date, end_date)

    # Quote / Snapshot ---------------------------------------------------

    def quote(self, symbol: str) -> pd.DataFrame:
        return snapshot_to_df(fetch_snapshot(self._to_secid(symbol)))

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        return self.quote(symbol)

    # Fund flow ----------------------------------------------------------

    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame:
        df = fetch_fund_flow(self._to_secid(symbol), days)
        if not df.empty:
            df["symbol"] = symbol
        return df

    # News ---------------------------------------------------------------

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        df = fetch_news_eastmoney(symbol, limit)
        if df.empty:
            df = fetch_news_sina(symbol, limit)
        return df

    # A-stock special data -----------------------------------------------

    northbound_flow = staticmethod(fetch_northbound_flow)
    dragon_tiger_board = staticmethod(fetch_dragon_tiger)
    lockup_expiry = staticmethod(fetch_lockup_expiry)
    profit_forecast = staticmethod(fetch_profit_forecast)
    hot_stocks = staticmethod(fetch_hot_stocks)
    insider_transactions = staticmethod(fetch_insider_transactions)

    # Unsupported — fall through ----------------------------------------
    balance_sheet = lambda self, s: pd.DataFrame()
    income_statement = lambda self, s: pd.DataFrame()
    cash_flow = lambda self, s: pd.DataFrame()
    technical_indicators = lambda self, s, sd="", ed="": pd.DataFrame()


# ── helpers ────────────────────────────────────────────────────────────

def _safe_float(val, default=0.0):
    """Parse float, returning default on failure. Also handles NaN."""
    if val is None:
        return default
    try:
        v = float(val)
        return default if (v != v) else v  # NaN check
    except (ValueError, TypeError):
        return default


def _parse_em_date(val):
    """Parse Eastmoney date string (e.g., '2026-05-20T00:00:00' or '2026-05-20')."""
    try:
        s = str(val)[:10]
        return pd.Timestamp(s)
    except Exception:
        return None


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


def _us_secid(symbol: str) -> str:
    """US stock to Eastmoney secid. Tries both NASDAQ (105) and NYSE (106)."""
    s = symbol.strip().upper()
    # Eastmoney US codes: 105.AAPL, 106.BRK.A
    # Most tech stocks on NASDAQ, most others on NYSE
    nasdaq_dominant = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA",
                       "TSLA", "NFLX", "ADBE", "INTC", "AMD", "PYPL", "CSCO",
                       "CMCSA", "PEP", "COST", "AVGO", "TXN", "QCOM", "INTU",
                       "AMGN", "ISRG", "GILD", "BIIB", "REGN", "VRTX",
                       "ADI", "LRCX", "MU", "KLAC", "SNPS", "CDNS", "MRNA",
                       "ZM", "DOCU", "CRWD", "DDOG", "SNOW", "PLTR", "UBER",
                       "LYFT", "ABNB", "COIN", "RBLX", "HOOD", "DKNG",
                       "MRVL", "WDAY", "TEAM", "ZS", "NET", "OKTA",
                       "MDB", "SPLK", "PANW", "FTNT", "CHTR",
                       "SBUX", "PCAR", "EXC", "KHC", "MNST", "KDP",
                       "MELI", "JD", "PDD", "BIDU", "NTES", "BILI",
                       "FUTU", "TIGR", "NIO", "XPEV", "LI",
                       "LCID", "RIVN", "F", "GM", "TM", "HMC",
                       "WBD", "PARA", "WBA", "BBY", "GPS"}
    market = "105" if s in nasdaq_dominant else "106"
    return f"{market}.{s}"
