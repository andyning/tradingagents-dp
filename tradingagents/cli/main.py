"""CLI entry point — Typer + Rich interactive terminal interface."""

from __future__ import annotations

import sys
from datetime import date, datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tradingagents.config import get_settings
from tradingagents.graph import TradingAgentsGraph
from tradingagents.logging import setup_logging

app = typer.Typer(
    name="tradingagents",
    help="Multi-agent A-share investment analysis CLI",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    symbol: str = typer.Option(..., "-s", "--symbol", help="Stock ticker (e.g. 600519)"),
    date: str = typer.Option(
        datetime.now().strftime("%Y-%m-%d"), "-d", "--date", help="Analysis date YYYY-MM-DD"
    ),
    market: str = typer.Option("a_stock", "-m", "--market", help="Market: a_stock, hk_stock, us_stock"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output"),
):
    """Run the full multi-agent analysis pipeline for a stock."""
    setup_logging()

    console.print(Panel.fit(
        f"[bold]TradingAgents[/bold] — Multi-Agent Investment Analysis\n"
        f"Symbol: {symbol} | Date: {date} | Market: {market}",
        border_style="blue",
    ))

    settings = get_settings()
    if not settings.llm_api_key:
        console.print("[red]Error:[/] No API key set. Set DEEPSEEK_API_KEY in .env")
        raise typer.Exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running analysis pipeline...", total=None)

            graph = TradingAgentsGraph(debug=debug)
            state, decision, _ = graph.propagate(symbol, date, market=market)

            progress.remove_task(task)

        # Extract rating
        rating = "Unknown"
        for r in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
            if r.lower() in decision.lower():
                rating = r
                break

        # Rating display
        color = {"Buy": "green", "Overweight": "bright_green", "Hold": "yellow",
                 "Underweight": "orange1", "Sell": "red"}.get(rating, "white")

        console.print()
        console.print(Panel(f"[bold {color}]{rating}[/bold {color}]", title="Final Decision"))
        console.print()

        # Reports
        reports = {
            "Market / Technical": state.get("market_report", ""),
            "Social Sentiment": state.get("sentiment_report", ""),
            "News & Macro": state.get("news_report", ""),
            "Fundamentals": state.get("fundamentals_report", ""),
            "Policy": state.get("policy_report", ""),
            "Hot Money / Flow": state.get("hot_money_report", ""),
            "Lockup / Insider": state.get("lockup_report", ""),
            "Investment Plan": state.get("investment_plan", ""),
            "Trader Proposal": state.get("trader_investment_plan", ""),
        }

        for title, content in reports.items():
            if content:
                console.print(Panel(content[:2000], title=title))

    except Exception as exc:
        console.print(f"[red]Error:[/] {exc}")
        if debug:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("TradingAgents-dp v0.3.0")


def main():
    app()


if __name__ == "__main__":
    main()
