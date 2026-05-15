"""LangGraph AgentState definitions.

Defines the state shape that flows through the graph.
Uses TypedDict for LangGraph compatibility.
"""

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class InvestDebateState(TypedDict):
    """Bull vs Bear researcher debate state."""
    bull_history: Annotated[str, "Bullish conversation history"]
    bear_history: Annotated[str, "Bearish conversation history"]
    history: Annotated[str, "Full debate transcript"]
    current_response: Annotated[str, "Latest response"]
    judge_decision: Annotated[str, "Final judge decision"]
    count: Annotated[int, "Debate round count"]


class RiskDebateState(TypedDict):
    """Three-way risk management debate state."""
    aggressive_history: Annotated[str, "Aggressive agent history"]
    conservative_history: Annotated[str, "Conservative agent history"]
    neutral_history: Annotated[str, "Neutral agent history"]
    history: Annotated[str, "Full debate transcript"]
    latest_speaker: Annotated[str, "Last speaker role"]
    current_aggressive_response: Annotated[str, "Latest aggressive response"]
    current_conservative_response: Annotated[str, "Latest conservative response"]
    current_neutral_response: Annotated[str, "Latest neutral response"]
    judge_decision: Annotated[str, "Judge's decision"]
    count: Annotated[int, "Risk debate round count"]


class AgentState(TypedDict):
    """Top-level state that flows through the entire graph."""

    # Input
    company_of_interest: Annotated[str, "Stock symbol being analyzed"]
    trade_date: Annotated[str, "Analysis date (YYYY-MM-DD)"]
    market: Annotated[str, "Market: a_stock, hk_stock, us_stock"]

    # Messages (LangGraph built-in)
    messages: Annotated[list[Any], add_messages]

    # Sender tracking
    sender: Annotated[str, "Agent that sent the last message"]

    # Analyst reports (Phase 1)
    market_report: Annotated[str, "Market/technical analyst report"]
    sentiment_report: Annotated[str, "Social media sentiment report"]
    news_report: Annotated[str, "News and macro report"]
    fundamentals_report: Annotated[str, "Fundamental analysis report"]
    policy_report: Annotated[str, "Policy analysis report (A-stock)"]
    hot_money_report: Annotated[str, "Hot money / capital flow report (A-stock)"]
    lockup_report: Annotated[str, "Lockup expiry / insider report (A-stock)"]

    # Quality gate
    data_quality_summary: Annotated[str, "Quality gate assessment"]

    # Investment debate (Phase 2)
    investment_debate_state: Annotated[InvestDebateState, "Bull vs Bear debate state"]
    investment_plan: Annotated[str, "Research Manager's investment plan"]

    # Trader (Phase 3)
    trader_investment_plan: Annotated[str, "Trader's transaction proposal"]

    # Risk debate (Phase 4)
    risk_debate_state: Annotated[RiskDebateState, "Three-way risk debate state"]
    final_trade_decision: Annotated[str, "Portfolio Manager's final decision"]

    # Memory
    past_context: Annotated[str, "Prior decisions and reflections for this ticker"]

    # Selected analysts
    selected_analysts: Annotated[list[str], "List of analyst types to run"]
