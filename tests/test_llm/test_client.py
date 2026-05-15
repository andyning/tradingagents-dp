"""Test DeepSeek LLM client."""

import pytest

from tradingagents.llm.client import DeepSeekClient, get_llm_client, clear_client_cache


class TestDeepSeekClient:
    def test_init_defaults(self, mock_settings):
        client = DeepSeekClient(mode="quick")
        assert client.mode == "quick"
        assert client.temperature == 0.0

    def test_deep_mode(self, mock_settings):
        client = DeepSeekClient(mode="deep")
        assert client.mode == "deep"

    def test_custom_model(self, mock_settings):
        client = DeepSeekClient(model="deepseek-chat", mode="quick")
        assert client.model == "deepseek-chat"


class TestGetClient:
    def test_caching(self, mock_settings):
        clear_client_cache()
        c1 = get_llm_client("quick")
        c2 = get_llm_client("quick")
        assert c1 is c2

    def test_different_modes(self, mock_settings):
        clear_client_cache()
        quick = get_llm_client("quick")
        deep = get_llm_client("deep")
        assert quick is not deep
