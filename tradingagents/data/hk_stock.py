"""Hong Kong stock unified data interface.

Primary: akshare (eastmoney, works in China)
Secondary: efinance
Tertiary: yfinance (global, needs VPN)
"""

from __future__ import annotations

import pandas as pd

from tradingagents.data.retry import with_fallback
from tradingagents.data.sources.akshare import AkshareSource
from tradingagents.data.sources.efinance import EfinanceSource
from tradingagents.data.sources.yfinance import YFinanceSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

_akshare = AkshareSource()
_efinance = EfinanceSource()
_yfinance = YFinanceSource(market="hk_stock")


def get_kline_daily(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    return with_fallback(
        symbol, "kline_daily_hk",
        sources=[
            ("akshare", lambda **kw: _akshare.hk_kline_daily(**kw)),
            ("efinance", lambda **kw: _efinance.kline_daily(**kw)),
            ("yfinance", lambda **kw: _yfinance.kline_daily(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_quote(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "quote_hk",
        sources=[
            ("efinance", lambda **kw: _efinance.quote(**kw)),
            ("yfinance", lambda **kw: _yfinance.quote(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=1,
    )


def get_financial_summary(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "financial_summary_hk",
        sources=[
            ("efinance", lambda **kw: _efinance.financial_summary(**kw)),
            ("yfinance", lambda **kw: _yfinance.financial_summary(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=2,
    )


def get_balance_sheet(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "balance_sheet_hk",
        sources=[
            ("yfinance", lambda **kw: _yfinance.balance_sheet(**kw)),
        ],
        params={"symbol": symbol},
    )


def get_income_statement(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "income_statement_hk",
        sources=[
            ("yfinance", lambda **kw: _yfinance.income_statement(**kw)),
        ],
        params={"symbol": symbol},
    )


def get_cash_flow(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "cash_flow_hk",
        sources=[
            ("yfinance", lambda **kw: _yfinance.cash_flow(**kw)),
        ],
        params={"symbol": symbol},
    )
