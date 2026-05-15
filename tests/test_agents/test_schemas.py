"""Test agent Pydantic schemas."""

from tradingagents.agents.schemas import (
    PortfolioDecision,
    PortfolioRating,
    ResearchPlan,
    TraderAction,
    TraderProposal,
    render_pm_decision,
    render_research_plan,
    render_trader_proposal,
)


class TestPortfolioDecision:
    def test_buy_decision(self):
        d = PortfolioDecision(
            rating=PortfolioRating.BUY,
            executive_summary="Strong buy signal.",
            investment_thesis="Multiple catalysts converging.",
            price_target=2000.0,
            time_horizon="3-6 months",
        )
        assert d.rating == PortfolioRating.BUY
        assert d.price_target == 2000.0

    def test_render_markdown(self):
        d = PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary="Hold position.",
            investment_thesis="Mixed signals.",
        )
        md = render_pm_decision(d)
        assert "**Rating**: Hold" in md
        assert "Hold position." in md


class TestResearchPlan:
    def test_buy_recommendation(self):
        plan = ResearchPlan(
            recommendation=PortfolioRating.OVERWEIGHT,
            rationale="Bull argument stronger.",
            strategic_actions="Gradually add to position.",
        )
        md = render_research_plan(plan)
        assert "Overweight" in md
        assert "Bull argument" in md


class TestTraderProposal:
    def test_buy_action(self):
        p = TraderProposal(
            action=TraderAction.BUY,
            reasoning="Entry signal triggered.",
            entry_price=1800.0,
            stop_loss=1750.0,
            position_sizing="10%",
        )
        md = render_trader_proposal(p)
        assert "BUY" in md
        assert "FINAL TRANSACTION PROPOSAL" in md
