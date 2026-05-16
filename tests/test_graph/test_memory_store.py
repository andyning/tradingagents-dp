"""Tests for memory_store — JSON persistence, retrieval, reflection."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tradingagents.graph.memory_store import (
    store_analysis,
    retrieve_memories,
    get_memory_context,
    _memory_path,
    MAX_MEMORIES_PER_TICKER,
)


class TestBasicCRUD:
    def test_store_and_retrieve(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "tradingagents.graph.memory_store.generate_reflection",
            lambda *a, **kw: "Mock reflection",
        )
        store_analysis("600519", "2026-05-15", "a_stock", "medium",
                       "Buy decision", "market report", "fundamentals",
                       "news report", "Buy", 0.85, 0.3, 1500.0)
        mems = retrieve_memories("600519")
        assert len(mems) == 1
        assert mems[0]["action"] == "Buy"
        assert mems[0]["confidence"] == 0.85

    def test_retrieve_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        mems = retrieve_memories("NONEXISTENT")
        assert mems == []

    def test_retrieve_limit(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "tradingagents.graph.memory_store.generate_reflection",
            lambda *a, **kw: "Mock reflection",
        )
        for i in range(10):
            store_analysis("000001", f"2026-01-{i+1:02d}", "a_stock", "light",
                           f"Decision {i}", "", "", "", "Hold", 0.5, 0.5)
        mems = retrieve_memories("000001", limit=3)
        assert len(mems) == 3

    def test_update_in_place(self, monkeypatch, tmp_path):
        """Same date+depth should update, not duplicate."""
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "tradingagents.graph.memory_store.generate_reflection",
            lambda *a, **kw: "Mock reflection",
        )
        store_analysis("600519", "2026-05-15", "a_stock", "medium",
                       "First", "", "", "", "Hold", 0.5, 0.5)
        store_analysis("600519", "2026-05-15", "a_stock", "medium",
                       "Second", "", "", "", "Buy", 0.9, 0.2)
        mems = retrieve_memories("600519")
        assert len(mems) == 1
        assert mems[0]["action"] == "Buy"


class TestMemoryContext:
    def test_format_with_reflection(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "tradingagents.graph.memory_store.generate_reflection",
            lambda *a, **kw: "Mock reflection",
        )
        store_analysis("600519", "2026-05-15", "a_stock", "medium",
                       "Buy decision", "", "", "", "Buy", 0.85, 0.3, 1500.0)
        ctx = get_memory_context("600519")
        assert "600519" in ctx or "2026-05-15" in ctx

    def test_empty_context(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        ctx = get_memory_context("NONEXISTENT")
        assert ctx == ""


class TestMaxEntries:
    def test_truncation(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "tradingagents.graph.memory_store.generate_reflection",
            lambda *a, **kw: "Mock reflection",
        )
        for i in range(MAX_MEMORIES_PER_TICKER + 5):
            store_analysis("000001", f"2026-01-{i+1:02d}", "a_stock", "light",
                           f"Decision {i}", "", "", "", "Hold", 0.5, 0.5)
        mems = retrieve_memories("000001", limit=100)
        assert len(mems) <= MAX_MEMORIES_PER_TICKER


class TestCorruptedFile:
    def test_corrupted_json(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        path = _memory_path("CORRUPT")
        path.write_text("{not valid json", encoding="utf-8")
        mems = retrieve_memories("CORRUPT")
        assert mems == []

    def test_special_ticker_chars(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "tradingagents.graph.memory_store._memory_dir",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "tradingagents.graph.memory_store.generate_reflection",
            lambda *a, **kw: "Mock reflection",
        )
        store_analysis("AAPL", "2026-05-15", "us_stock", "medium",
                       "Buy", "", "", "", "Buy", 0.8, 0.2)
        mems = retrieve_memories("AAPL")
        assert len(mems) == 1
