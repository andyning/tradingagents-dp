"""LLM integration tests — actual DeepSeek API calls.

These tests require a valid DEEPSEEK_API_KEY in .env.
Marked as 'integration' so they can be skipped with -m "not integration".
"""

import pytest

from tradingagents.config import get_settings, reset_settings
from tradingagents.llm.client import DeepSeekClient, get_llm_client, clear_client_cache


@pytest.mark.integration
class TestQuickThinkIntegration:
    """Test quick-think (deepseek-chat) mode with real API calls."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_client_cache()
        reset_settings()
        settings = get_settings()
        if not settings.deepseek_api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")
        self.client = get_llm_client("quick")

    def test_simple_chat(self):
        """Basic chat completion."""
        resp = self.client.chat([{"role": "user", "content": "Reply with exactly: OK"}])
        assert resp.content is not None
        assert len(resp.content.strip()) > 0

    def test_chinese_response(self):
        """Chinese language response."""
        resp = self.client.chat([{"role": "user", "content": "用中文回答：今天天气怎么样？控制在10个字以内。"}])
        assert resp.content is not None
        assert len(resp.content.strip()) > 0

    def test_json_mode(self):
        """JSON mode output."""
        resp = self.client.chat(
            [{"role": "user", "content": 'Output the following JSON exactly: {"score": 85, "reason": "good"}'}],
            json_mode=True,
        )
        import json
        content = resp.content or ""
        data = json.loads(content)
        assert "score" in data

    def test_structured_output(self):
        """Structured JSON output with schema."""
        schema = {
            "type": "object",
            "properties": {
                "rating": {"type": "string", "enum": ["Buy", "Hold", "Sell"]},
                "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["rating", "confidence"],
        }
        result = self.client.structured(
            [{"role": "user", "content": "Rate Apple stock: Buy, 5 confidence."}],
            schema, schema_name="stock_rating",
        )
        assert result["rating"] in ("Buy", "Hold", "Sell")
        assert 1 <= result["confidence"] <= 5

    def test_long_context(self):
        """Handle a moderately long prompt like an analyst report request."""
        prompt = (
            "You are a market analyst. Analyze the following stock data for 贵州茅台(600519). "
            "最新收盘价 1800元, 涨跌幅 +2.5%, 5日均量 500万手, 20日均量 450万手. "
            "MACD金叉, RSI 65, 股价在布林带中轨上方. "
            "Provide a concise analysis in Chinese, under 200 words."
        )
        resp = self.client.chat([{"role": "user", "content": prompt}])
        assert resp.content is not None
        assert len(resp.content.strip()) > 50, "Response too short for analytical content"


@pytest.mark.integration
class TestDeepThinkIntegration:
    """Test deep-think (deepseek-reasoner) mode with real API calls."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_client_cache()
        reset_settings()
        settings = get_settings()
        if not settings.deepseek_api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")
        self.client = get_llm_client("deep")

    def test_reasoning_response(self):
        """Deep reasoning on a financial question."""
        resp = self.client.chat([{
            "role": "user",
            "content": (
                "A stock has PE=35, sector average PE=25, ROE=18%, revenue growth=25% YoY. "
                "Is it overvalued? Answer with reasoning in under 100 words."
            ),
        }])
        assert resp.content is not None
        assert len(resp.content.strip()) > 30

    def test_complex_analysis(self):
        """Complex multi-factor analysis requiring reasoning."""
        resp = self.client.chat([{
            "role": "user",
            "content": (
                "Analyze whether to Buy/Hold/Sell 宁德时代(300750): "
                "PE=28, PB=6.5, ROE=22%, debt ratio=65%, "
                "revenue growth=15%, net profit growth=8%, "
                "price at 200-day MA support, northbound net inflow 连续5日. "
                "新能源补贴退坡, 锂价下跌对电池厂利好. "
                "Give a single rating: Buy, Hold, or Sell, with 2-3 sentence reasoning."
            ),
        }])
        assert resp.content is not None
        content = resp.content.lower()
        assert any(r in content for r in ("buy", "hold", "sell")), \
            f"Expected rating not found in: {content[:200]}"


@pytest.mark.integration
class TestClientConsistency:
    """Test that quick and deep clients don't interfere with each other."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_client_cache()
        reset_settings()
        settings = get_settings()
        if not settings.deepseek_api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")

    def test_both_modes_independent(self):
        """Quick and deep clients can be used independently."""
        quick = get_llm_client("quick")
        deep = get_llm_client("deep")
        assert quick is not deep
        assert quick.mode == "quick"
        assert deep.mode == "deep"

        # Both should work
        r1 = quick.chat([{"role": "user", "content": "Say 'hello'"}])
        r2 = deep.chat([{"role": "user", "content": "Say 'world'"}])
        assert r1.content is not None
        assert r2.content is not None
