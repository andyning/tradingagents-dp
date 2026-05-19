"""US stock unified data interface.

Primary: akshare (eastmoney, works in China without VPN)
Secondary: efinance (fallback)
Tertiary: yfinance (last resort, often blocked in China)
"""

from __future__ import annotations

import pandas as pd

from tradingagents.data.retry import with_fallback
from tradingagents.data.sources.akshare import AkshareSource
from tradingagents.data.sources.efinance import EfinanceSource
from tradingagents.data.sources.futu import FutuSource
from tradingagents.data.sources.ib import IBSource
from tradingagents.data.sources.yfinance import YFinanceSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

_ib = IBSource(market="us_stock")
_futu = FutuSource(market="us_stock")
_akshare = AkshareSource()
_efinance = EfinanceSource()
_yfinance = YFinanceSource(market="us_stock")


def get_kline_daily(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    return with_fallback(
        symbol, "kline_daily_us",
        sources=[
            ("ib", lambda **kw: _ib.kline_daily(**kw), None),  # IB has its own timeouts
            ("futu", lambda **kw: _futu.kline_daily(**kw)),
            ("akshare", lambda **kw: _akshare.us_kline_daily(**kw)),
            ("efinance", lambda **kw: _efinance.kline_daily(**kw)),
            ("yfinance", lambda **kw: _yfinance.kline_daily(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_kline_weekly(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    return with_fallback(
        symbol, "kline_weekly_us",
        sources=[
            ("akshare", lambda **kw: _akshare.us_kline_daily(**kw)),
            ("yfinance", lambda **kw: _yfinance.kline_weekly(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_kline_monthly(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    return with_fallback(
        symbol, "kline_monthly_us",
        sources=[
            ("yfinance", lambda **kw: _yfinance.kline_monthly(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_quote(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "quote_us",
        sources=[
            ("efinance", lambda **kw: _efinance.quote(**kw)),
            ("yfinance", lambda **kw: _yfinance.quote(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=1,
    )


def get_financial_summary(symbol: str) -> pd.DataFrame:
    # US financial summary is handled by Futu snapshot in data_context
    # yfinance is blocked in China — skip to avoid 36s timeout
    return pd.DataFrame()


def get_balance_sheet(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "balance_sheet_us",
        sources=[("yfinance", lambda **kw: _yfinance.balance_sheet(**kw))],
        params={"symbol": symbol},
    )


def get_income_statement(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "income_statement_us",
        sources=[("yfinance", lambda **kw: _yfinance.income_statement(**kw))],
        params={"symbol": symbol},
    )


def get_cash_flow(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "cash_flow_us",
        sources=[("yfinance", lambda **kw: _yfinance.cash_flow(**kw))],
        params={"symbol": symbol},
    )


def get_news(symbol: str, limit: int = 20) -> pd.DataFrame:
    """News for US stocks via IB (Dow Jones) → yfinance."""
    return with_fallback(
        symbol, "news_us",
        sources=[
            ("ib", lambda **kw: _ib.news(**kw)),
            ("yfinance", lambda **kw: _yfinance.news(**kw)),
        ],
        params={"symbol": symbol, "limit": limit},
        cache_ttl_hours=2,
    )


def get_insider_transactions(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "insider_transactions_us",
        sources=[("yfinance", lambda **kw: _yfinance.insider_transactions(**kw))],
        params={"symbol": symbol},
        cache_ttl_hours=24,
    )
