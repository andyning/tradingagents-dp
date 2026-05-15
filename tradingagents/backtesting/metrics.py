"""Performance metrics for backtest evaluation.

Computes industry-standard measures:
- Sharpe Ratio (annualized)
- Sortino Ratio
- Maximum Drawdown
- CAGR (Compound Annual Growth Rate)
- Win Rate, Profit Factor
- Calmar Ratio
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(
    daily_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.03,
    trading_days: int = 252,
) -> dict[str, float]:
    """Compute a comprehensive set of performance metrics.

    Args:
        daily_returns: Daily portfolio returns (percentage, not decimal)
        benchmark_returns: Optional benchmark daily returns
        risk_free_rate: Annual risk-free rate (default 3% for China)
        trading_days: Trading days per year (approx 252 for A-stock)

    Returns:
        Dictionary of metric_name → value
    """
    if daily_returns.empty:
        return {}

    rets = daily_returns.dropna().values

    if len(rets) < 2:
        return {}

    total_return = float(np.prod(1 + rets / 100) - 1)
    mean_daily = float(np.mean(rets))
    std_daily = float(np.std(rets, ddof=1))
    ann_return = float(mean_daily * trading_days)
    ann_vol = float(std_daily * np.sqrt(trading_days))

    # Sharpe ratio
    excess = ann_return - risk_free_rate * 100  # risk_free in percentage
    sharpe = excess / ann_vol if ann_vol > 0 else 0.0

    # Sortino ratio (downside deviation)
    downside = rets[rets < 0]
    down_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    ann_down_std = float(down_std * np.sqrt(trading_days))
    sortino = excess / ann_down_std if ann_down_std > 0 else 0.0

    # Maximum drawdown
    cumulative = (1 + pd.Series(rets) / 100).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative / running_max - 1) * 100
    max_dd = float(drawdown.min())

    # CAGR
    n_years = len(rets) / trading_days
    cagr = float((1 + total_return) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0.0

    # Calmar ratio
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

    # Win rate and profit factor
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    win_rate = len(wins) / len(rets) * 100 if len(rets) > 0 else 0.0
    gross_profit = float(wins.sum()) if len(wins) > 0 else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Alpha & Beta (vs benchmark)
    alpha = 0.0
    beta = 0.0
    if benchmark_returns is not None and not benchmark_returns.empty:
        aligned = pd.concat([daily_returns, benchmark_returns], axis=1).dropna()
        if len(aligned) > 10:
            rets_aligned = aligned.iloc[:, 0]
            bench_aligned = aligned.iloc[:, 1]
            cov = np.cov(rets_aligned, bench_aligned)
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0.0
            alpha = ann_return - risk_free_rate * 100 - beta * (float(np.mean(bench_aligned)) * trading_days - risk_free_rate * 100)

    return {
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr, 2),
        "annual_volatility_pct": round(ann_vol, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "calmar_ratio": round(calmar, 2),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else float("inf"),
        "alpha_pct": round(alpha, 2),
        "beta": round(beta, 2),
        "n_trading_days": len(rets),
    }
