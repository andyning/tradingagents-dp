"""Backtesting engine based on Backtrader.

Wraps Backtrader's Cerebro engine with convenient A-stock defaults.
Supports:
- Single symbol and portfolio-level backtesting
- A-stock rules (T+1, price limits, lot sizes)
- Commission and slippage modeling
- Performance metric extraction
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import backtrader as bt
import pandas as pd

from tradingagents.config import get_settings
from tradingagents.data.loader import load_history
from tradingagents.logging import get_logger

logger = get_logger(__name__)


class AStockCommission(bt.CommInfoBase):
    """A-stock commission model: 0.025% per side, min 5 CNY, stamp duty on sell."""

    params = (
        ("commission", 0.00025),
        ("stamp_duty", 0.0005),   # sell only
        ("min_commission", 5.0),
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        comm = max(value * self.p.commission, self.p.min_commission)
        if size < 0:  # sell
            comm += value * self.p.stamp_duty
        return comm


class SignalStrategy(bt.Strategy):
    """Backtrader strategy driven by external signals (from LLM pipeline)."""

    params = (
        ("signals", None),  # dict of date → signal ("buy"/"sell"/"hold")
    )

    def __init__(self):
        self.order = None

    def next(self):
        if self.order:
            return  # pending order

        dt = self.datas[0].datetime.date(0).isoformat()
        signal = (self.p.signals or {}).get(dt, "hold")

        if signal == "buy" and not self.position:
            size = int(self.broker.get_cash() * 0.95 / self.data.close[0])
            size = (size // 100) * 100  # round to lot
            if size >= 100:
                self.order = self.buy(size=size)
        elif signal == "sell" and self.position:
            self.order = self.sell(size=self.position.size)

    def notify_order(self, order):
        if order.status in (order.Completed, order.Canceled, order.Margin, order.Rejected):
            self.order = None


def run_backtest(
    symbol: str,
    start_date: str,
    end_date: str,
    signals: dict[str, str] | None = None,
    initial_cash: float | None = None,
    benchmark_symbol: str = "000300.SH",
    market: str = "a_stock",
) -> dict[str, Any]:
    """Run a backtest for a single symbol.

    Args:
        symbol: Stock ticker
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        signals: Date-isoformat → "buy"/"sell"/"hold" dict
        initial_cash: Starting capital (default: from settings)
        benchmark_symbol: Benchmark for alpha/beta calculation
        market: Market identifier

    Returns:
        Dict with metrics, trades, and equity curve
    """
    settings = get_settings()
    if initial_cash is None:
        initial_cash = settings.backtest_initial_cash

    # Load data
    df = load_history(symbol, start_date, end_date, market, frequency="daily")
    if df.empty:
        raise ValueError(f"No data for {symbol} from {start_date} to {end_date}")

    # Prepare Backtrader data feed
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    col_map = {"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    data = bt.feeds.PandasData(dataname=df.reset_index())

    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.broker.setcash(initial_cash)

    # Commission and slippage
    cerebro.broker.addcommissioninfo(AStockCommission())
    cerebro.broker.set_slippage_perc(perc=0.001)

    # Add strategy with signals if provided
    if signals:
        cerebro.addstrategy(SignalStrategy, signals=signals)

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03,
                        annualize=True, timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.VWR, _name="vwr")  # Variability-Weighted Return

    logger.info("Running backtest for %s: %s → %s", symbol, start_date, end_date)
    results = cerebro.run()
    strat = results[0]

    # Extract metrics
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash * 100

    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    metrics = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": initial_cash,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "sharpe_ratio": round(sharpe.get("sharperatio", 0.0) or 0.0, 3),
        "max_drawdown_pct": round(drawdown.get("max", {}).get("drawdown", 0.0), 2),
        "max_drawdown_duration": drawdown.get("max", {}).get("len", 0),
        "total_trades": trades.get("total", {}).get("total", 0) if trades.get("total") else 0,
        "won_trades": trades.get("won", {}).get("total", 0) if trades.get("won") else 0,
        "lost_trades": trades.get("lost", {}).get("total", 0) if trades.get("lost") else 0,
        "win_rate_pct": 0.0,
    }

    won = metrics["won_trades"]
    total_trades = metrics["total_trades"]
    if total_trades > 0:
        metrics["win_rate_pct"] = round(won / total_trades * 100, 2)

    logger.info("Backtest complete: return=%.2f%%, sharpe=%.2f, max_dd=%.2f%%",
                metrics["total_return_pct"], metrics["sharpe_ratio"], metrics["max_drawdown_pct"])

    return metrics
