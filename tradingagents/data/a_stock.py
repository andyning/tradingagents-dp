"""A-stock unified data interface.

HTTP-first fallback chain:
  Tencent HTTP → Eastmoney HTTP → Yahoo HTTP → Futu (local, last resort)

Baostock / efinance / akshare library dependencies removed.
"""

from __future__ import annotations

import pandas as pd

from tradingagents.data.retry import with_fallback
from tradingagents.data.http.tencent import TencentSource
from tradingagents.data.http.eastmoney import EastmoneySource
from tradingagents.data.http.yahoo import YahooSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

# ── Singleton source instances ─────────────────────────────────────────
_tencent = TencentSource(market="a_stock")
_eastmoney = EastmoneySource(market="a_stock")
_yahoo = YahooSource(market="a_stock")

# Futu — lazy import so users without OpenD still get full HTTP functionality
_futu = None


def _get_futu():
    global _futu
    if _futu is None:
        try:
            from tradingagents.data.sources.futu import FutuSource
            _futu = FutuSource(market="a_stock")
        except Exception:
            _futu = False
    return _futu if _futu is not False else None


# ── K-line ─────────────────────────────────────────────────────────────

def get_kline_daily(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq",
) -> pd.DataFrame:
    """Daily K-line: Tencent → Eastmoney → Yahoo → Futu."""
    sources = [
        ("tencent", lambda **kw: _tencent.kline_daily(**kw)),
        ("eastmoney", lambda **kw: _eastmoney.kline_daily(**kw)),
        ("yahoo", lambda **kw: _yahoo.kline_daily(**kw)),
    ]
    futu = _get_futu()
    if futu:
        sources.append(("futu", lambda **kw: futu.kline_daily(**kw)))

    return with_fallback(
        symbol, "kline_daily",
        sources=sources,
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_kline_weekly(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq",
) -> pd.DataFrame:
    """Weekly K-line: Tencent → Eastmoney → Yahoo."""
    return with_fallback(
        symbol, "kline_weekly",
        sources=[
            ("tencent", lambda **kw: _tencent.kline_weekly(**kw)),
            ("eastmoney", lambda **kw: _eastmoney.kline_weekly(**kw)),
            ("yahoo", lambda **kw: _yahoo.kline_weekly(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


def get_kline_monthly(
    symbol: str, start_date: str, end_date: str, adjust: str = "qfq",
) -> pd.DataFrame:
    """Monthly K-line: Tencent → Eastmoney → Yahoo."""
    return with_fallback(
        symbol, "kline_monthly",
        sources=[
            ("tencent", lambda **kw: _tencent.kline_monthly(**kw)),
            ("eastmoney", lambda **kw: _eastmoney.kline_monthly(**kw)),
            ("yahoo", lambda **kw: _yahoo.kline_monthly(**kw)),
        ],
        params={"symbol": symbol, "start_date": start_date, "end_date": end_date, "adjust": adjust},
    )


# ── Real-time Quote ────────────────────────────────────────────────────

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
        symbol, "quote",
        sources=sources,
        params={"symbol": symbol},
        cache_ttl_hours=1,
    )


# ── Financial Statements (simplified — mostly from quote) ──────────────

def get_financial_summary(symbol: str) -> pd.DataFrame:
    sources = [
        ("eastmoney", lambda **kw: _eastmoney.financial_summary(**kw)),
        ("yahoo", lambda **kw: _yahoo.financial_summary(**kw)),
    ]
    futu = _get_futu()
    if futu:
        sources.append(("futu", lambda **kw: futu.financial_summary(**kw)))

    return with_fallback(
        symbol, "financial_summary",
        sources=sources,
        params={"symbol": symbol},
        cache_ttl_hours=2,
    )


def get_balance_sheet(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "balance_sheet",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.balance_sheet(**kw)),
            ("yahoo", lambda **kw: _yahoo.balance_sheet(**kw)),
        ],
        params={"symbol": symbol},
    )


def get_income_statement(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "income_statement",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.income_statement(**kw)),
            ("yahoo", lambda **kw: _yahoo.income_statement(**kw)),
        ],
        params={"symbol": symbol},
    )


def get_cash_flow(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "cash_flow",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.cash_flow(**kw)),
            ("yahoo", lambda **kw: _yahoo.cash_flow(**kw)),
        ],
        params={"symbol": symbol},
    )


# ── Technical Indicators (computed locally from K-line) ────────────────

def get_technical_indicators(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = get_kline_daily(symbol, start_date, end_date)
    if df.empty:
        return pd.DataFrame()
    return _compute_indicators(df)


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MA, MACD, RSI, Bollinger Bands from K-line data."""
    df = df.sort_values("date").copy()
    close = df["close"].astype(float)
    high_series = df["high"].astype(float)
    low_series = df["low"].astype(float)

    for period in (5, 10, 20, 60):
        df[f"ma{period}"] = close.rolling(window=period).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi14"] = 100.0 - (100.0 / (1.0 + rs))

    df["boll_mid"] = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    df["boll_upper"] = df["boll_mid"] + 2 * std20
    df["boll_lower"] = df["boll_mid"] - 2 * std20

    df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=5).mean().replace(0, float("nan"))

    return df


# ── News ───────────────────────────────────────────────────────────────

def get_news(symbol: str, limit: int = 20) -> pd.DataFrame:
    return with_fallback(
        symbol, "news",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.news(**kw)),
        ],
        params={"symbol": symbol, "limit": limit},
        cache_ttl_hours=2,
    )


def get_global_news(limit: int = 20) -> pd.DataFrame:
    """Global / macro news via Yahoo RSS."""
    try:
        return _yahoo.news("", limit)
    except Exception:
        return pd.DataFrame()


# ── Capital Flow ───────────────────────────────────────────────────────

def get_fund_flow(symbol: str, days: int = 30) -> pd.DataFrame:
    sources = [
        ("eastmoney", lambda **kw: _eastmoney.fund_flow(**kw)),
    ]
    futu = _get_futu()
    if futu:
        sources.append(("futu", lambda **kw: futu.fund_flow(**kw)))

    return with_fallback(
        symbol, "fund_flow",
        sources=sources,
        params={"symbol": symbol, "days": days},
        cache_ttl_hours=4,
    )


def get_northbound_flow(days: int = 30) -> pd.DataFrame:
    return with_fallback(
        "northbound", "northbound_flow",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.northbound_flow(**kw)),
        ],
        params={"days": days},
        cache_ttl_hours=4,
    )


# ── A-stock Special Data ──────────────────────────────────────────────

def get_dragon_tiger_board(symbol: str, days: int = 30) -> pd.DataFrame:
    return with_fallback(
        symbol, "dragon_tiger_board",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.dragon_tiger_board(**kw)),
        ],
        params={"symbol": symbol, "days": days},
        cache_ttl_hours=4,
    )


def get_lockup_expiry(symbol: str, months: int = 6) -> pd.DataFrame:
    return with_fallback(
        symbol, "lockup_expiry",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.lockup_expiry(**kw)),
        ],
        params={"symbol": symbol, "months": months},
        cache_ttl_hours=24,
    )


def get_hot_stocks(limit: int = 20) -> pd.DataFrame:
    return with_fallback(
        "market", "hot_stocks",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.hot_stocks(**kw)),
        ],
        params={"limit": limit},
        cache_ttl_hours=2,
    )


def get_concept_blocks() -> pd.DataFrame:
    return pd.DataFrame()  # TODO


def get_profit_forecast(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "profit_forecast",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.profit_forecast(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=24,
    )


def get_industry_comparison(symbol: str) -> pd.DataFrame:
    return pd.DataFrame()  # TODO


def get_insider_transactions(symbol: str) -> pd.DataFrame:
    return with_fallback(
        symbol, "insider_transactions",
        sources=[
            ("eastmoney", lambda **kw: _eastmoney.insider_transactions(**kw)),
        ],
        params={"symbol": symbol},
        cache_ttl_hours=24,
    )
