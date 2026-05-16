"""Tests for SignalProcessor — structured decision extraction."""

import pytest
from tradingagents.graph.signal_processor import (
    extract_decision, _extract_action, _extract_price_from_text, _default_decision,
)


class TestExtractAction:
    def test_buy_chinese(self):
        assert _extract_action("建议买入") == "Buy"

    def test_sell_english(self):
        assert _extract_action("we recommend to SELL") == "Sell"

    def test_hold(self):
        assert _extract_action("建议继续持有") == "Hold"

    def test_overweight(self):
        assert _extract_action("建议增持该股票") == "Buy"

    def test_no_action_found(self):
        assert _extract_action("这是一段分析文本") == "Hold"


class TestExtractPriceFromText:
    def test_chinese_target_price(self):
        assert _extract_price_from_text("目标价位：45.50元") == 45.50

    def test_yuan_suffix(self):
        assert _extract_price_from_text("看到250.00元") == 250.00

    def test_dollar_sign(self):
        assert _extract_price_from_text("target $190.50") == 190.50

    def test_estimate_prefix(self):
        assert _extract_price_from_text("估值：123.45") == 123.45

    def test_no_price(self):
        assert _extract_price_from_text("该股票没有明确目标价") is None

    def test_negative_price_ignored(self):
        # Negative prices shouldn't match in financial context
        assert _extract_price_from_text("收益率-5.5%") is None

    def test_range_not_single_price(self):
        # Regex matches the last valid number pattern found
        result = _extract_price_from_text("目标区间45-50元")
        # Either 45.0 or 50.0 is acceptable — both are in the range
        assert result in (45.0, 50.0)

    def test_large_price(self):
        assert _extract_price_from_text("目标价1500.00元") == 1500.00


class TestExtractDecision:
    def test_empty_input(self):
        result = extract_decision("")
        assert result["action"] == "Hold"
        assert result["confidence"] == 0.5

    def test_none_input(self):
        result = extract_decision(None)
        assert result["action"] == "Hold"

    def test_whitespace_only(self):
        result = extract_decision("   \n  ")
        assert result["action"] == "Hold"

    def test_chinese_buy_with_price(self):
        text = "建议买入，目标价位45.50元，置信度较高"
        result = extract_decision(text, "600519", "a_stock")
        assert result["action"] == "Buy"
        assert result["target_price"] == 45.50

    def test_english_sell(self):
        text = "We recommend SELL. Target: $190. Risk is low."
        result = extract_decision(text, "AMD", "us_stock")
        assert result["action"] == "Sell"

    def test_default_decision(self):
        d = _default_decision()
        assert d["action"] == "Hold"
        assert d["confidence"] == 0.5
        assert d["target_price"] is None

    def test_market_currency(self):
        # Different markets should still extract correctly
        result_cny = extract_decision("目标价：100元", "600519", "a_stock")
        assert result_cny["target_price"] == 100.0


class TestCornerCases:
    def test_json_like_text(self):
        """Text that looks like JSON should not crash."""
        text = '{"action": "买入", "target_price": 50}'
        result = extract_decision(text, "600519", "a_stock")
        assert result["action"] in ("Buy", "Sell", "Hold")

    def test_very_long_text(self):
        """Should handle long decision text without hanging."""
        text = "建议买入。" + "这是一个很长的分析报告。" * 500
        result = extract_decision(text, "600519", "a_stock")
        assert result["action"] == "Buy"
