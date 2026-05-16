"""A-stock unified data interface.

Composes Baostock (primary), efinance (secondary), akshare (special),
and yfinance (last-resort fallback) through the fallback chain.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tradingagents.data.retry import with_fallback
from tradingagents.data.sources.baostock import BaostockSource
from tradingagents.data.sources.efinance import EfinanceSource
from tradingagents.data.sources.akshare import AkshareSource
from tradingagents.data.sources.futu import FutuSource
from tradingagents.data.sources.ib import IBSource
from tradingagents.data.sources.yfinance import YFinanceSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

# Singleton source instances
_ib = IBSource(market="a_stock")
_futu = FutuSource(market="a_stock")
_baostock = BaostockSource()
_efinance = EfinanceSource()
_akshare = AkshareSource()
_yfinance = YFinanceSource(market="a_stock")


# ---- K-line ----

def get_kline_daily(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    """Daily K-line with Baostock → efinance → yfinance fallback."""
    return with_fallback(
        symbol, "kline_daily",
        sources=[
            ("futu", lambda **kw: _futu.kline_daily(**kw)),
            ("baostock", lambda **kw: _baostock.kline_daily(**kw)),
            ("efinance", lambda **kw: _efinance.kline_daily(**kw)),
            ("yfinance", lambda **kw: _yfinance.kline_daily(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_kline_weekly(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    return with_fallback(
        symbol, "kline_weekly",
        sources=[
            ("baostock", lambda **kw: _baostock.kline_weekly(**kw)),
            ("efinance", lambda **kw: _efinance.kline_weekly(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_kline_monthly(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    return with_fallback(
        symbol, "kline_monthly",
        sources=[
            ("baostock", lambda **kw: _baostock.kline_monthly(**kw)),
            ("efinance", lambda **kw: _efinance.kline_monthly(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


# ---- Real-time Quote ----

def get_quote(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "quote",
        sources=[
            ("efinance", lambda **kw: _efinance.quote(**kw)),
            ("baostock", lambda **kw: _baostock.quote(**kw)),
            ("yfinance", lambda **kw: _yfinance.quote(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=1,
    )


# ---- Financial Statements ----

def get_balance_sheet(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "balance_sheet",
        sources=[
            ("baostock", lambda **kw: _baostock.balance_sheet(**kw)),
            ("yfinance", lambda **kw: _yfinance.balance_sheet(**kw)),
        ],
        params={"symbol": symbol},
    )


def get_income_statement(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "income_statement",
        sources=[
            ("baostock", lambda **kw: _baostock.income_statement(**kw)),
            ("yfinance", lambda **kw: _yfinance.income_statement(**kw)),
        ],
        params={"symbol": symbol},
    )


def get_cash_flow(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "cash_flow",
        sources=[
            ("baostock", lambda **kw: _baostock.cash_flow(**kw)),
            ("yfinance", lambda **kw: _yfinance.cash_flow(**kw)),
        ],
        params={"symbol": symbol},
    )


def get_financial_summary(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "financial_summary",
        sources=[
            ("efinance", lambda **kw: _efinance.financial_summary(**kw)),
            ("baostock", lambda **kw: _baostock.financial_summary(**kw)),
            ("yfinance", lambda **kw: _yfinance.financial_summary(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=2,
    )


# ---- Technical Indicators ----

def get_technical_indicators(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Compute technical indicators from daily K-line data."""
    # All sources return empty for indicators; we compute locally from K-line
    df = get_kline_daily(symbol, start_date, end_date)
    if df.empty:
        return pd.DataFrame()
    return _compute_indicators(df)


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MA, MACD, RSI, Bollinger Bands from K-line data."""
    df = df.sort_values("date").copy()
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # Moving averages
    for period in (5, 10, 20, 60):
        df[f"ma{period}"] = close.rolling(window=period).mean()

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi14"] = 100.0 - (100.0 / (1.0 + rs))

    # Bollinger Bands (20)
    df["boll_mid"] = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    df["boll_upper"] = df["boll_mid"] + 2 * std20
    df["boll_lower"] = df["boll_mid"] - 2 * std20

    # Volume ratio
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=5).mean().replace(0, float("nan"))

    return df


# ---- News ----

def get_news(symbol: str, limit: int = 20) -> pd.DataFrame:
    return with_fallback(
        symbol, "news",
        sources=[
            ("yfinance", lambda **kw: _yfinance.news(**kw)),
        ],
        params={"symbol": symbol, "limit": limit},
        cache_ttl_hours=2,
    )


def get_global_news(limit: int = 20) -> pd.DataFrame:
    """Global / macro news (no symbol filter)."""
    # Use yfinance to get market news
    try:
        import yfinance as yf
        news = yf.Search("market news").news[:limit]
        if not news:
            return pd.DataFrame()
        rows = [{"title": n.get("title", ""), "source": n.get("publisher", ""),
                 "url": n.get("link", ""), "summary": n.get("summary", "")} for n in news]
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


# ---- Capital Flow ----

def get_fund_flow(symbol: str, days: int = 30) -> pd.DataFrame:
    return with_fallback(
        symbol, "fund_flow",
        sources=[
            ("efinance", lambda **kw: _efinance.fund_flow(**kw)),
            ("akshare", lambda **kw: _akshare.fund_flow(**kw)),
        ],
        params={"symbol": symbol, "days": days},
        cache_ttl_hours=4,
    )


def get_northbound_flow(days: int = 30) -> pd.DataFrame:
    return with_fallback(
        "northbound", "northbound_flow",
        sources=[
            ("akshare", lambda **kw: _akshare.northbound_flow(**kw)),
        ],
        params={"days": days},
        cache_ttl_hours=4,
    )


# ---- A-stock Special Data ----

def get_dragon_tiger_board(symbol: str, days: int = 30) -> pd.DataFrame:
    return with_fallback(
        symbol, "dragon_tiger_board",
        sources=[
            ("akshare", lambda **kw: _akshare.dragon_tiger_board(**kw)),
        ],
        params={"symbol": symbol, "days": days},
        cache_ttl_hours=4,
    )


def get_lockup_expiry(symbol: str, months: int = 6) -> pd.DataFrame:
    return with_fallback(
        symbol, "lockup_expiry",
        sources=[
            ("akshare", lambda **kw: _akshare.lockup_expiry(**kw)),
        ],
        params={"symbol": symbol, "months": months},
        cache_ttl_hours=24,
    )


def get_hot_stocks(limit: int = 20) -> pd.DataFrame:
    return with_fallback(
        "market", "hot_stocks",
        sources=[
            ("akshare", lambda **kw: _akshare.hot_stocks(**kw)),
        ],
        params={"limit": limit},
        cache_ttl_hours=2,
    )


def get_concept_blocks() -> pd.DataFrame:
    return pd.DataFrame()  # TODO: implement when source available


def get_profit_forecast(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "profit_forecast",
        sources=[
            ("akshare", lambda **kw: _akshare.profit_forecast(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=24,
    )


def get_industry_comparison(symbol: str) -> pd.DataFrame:
    return pd.DataFrame()  # TODO: implement when source available


def get_insider_transactions(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "insider_transactions",
        sources=[
            ("akshare", lambda **kw: _akshare.insider_transactions(**kw)),
            ("yfinance", lambda **kw: _yfinance.insider_transactions(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=24,
    )
