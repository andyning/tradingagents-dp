"""LangGraph StateGraph builder — assembles the trading agent pipeline.

Supports three analysis depths:
  - light:   market → fundamentals → news → research_manager → portfolio_manager  (5 steps)
  - medium:  7 analysts → quality_gate → bull⇄bear → research_manager → trader → PM  (13 steps)
  - deep:    full 16 steps including three-way risk debate
"""

from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from tradingagents.graph.state import AgentState
from tradingagents.graph.nodes import (
    aggressive_risk_node, bear_researcher_node, bull_researcher_node,
    conservative_risk_node,
    fundamentals_analyst_node, hot_money_analyst_node, lockup_analyst_node,
    market_analyst_node, neutral_risk_node, news_analyst_node,
    policy_analyst_node, portfolio_manager_node, quality_gate_node,
    research_manager_node, social_analyst_node, trader_node,
)
from tradingagents.graph.routing import (
    should_continue_debate, should_continue_risk_debate,
)
from tradingagents.logging import get_logger

logger = get_logger(__name__)

# All 18 nodes registered once
_ALL_NODES = {
    "market_analyst": market_analyst_node,
    "social_analyst": social_analyst_node,
    "news_analyst": news_analyst_node,
    "fundamentals_analyst": fundamentals_analyst_node,
    "policy_analyst": policy_analyst_node,
    "hot_money_analyst": hot_money_analyst_node,
    "lockup_analyst": lockup_analyst_node,
    "quality_gate": quality_gate_node,
    "bull_researcher": bull_researcher_node,
    "bear_researcher": bear_researcher_node,
    "research_manager": research_manager_node,
    "trader": trader_node,
    "aggressive_risk": aggressive_risk_node,
    "conservative_risk": conservative_risk_node,
    "neutral_risk": neutral_risk_node,
    "portfolio_manager": portfolio_manager_node,
}


def build_graph(depth: str = "medium", checkpointer: Optional[SqliteSaver] = None) -> StateGraph:
    """Build and compile a graph for the given analysis depth.

    Args:
        depth: "light", "medium", or "deep"
        checkpointer: Optional SQLite checkpointer for resume support.
    """
    workflow = StateGraph(AgentState)

    # Register all nodes
    for name, fn in _ALL_NODES.items():
        workflow.add_node(name, fn)

    workflow.set_entry_point("market_analyst")

    if depth == "light":
        _build_light(workflow)
    elif depth == "deep":
        _build_deep(workflow)
    else:
        _build_medium(workflow)

    logger.info("Graph built: depth=%s", depth)
    return workflow.compile(checkpointer=checkpointer)


def _build_light(wf: StateGraph) -> None:
    """5 steps: market → fundamentals → news → research_manager → portfolio_manager."""
    wf.add_edge("market_analyst", "fundamentals_analyst")
    wf.add_edge("fundamentals_analyst", "news_analyst")
    wf.add_edge("news_analyst", "research_manager")
    wf.add_edge("research_manager", "portfolio_manager")
    wf.add_edge("portfolio_manager", END)


def _build_medium(wf: StateGraph) -> None:
    """13 steps: 7 analysts → quality → bull⇄bear → research_manager → trader → PM."""
    # Analyst chain
    wf.add_edge("market_analyst", "social_analyst")
    wf.add_edge("social_analyst", "news_analyst")
    wf.add_edge("news_analyst", "fundamentals_analyst")
    wf.add_edge("fundamentals_analyst", "policy_analyst")
    wf.add_edge("policy_analyst", "hot_money_analyst")
    wf.add_edge("hot_money_analyst", "lockup_analyst")
    wf.add_edge("lockup_analyst", "quality_gate")

    # Debate
    wf.add_edge("quality_gate", "bull_researcher")
    wf.add_conditional_edges("bull_researcher", should_continue_debate,
        {"bull_researcher": "bear_researcher", "research_manager": "research_manager"})
    wf.add_conditional_edges("bear_researcher", should_continue_debate,
        {"bull_researcher": "bull_researcher", "research_manager": "research_manager"})

    # Trader → PM (skip risk debate)
    wf.add_edge("research_manager", "trader")
    wf.add_edge("trader", "portfolio_manager")
    wf.add_edge("portfolio_manager", END)


def _build_deep(wf: StateGraph) -> None:
    """Full 16 steps with three-way risk debate."""
    # Analyst chain
    wf.add_edge("market_analyst", "social_analyst")
    wf.add_edge("social_analyst", "news_analyst")
    wf.add_edge("news_analyst", "fundamentals_analyst")
    wf.add_edge("fundamentals_analyst", "policy_analyst")
    wf.add_edge("policy_analyst", "hot_money_analyst")
    wf.add_edge("hot_money_analyst", "lockup_analyst")
    wf.add_edge("lockup_analyst", "quality_gate")

    # Debate
    wf.add_edge("quality_gate", "bull_researcher")
    wf.add_conditional_edges("bull_researcher", should_continue_debate,
        {"bull_researcher": "bear_researcher", "research_manager": "research_manager"})
    wf.add_conditional_edges("bear_researcher", should_continue_debate,
        {"bull_researcher": "bull_researcher", "research_manager": "research_manager"})

    # Trader → Risk debate → PM
    wf.add_edge("research_manager", "trader")
    wf.add_edge("trader", "aggressive_risk")
    wf.add_conditional_edges("aggressive_risk", should_continue_risk_debate,
        {"conservative_risk": "conservative_risk", "portfolio_manager": "portfolio_manager"})
    wf.add_conditional_edges("conservative_risk", should_continue_risk_debate,
        {"neutral_risk": "neutral_risk", "portfolio_manager": "portfolio_manager"})
    wf.add_conditional_edges("neutral_risk", should_continue_risk_debate,
        {"aggressive_risk": "aggressive_risk", "portfolio_manager": "portfolio_manager"})
    wf.add_edge("portfolio_manager", END)
