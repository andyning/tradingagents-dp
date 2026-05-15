"""End-to-end pipeline integration test.

Runs the full multi-agent analysis on a real ticker with real data.
This is the final verification that everything works together.
"""

import pytest

from tradingagents.config import get_settings, reset_settings
from tradingagents.graph import TradingAgentsGraph
from tradingagents.llm.client import clear_client_cache


@pytest.mark.integration
class TestFullPipeline:
    """End-to-end pipeline tests with real LLM calls."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_client_cache()
        reset_settings()
        settings = get_settings()
        if not settings.deepseek_api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")

    def test_pipeline_a_stock(self):
        """Run full pipeline on 贵州茅台 (600519)."""
        graph = TradingAgentsGraph(debug=False)
        state, decision = graph.propagate(
            "600519",
            "2025-05-14",
            market="a_stock",
        )

        # Verify state contains all expected keys
        assert "market_report" in state
        assert "sentiment_report" in state
        assert "news_report" in state
        assert "fundamentals_report" in state
        assert "policy_report" in state
        assert "hot_money_report" in state
        assert "lockup_report" in state
        assert "investment_plan" in state
        assert "trader_investment_plan" in state
        assert "final_trade_decision" in state

        # Verify all reports have content
        for report_key in [
            "market_report", "news_report", "fundamentals_report",
            "investment_plan", "trader_investment_plan", "final_trade_decision",
        ]:
            content = state[report_key]
            assert content, f"{report_key} is empty"
            assert len(content.strip()) > 50, \
                f"{report_key} too short ({len(content)} chars)"

        # Verify decision contains a valid rating
        decision_lower = decision.lower()
        valid_ratings = ["buy", "overweight", "hold", "underweight", "sell"]
        assert any(r in decision_lower for r in valid_ratings), \
            f"Decision must contain a valid rating. Got: {decision[:300]}"

        print(f"\nPipeline complete for 600519")
        print(f"  Decision: {self._extract_rating(decision)}")
        print(f"  Market report: {len(state['market_report'])} chars")
        print(f"  News report: {len(state['news_report'])} chars")
        print(f"  Fundamentals report: {len(state['fundamentals_report'])} chars")
        print(f"  Investment plan: {len(state['investment_plan'])} chars")
        print(f"  Trader plan: {len(state['trader_investment_plan'])} chars")
        print(f"  Final decision: {len(state['final_trade_decision'])} chars")

    def test_pipeline_debate_state(self):
        """Verify debate state is populated correctly."""
        graph = TradingAgentsGraph(debug=False)
        state, decision = graph.propagate(
            "000001",
            "2025-05-14",
            market="a_stock",
        )

        # Verify debate state
        debate = state.get("investment_debate_state", {})
        assert debate.get("count", 0) > 0, "Should have at least 1 debate round"
        assert debate.get("bull_history"), "Bull history should not be empty"
        assert debate.get("bear_history"), "Bear history should not be empty"

        # Verify risk debate state
        risk = state.get("risk_debate_state", {})
        assert risk.get("count", 0) > 0, "Should have at least 1 risk debate round"

    def test_pipeline_hk_stock(self):
        """Run pipeline on a HK stock — Tencent (0700.HK)."""
        graph = TradingAgentsGraph(debug=False)
        state, decision = graph.propagate(
            "0700",
            "2025-05-14",
            market="hk_stock",
        )

        assert "final_trade_decision" in state
        assert state["final_trade_decision"], "Decision should not be empty"
        print(f"\nHK Pipeline complete for 0700.HK (Tencent)")

    @staticmethod
    def _extract_rating(text: str) -> str:
        for r in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
            if r.lower() in text.lower():
                return r
        return "Unknown"
