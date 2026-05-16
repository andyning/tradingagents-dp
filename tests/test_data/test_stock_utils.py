"""Tests for market detection and stock utility functions."""

import sys
from pathlib import Path

import pytest

# Test the _detect_market function from web/app.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tradingagents.web.app import _detect_market, _market_label


class TestDetectMarket:
    def test_a_stock_shanghai(self):
        assert _detect_market("600519") == "a_stock"
        assert _detect_market("688775") == "a_stock"

    def test_a_stock_shenzhen(self):
        assert _detect_market("000001") == "a_stock"
        assert _detect_market("002241") == "a_stock"
        assert _detect_market("300750") == "a_stock"

    def test_hk_stock(self):
        assert _detect_market("0700") == "hk_stock"
        assert _detect_market("09660") == "hk_stock"
        assert _detect_market("9988") == "hk_stock"

    def test_hk_with_suffix(self):
        assert _detect_market("0700.HK") == "hk_stock"
        assert _detect_market("9988.HK") == "hk_stock"

    def test_us_stock(self):
        assert _detect_market("AAPL") == "us_stock"
        assert _detect_market("AMD") == "us_stock"
        assert _detect_market("TSLA") == "us_stock"
        assert _detect_market("INTC") == "us_stock"

    def test_empty_input(self):
        assert _detect_market("") == "a_stock"

    def test_shanghai_prefix(self):
        assert _detect_market("SH.600519") == "a_stock"

    def test_shenzhen_prefix(self):
        assert _detect_market("SZ.000001") == "a_stock"

    def test_five_digit_numeric(self):
        """5-digit numbers should be HK, not A-share."""
        assert _detect_market("09660") == "hk_stock"


class TestMarketLabel:
    def test_labels(self):
        assert "A-Share" in _market_label("a_stock")
        assert "Hong Kong" in _market_label("hk_stock")
        assert "US" in _market_label("us_stock")
