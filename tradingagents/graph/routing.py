"""Conditional edge routing logic for the LangGraph workflow.

Determines which node to visit next based on current state.
"""

from __future__ import annotations

from typing import Any, Literal

from tradingagents.config import get_settings


def should_continue_debate(state: dict[str, Any]) -> Literal["bull_researcher", "research_manager"]:
    """After a debate turn, decide whether to continue or move to the manager."""
    debate = state.get("investment_debate_state", {})
    current_count = debate.get("count", 0)
    max_rounds = get_settings().max_debate_rounds

    if current_count >= max_rounds * 2:  # *2 because each round = bull + bear
        return "research_manager"
    return "bull_researcher"


def next_debate_speaker(state: dict[str, Any]) -> Literal["bull_researcher", "bear_researcher"]:
    """Alternate between bull and bear based on round count."""
    debate = state.get("investment_debate_state", {})
    count = debate.get("count", 0)
    return "bull_researcher" if count % 2 == 0 else "bear_researcher"


def should_continue_risk_debate(state: dict[str, Any]) -> Literal["aggressive_risk", "conservative_risk", "portfolio_manager"]:
    """After a risk debate turn, decide next step."""
    risk = state.get("risk_debate_state", {})
    count = risk.get("count", 0)
    max_rounds = get_settings().max_risk_discuss_rounds

    if count >= max_rounds * 3:  # *3 because each round = aggressive + conservative + neutral
        return "portfolio_manager"

    # Rotate speakers: aggressive → conservative → neutral → aggressive → ...
    speakers = ["aggressive_risk", "conservative_risk", "neutral_risk"]
    return speakers[count % 3]
