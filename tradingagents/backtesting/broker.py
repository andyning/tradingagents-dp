"""A-stock trading rule simulator for backtesting.

Models A-share specific constraints:
- T+1 settlement (can't sell shares bought today)
- Price limits (main board ±10%, STAR/ChiNext ±20%, ST ±5%)
- Minimum lot size (100 shares for main board, 200 for STAR)
- Stamp duty (0.05% sell only), commission (0.025% both sides)
- No short selling for most stocks
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional


class BoardType(str, Enum):
    MAIN = "main"         # 主板: 60xxxx, 00xxxx
    CHINEXT = "chinext"   # 创业板: 30xxxx
    STAR = "star"         # 科创板: 688xxx, 689xxx
    ST = "st"             # ST / *ST stocks


def classify_board(symbol: str) -> BoardType:
    """Classify A-stock symbol into board type based on prefix."""
    code = symbol.strip().upper().replace("SH.", "").replace("SZ.", "").replace(".SH", "").replace(".SZ", "").replace(".SS", "")
    if code.startswith("688") or code.startswith("689"):
        return BoardType.STAR
    if code.startswith("300") or code.startswith("301"):
        return BoardType.CHINEXT
    if code.startswith("60") or code.startswith("00"):
        return BoardType.MAIN
    return BoardType.MAIN


def price_limit(symbol: str) -> float:
    """Return the daily price limit ratio for a given A-stock."""
    board = classify_board(symbol)
    if board == BoardType.STAR or board == BoardType.CHINEXT:
        return 0.20
    if board == BoardType.ST:
        return 0.05
    return 0.10


def min_lot_size(symbol: str) -> int:
    """Minimum shares per order (1手) for a given A-stock."""
    board = classify_board(symbol)
    return 200 if board == BoardType.STAR else 100


def commission_rate() -> float:
    """Standard brokerage commission rate (per side)."""
    return 0.00025  # 万2.5


def stamp_duty_rate() -> float:
    """Stamp duty — A-share charges on sell side only."""
    return 0.0005  # 万5


def apply_price_limit(price: float, symbol: str, pre_close: float, is_buy: bool) -> float:
    """Clamp an order price to the daily price limit range.

    For buy orders, the price cannot exceed pre_close * (1 + limit).
    For sell orders, the price cannot be below pre_close * (1 - limit).
    """
    limit = price_limit(symbol)
    if is_buy:
        return min(price, pre_close * (1 + limit))
    else:
        return max(price, pre_close * (1 - limit))


def transaction_cost(trade_value: float, is_sell: bool) -> float:
    """Calculate total transaction cost for a trade.

    Args:
        trade_value: total trade amount (price * shares)
        is_sell: True if selling, False if buying
    """
    commission = trade_value * commission_rate()
    # Minimum commission of 5 CNY
    commission = max(commission, 5.0)
    stamp = trade_value * stamp_duty_rate() if is_sell else 0.0
    return commission + stamp


class Position:
    """Tracks a single stock position with T+1 constraint."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.shares: int = 0
        self.avg_cost: float = 0.0
        self.today_bought: int = 0  # Shares bought today (can't be sold due to T+1)

    @property
    def market_value(self) -> float:
        return self.shares * self.avg_cost

    def can_sell(self, shares: int) -> bool:
        """Check if enough available shares (not locked by T+1) to sell."""
        available = self.shares - self.today_bought
        return available >= shares

    def buy(self, shares: int, price: float) -> None:
        total_cost = self.market_value + shares * price
        self.shares += shares
        self.avg_cost = total_cost / self.shares if self.shares > 0 else 0.0
        self.today_bought += shares

    def sell(self, shares: int, price: float) -> float:
        """Sell shares and return proceeds after costs."""
        if not self.can_sell(shares):
            raise ValueError(
                f"T+1 constraint: cannot sell {shares} shares of {self.symbol} "
                f"(holding {self.shares}, {self.today_bought} bought today)"
            )
        proceeds = shares * price
        cost = transaction_cost(proceeds, is_sell=True)
        self.shares -= shares
        self.avg_cost = self.avg_cost if self.shares == 0 else self.avg_cost  # keep avg_cost stable on partial sales
        return proceeds - cost

    def end_of_day(self) -> None:
        """Reset T+1 lock at end of day."""
        self.today_bought = 0
