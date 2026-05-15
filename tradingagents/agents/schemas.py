"""Pydantic data contracts for inter-agent communication.

All agents exchange data through these typed schemas. The three
decision-making agents (Research Manager, Trader, Portfolio Manager)
produce structured Pydantic output; analyst agents produce markdown
reports stored as strings.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---- Enums ----

class PortfolioRating(str, Enum):
    """5-tier rating used by Research Manager and Portfolio Manager."""

    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    """3-tier transaction direction used by the Trader."""

    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


class DataQualityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


# ---- Research Manager ----

class ResearchPlan(BaseModel):
    """Structured investment plan produced by the Research Manager."""

    recommendation: PortfolioRating = Field(
        description="The investment recommendation: Buy / Overweight / Hold / Underweight / Sell."
    )
    rationale: str = Field(
        description="Summary of key points from both sides of the debate, ending with which arguments led to the recommendation."
    )
    strategic_actions: str = Field(
        description="Concrete steps for the trader to implement the recommendation."
    )


def render_research_plan(plan: ResearchPlan) -> str:
    """Render a ResearchPlan to markdown."""
    return "\n".join([
        f"**Recommendation**: {plan.recommendation.value}",
        "",
        f"**Rationale**: {plan.rationale}",
        "",
        f"**Strategic Actions**: {plan.strategic_actions}",
    ])


# ---- Trader ----

class TraderProposal(BaseModel):
    """Structured transaction proposal produced by the Trader."""

    action: TraderAction = Field(
        description="Transaction direction: Buy / Hold / Sell."
    )
    reasoning: str = Field(
        description="The case for this action, anchored in analysts' reports. Two to four sentences."
    )
    entry_price: Optional[float] = Field(
        default=None, description="Optional entry price target."
    )
    stop_loss: Optional[float] = Field(
        default=None, description="Optional stop-loss price."
    )
    position_sizing: Optional[str] = Field(
        default=None, description="Optional sizing guidance, e.g. '5% of portfolio'."
    )


def render_trader_proposal(proposal: TraderProposal) -> str:
    """Render a TraderProposal to markdown."""
    parts = [
        f"**Action**: {proposal.action.value}",
        "",
        f"**Reasoning**: {proposal.reasoning}",
    ]
    if proposal.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {proposal.entry_price}"])
    if proposal.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {proposal.stop_loss}"])
    if proposal.position_sizing:
        parts.extend(["", f"**Position Sizing**: {proposal.position_sizing}"])
    parts.extend([
        "",
        f"FINAL TRANSACTION PROPOSAL: **{proposal.action.value.upper()}**",
    ])
    return "\n".join(parts)


# ---- Portfolio Manager ----

class PortfolioDecision(BaseModel):
    """Final decision produced by the Portfolio Manager."""

    rating: PortfolioRating = Field(
        description="Final position rating: Buy / Overweight / Hold / Underweight / Sell."
    )
    executive_summary: str = Field(
        description="Concise action plan: entry, sizing, risk levels, time horizon. Two to four sentences."
    )
    investment_thesis: str = Field(
        description="Detailed reasoning anchored in specific evidence from the analysts' debate."
    )
    price_target: Optional[float] = Field(
        default=None, description="Optional target price."
    )
    time_horizon: Optional[str] = Field(
        default=None, description="Optional holding period, e.g. '3-6 months'."
    )


def render_pm_decision(decision: PortfolioDecision) -> str:
    """Render a PortfolioDecision to markdown for storage and display."""
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Executive Summary**: {decision.executive_summary}",
        "",
        f"**Investment Thesis**: {decision.investment_thesis}",
    ]
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    return "\n".join(parts)
