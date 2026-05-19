"""Hong Kong stock unified data interface.

HTTP-first fallback chain:
  Tencent HTTP → Eastmoney HTTP → Yahoo HTTP → Futu (local) → IB (local)
"""

from __future__ import annotations

import pandas as pd

from tradingagents.data.retry import with_fallback
from tradingagents.data.http.tencent import TencentSource
from tradingagents.data.http.eastmoney import EastmoneySource
from tradingagents.data.http.yahoo import YahooSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

_tencent = TencentSource(market="hk_stock")
_eastmoney = EastmoneySource(market="hk_stock")
_yahoo = YahooSource(market="hk_stock")

_futu = None
_ib = None


def _get_futu():
    global _futu
    if _futu is None:
        try:
            from tradingagents.data.sources.futu import FutuSource
            _futu = FutuSource(market="hk_stock")
        except Exception:
            _futu = False
    return _futu if _futu is not False else None


def _get_ib():
    global _ib
    if _ib is None:
        try:
            from tradingagents.data.sources.ib import IBSource
            _ib = IBSource(market="hk_stock")
        except Exception:
            _ib = False
    return _ib if _ib is not False else None


# ── K-line ─────────────────────────────────────────────────────────────

def get_kline_daily(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq",
) -> pd.DataFrame:
    sources = [
        ("tencent", lambda **kw: _tencent.kline_daily(**kw)),
        ("eastmoney", lambda **kw: _eastmoney.hk_kline_daily(**kw)),
        ("yahoo", lambda **kw: _yahoo.kline_daily(**kw)),
    ]
    futu = _get_futu()
    if futu:
        sources.append(("futu", lambda **kw: futu.kline_daily(**kw)))
    ib = _get_ib()
    if ib:
        sources.append(("ib", lambda **kw: ib.kline_daily(**kw), None))

    return with_fallback(
        symbol, "kline_daily_hk",
        sources=sources,
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


# ── Quote ──────────────────────────────────────────────────────────────

def get_quote(symbol: str) -> pd.DataFrame:
    sources = [
        ("tencent", lambda **kw: _tencent.quote(**kw)),
        ("eastmoney", lambda **kw: _eastmoney.quote(**kw)),
        ("yahoo", lambda **kw: _yahoo.quote(**kw)),
    ]
    futu = _get_futu()
    if futu:
        sources.append(("futu", lambda **kw: futu.quote(**kw)))

    return with_fallback(
        symbol, "quote_hk",
        sources=sources,
        params={"symbol": symbol},
        cache_ttl_hours=1,
    )


# ── Financial ──────────────────────────────────────────────────────────

def get_financial_summary(symbol: str) -> pd.DataFrame:
    sources = [
        ("eastmoney", lambda **kw: _eastmoney.financial_summary(**kw)),
        ("yahoo", lambda **kw: _yahoo.financial_summary(**kw)),
    ]
    futu = _get_futu()
    if futu:
        sources.append(("futu", lambda **kw: futu.financial_summary(**kw)))

    return with_fallback(
        symbol, "financial_summary_hk",
        sources=sources,
        params={"symbol": symbol},
        cache_ttl_hours=2,
    )


def get_balance_sheet(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "balance_sheet_hk",
        sources=[("yahoo", lambda **kw: _yahoo.balance_sheet(**kw))],
        params={"symbol": symbol},
    )


def get_income_statement(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "income_statement_hk",
        sources=[("yahoo", lambda **kw: _yahoo.income_statement(**kw))],
        params={"symbol": symbol},
    )


def get_cash_flow(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "cash_flow_hk",
        sources=[("yahoo", lambda **kw: _yahoo.cash_flow(**kw))],
        params={"symbol": symbol},
    )


# ── News ───────────────────────────────────────────────────────────────

def get_news(symbol: str, limit: int = 20) -> pd.DataFrame:
    sources = [
        ("eastmoney", lambda **kw: _eastmoney.news(**kw)),
        ("yahoo", lambda **kw: _yahoo.news(**kw)),
    ]
    ib = _get_ib()
    if ib:
        sources.append(("ib", lambda **kw: ib.news(**kw), None))

    return with_fallback(
        symbol, "news_hk",
        sources=sources,
        params={"symbol": symbol, "limit": limit},
        cache_ttl_hours=2,
    )
