"""Top-level TradingAgentsGraph — the public API for running the pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

import yfinance as yf

from tradingagents.config import get_settings
from tradingagents.graph.builder import build_graph
from tradingagents.graph.state import AgentState
from tradingagents.logging import get_logger

logger = get_logger(__name__)


def _safe_ticker(ticker: str) -> str:
    """Sanitize ticker for use in file paths."""
    return ticker.strip().replace("/", "_").replace("\\", "_").replace("..", "")


class TradingAgentsGraph:
    """Main orchestrator for the multi-agent trading analysis pipeline."""

    def __init__(self, debug: bool = False, config: dict[str, Any] | None = None):
        self.debug = debug

        # Apply any runtime config overrides
        if config:
            import os
            for key, value in config.items():
                os.environ[f"TA_{key.upper()}"] = str(value)

        settings = get_settings()
        self.settings = settings

        # Ensure directories
        settings.results_dir.mkdir(parents=True, exist_ok=True)
        settings.data_cache_dir.mkdir(parents=True, exist_ok=True)

        # Build the graph (default medium, overridden in propagate)
        self.graph = build_graph(depth="medium")
        self._current_depth = "medium"
        logger.info("TradingAgentsGraph initialized")

    def propagate(
        self,
        ticker: str,
        trade_date: str,
        market: str = "a_stock",
        depth: str = "medium",
        data_window: int = 120,
        selected_analysts: list[str] | None = None,
        past_context: str = "",
    ) -> tuple[dict[str, Any], str]:
        """Run the full analysis pipeline.

        Args:
            ticker: Stock symbol (e.g. "600519")
            trade_date: Analysis date YYYY-MM-DD
            market: Market identifier: "a_stock", "hk_stock", "us_stock"
            depth: Analysis depth: "light" (5 steps), "medium" (13 steps), "deep" (16 steps)
            selected_analysts: Which analysts to run (default: all 7)
            past_context: Prior decisions/reflections for this ticker

        Returns:
            (final_state, decision_string) tuple
        """
        if selected_analysts is None:
            selected_analysts = ["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]

        init_state: AgentState = {
            "company_of_interest": ticker,
            "trade_date": trade_date,
            "market": market,
            "data_window": data_window,
            "messages": [],
            "sender": "",
            "market_report": "",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
            "policy_report": "",
            "hot_money_report": "",
            "lockup_report": "",
            "data_quality_summary": "",
            "investment_debate_state": {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "judge_decision": "",
                "count": 0,
            },
            "investment_plan": "",
            "trader_investment_plan": "",
            "risk_debate_state": {
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "history": "",
                "latest_speaker": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 0,
            },
            "final_trade_decision": "",
            "past_context": past_context,
            "selected_analysts": selected_analysts,
        }

        # Rebuild graph if depth changed
        if depth != self._current_depth:
            self.graph = build_graph(depth=depth)
            self._current_depth = depth

        # Reset progress for this depth
        from tradingagents.graph.progress import reset_progress
        reset_progress(depth)

        logger.info("Starting pipeline for %s on %s (market=%s, depth=%s)", ticker, trade_date, market, depth)

        if self.debug:
            final_state = None
            for chunk in self.graph.stream(init_state):
                for node_name, node_output in chunk.items():
                    sender = node_output.get("sender", node_name)
                    logger.debug("Node completed: %s", sender)
                final_state = chunk
            # Get the last chunk's full state
            final_state = self.graph.invoke(init_state)
        else:
            final_state = self.graph.invoke(init_state)

        decision = final_state.get("final_trade_decision", "")
        self._save_result(ticker, trade_date, depth, market, final_state)

        logger.info("Pipeline complete for %s: decision=%s",
                     ticker, self._extract_rating(decision))
        return final_state, decision

    @staticmethod
    def _extract_rating(decision: str) -> str:
        """Extract the rating from the decision text."""
        for rating in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
            if rating.lower() in decision.lower():
                return rating
        return "Unknown"

    def _save_result(self, ticker: str, trade_date: str, depth: str, market: str, state: dict[str, Any]) -> None:
        """Persist the final state to disk as JSON, plus a latest_{depth}.json cache."""
        safe = _safe_ticker(ticker)
        directory = self.settings.results_dir / safe / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        saved = {
            "company_of_interest": state.get("company_of_interest", ""),
            "trade_date": state.get("trade_date", ""),
            "market": market,
            "depth": depth,
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "policy_report": state.get("policy_report", ""),
            "hot_money_report": state.get("hot_money_report", ""),
            "lockup_report": state.get("lockup_report", ""),
            "data_quality_summary": state.get("data_quality_summary", ""),
            "investment_debate_state": state.get("investment_debate_state", {}),
            "trader_investment_plan": state.get("trader_investment_plan", ""),
            "risk_debate_state": state.get("risk_debate_state", {}),
            "investment_plan": state.get("investment_plan", ""),
            "final_trade_decision": state.get("final_trade_decision", ""),
            "saved_at": datetime.now().isoformat(),
        }

        # Date-stamped log
        path = directory / f"full_states_log_{trade_date}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(saved, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Result saved to %s", path)

        # Latest cache per depth (for quick dashboard reload)
        cache_path = directory / f"latest_{depth}.json"
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(saved, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Cache updated: %s", cache_path)
