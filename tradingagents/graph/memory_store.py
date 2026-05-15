"""Persistent memory store for trading decisions.

Lightweight JSON file-based storage. Each analysis result is saved
per ticker. Before the next analysis, past results for the same ticker
are retrieved and injected as context.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tradingagents.config import get_settings
from tradingagents.logging import get_logger

logger = get_logger(__name__)

MAX_MEMORIES_PER_TICKER = 20


def _memory_dir() -> Path:
    d = get_settings().data_cache_dir / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _memory_path(ticker: str) -> Path:
    safe = ticker.strip().replace("/", "_").replace("\\", "_").replace("..", "")
    return _memory_dir() / f"{safe}.json"


def _load(ticker: str) -> list[dict[str, Any]]:
    path = _memory_path(ticker)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(ticker: str, entries: list[dict[str, Any]]) -> None:
    path = _memory_path(ticker)
    # Keep only the most recent N entries
    entries = entries[-MAX_MEMORIES_PER_TICKER:]
    try:
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save memory: %s", exc)


def store_analysis(
    ticker: str,
    trade_date: str,
    market: str,
    depth: str,
    decision: str,
    market_report: str,
    fundamentals_report: str,
    news_report: str,
    action: str = "",
    confidence: float = 0.0,
    risk_score: float = 0.0,
    target_price: float | None = None,
) -> None:
    """Store an analysis result. Appends to ticker's memory file."""
    entries = _load(ticker)

    # Remove existing entry for same date+depth (update-in-place)
    entries = [e for e in entries if not (e.get("trade_date") == trade_date and e.get("depth") == depth)]

    entries.append({
        "ticker": ticker,
        "trade_date": trade_date,
        "market": market,
        "depth": depth,
        "action": action,
        "confidence": confidence,
        "risk_score": risk_score,
        "target_price": str(target_price) if target_price else "",
        "decision_summary": (decision or "")[:500],
        "stored_at": datetime.now().isoformat(),
    })
    _save(ticker, entries)
    logger.info("Memory stored: %s %s (%s)", ticker, trade_date, depth)


def retrieve_memories(
    ticker: str,
    market: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve past analyses for the same ticker. Most recent first."""
    entries = _load(ticker)
    entries.sort(key=lambda e: e.get("trade_date", ""), reverse=True)
    return entries[:limit]


def get_memory_context(ticker: str, market: str = "", limit: int = 5) -> str:
    """Return a formatted string of past memories for prompt injection."""
    memories = retrieve_memories(ticker, market, limit)
    if not memories:
        return ""

    lines = ["## 历史分析记录 (Past Analysis Memory)", ""]
    for i, m in enumerate(memories):
        tp = f", 目标价 {m['target_price']}" if m.get("target_price") else ""
        lines.append(
            f"{i+1}. **{m['trade_date']}** ({m.get('depth', '')}): "
            f"评级 **{m.get('action', 'N/A')}**, "
            f"置信度 {float(m.get('confidence', 0)):.0%}"
            f"{tp}"
        )
    lines.append("")
    lines.append("*以上为历史分析记录，请结合当前数据独立判断。*")
    lines.append("")
    return "\n".join(lines)
