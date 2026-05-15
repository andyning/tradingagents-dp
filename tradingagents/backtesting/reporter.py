"""Backtest report generator.

Produces markdown and HTML reports from backtesting results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_report(metrics: dict[str, Any], output_path: str | Path | None = None) -> str:
    """Generate a markdown-formatted backtest report.

    Args:
        metrics: Metric dict from engine.run_backtest()
        output_path: Optional path to save the report

    Returns:
        Markdown report string
    """
    md = _render_markdown(metrics)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md, encoding="utf-8")

    return md


def _render_markdown(metrics: dict[str, Any]) -> str:
    """Render metrics dict to markdown."""
    lines = [
        f"# Backtest Report: {metrics.get('symbol', 'N/A')}",
        "",
        f"**Period**: {metrics.get('start_date', '')} → {metrics.get('end_date', '')}",
        "",
        "## Performance Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Initial Capital | ¥{metrics.get('initial_cash', 0):,.0f} |",
        f"| Final Value | ¥{metrics.get('final_value', 0):,.2f} |",
        f"| Total Return | {metrics.get('total_return_pct', 0)}% |",
        f"| Sharpe Ratio | {metrics.get('sharpe_ratio', 0)} |",
        f"| Max Drawdown | {metrics.get('max_drawdown_pct', 0)}% |",
        f"| Max DD Duration | {metrics.get('max_drawdown_duration', 0)} days |",
        "",
        "## Trade Statistics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Trades | {metrics.get('total_trades', 0)} |",
        f"| Win Rate | {metrics.get('win_rate_pct', 0)}% |",
        f"| Won | {metrics.get('won_trades', 0)} |",
        f"| Lost | {metrics.get('lost_trades', 0)} |",
    ]

    return "\n".join(lines)
