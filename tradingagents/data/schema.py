"""Pydantic data schemas for all financial data types.

Every data source must return data conforming to these schemas.
Validation failure triggers fallback to the next data source.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---- K-line (OHLCV) ----

class KLineRow(BaseModel):
    """Single daily or minute K-line bar."""

    date: date
    open: float = Field(ge=0)
    low: float = Field(ge=0)
    high: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: int = Field(ge=0)
    amount: float = Field(ge=0)  # Trading amount in yuan (A-stock) or base currency

    @field_validator("high")
    @classmethod
    def high_ge_low(cls, v: float, info) -> float:
        if v < info.data["low"]:
            raise ValueError(f"high ({v}) must be >= low ({info.data['low']})")
        return v


class KLineData(BaseModel):
    """A collection of K-line rows."""

    symbol: str
    market: str  # "a_stock", "hk_stock", "us_stock"
    frequency: str = "daily"  # "daily", "weekly", "monthly"
    rows: list[KLineRow] = Field(default_factory=list, min_length=1)


# ---- Real-time Quote ----

class Quote(BaseModel):
    """Real-time or latest price quote."""

    symbol: str
    name: str = ""
    price: float
    change_pct: float = 0.0
    volume: int = 0
    amount: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    pre_close: float = 0.0
    turnover: float = 0.0  # Turnover rate (%)
    pe: Optional[float] = None
    pb: Optional[float] = None
    market_cap: Optional[float] = None  # Total market cap in 100M
    timestamp: datetime = Field(default_factory=datetime.now)


# ---- Financial Statements ----

class BalanceSheet(BaseModel):
    symbol: str
    report_date: date
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None


class IncomeStatement(BaseModel):
    symbol: str
    report_date: date
    revenue: Optional[float] = None
    operating_profit: Optional[float] = None
    net_profit: Optional[float] = None
    eps: Optional[float] = None


class CashFlowStatement(BaseModel):
    symbol: str
    report_date: date
    operating_cf: Optional[float] = None
    investing_cf: Optional[float] = None
    financing_cf: Optional[float] = None


class FinancialSummary(BaseModel):
    """Combined key financial metrics."""

    symbol: str
    report_date: date
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_ratio: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    revenue_yoy: Optional[float] = None
    profit_yoy: Optional[float] = None
    market_cap: Optional[float] = None


# ---- News & Sentiment ----

class NewsItem(BaseModel):
    title: str
    source: str = ""
    url: str = ""
    publish_time: Optional[datetime] = None
    summary: str = ""


# ---- Capital Flow ----

class FundFlowItem(BaseModel):
    date: date
    symbol: str
    main_inflow: float = 0.0  # Main force net inflow (10k yuan)
    main_inflow_pct: float = 0.0  # Main force inflow ratio (%)
    super_large_inflow: float = 0.0
    large_inflow: float = 0.0
    medium_inflow: float = 0.0
    small_inflow: float = 0.0


# ---- Dragon Tiger Board ----

class DragonTigerItem(BaseModel):
    date: date
    symbol: str
    name: str = ""
    reason: str = ""  # Reason for appearing on the board
    buy_amount: float = 0.0
    sell_amount: float = 0.0
    net_amount: float = 0.0
    institution_buy: float = 0.0
    institution_sell: float = 0.0


# ---- Lockup Expiry ----

class LockupExpiryItem(BaseModel):
    symbol: str
    unlock_date: date
    unlock_shares: int = 0  # Number of shares unlocking
    unlock_ratio: float = 0.0  # % of total shares
    unlock_market_value: float = 0.0  # Market value of unlocking shares (10k)


# ---- Northbound Flow ----

class NorthboundFlow(BaseModel):
    date: date
    net_inflow: float = 0.0  # Net northbound inflow (100M yuan)
    balance: float = 0.0  # Cumulative balance


# ---- Industry Comparison ----

class IndustryComparison(BaseModel):
    symbol: str
    industry: str = ""
    peer_count: int = 0
    pe_percentile: Optional[float] = None
    pb_percentile: Optional[float] = None
    roe_percentile: Optional[float] = None
    revenue_rank: Optional[int] = None
    profit_rank: Optional[int] = None


# ---- Profit Forecast ----

class ProfitForecast(BaseModel):
    symbol: str
    year: int
    forecast_eps: Optional[float] = None
    forecast_net_profit: Optional[float] = None
    analyst_count: int = 0


# ---- Indicator ----

class TechnicalIndicator(BaseModel):
    symbol: str
    date: date
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    rsi14: Optional[float] = None
    boll_upper: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_lower: Optional[float] = None
    volume_ratio: Optional[float] = None
