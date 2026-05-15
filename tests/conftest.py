"""Shared pytest fixtures."""

import os
from unittest.mock import MagicMock, patch

import pytest


def pytest_configure(config):
    for marker in ("unit", "integration", "smoke"):
        config.addinivalue_line("markers", f"{marker}: {marker}-level tests")


@pytest.fixture(autouse=True)
def _dummy_api_keys(monkeypatch):
    # Load the real key from .env if present, otherwise use placeholder
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("DEEPSEEK_API_KEY", "test-placeholder")
    monkeypatch.setenv("DEEPSEEK_API_KEY", key)


@pytest.fixture
def mock_settings(monkeypatch):
    """Provide test-friendly settings."""
    monkeypatch.setenv("TA_LLM_API_KEY", "test-key")
    monkeypatch.setenv("TA_DATA_CACHE_DIR", "/tmp/tradingagents-test-cache")
    monkeypatch.setenv("TA_RESULTS_DIR", "/tmp/tradingagents-test-results")


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings singleton between tests."""
    from tradingagents.config import reset_settings
    reset_settings()
