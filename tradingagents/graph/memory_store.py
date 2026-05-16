"""Persistent memory store for trading decisions.

Lightweight JSON file-based storage. Each analysis result is saved
per ticker to ``~/.tradingagents/cache/memory/{ticker}.json``.

Architecture:
- store_analysis(): saves decision metadata + auto-generates LLM reflection
- retrieve_memories(): loads past analyses for a ticker, most recent first
- get_memory_context(): formats memories as Markdown for prompt injection
- generate_reflection(): uses quick LLM to produce structured lessons

Thread safety: file reads/writes are atomic on most OSes. No concurrent
write protection — assumes single process per ticker.

Limits: MAX_MEMORIES_PER_TICKER = 20 entries per file. Oldest trimmed.
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


_REFLECTION_PROMPT = """You are an expert trading coach. Review the following investment analysis and provide a structured lesson.

The analysis was for {ticker} on {trade_date}. The final rating was {action} (confidence: {confidence:.0%}).

Analysis Report:
{decision_summary}

Market Context:
{market_context}

Provide your response in exactly this format:

**Reasoning**: Was the decision well-supported by the data? 2-3 sentences.
**Lesson**: What is the single most important takeaway for future analyses of this stock? 1 sentence.
**Watch**: What signal or condition would have changed this decision? 1 sentence.

Keep the total under 200 words. Be specific to {ticker}."""


def generate_reflection(
    ticker: str,
    trade_date: str,
    action: str,
    confidence: float,
    decision: str,
    market_report: str = "",
    fundamentals_report: str = "",
) -> str:
    """Generate a structured reflection on an analysis using the LLM.

    Returns a concise lesson (under 200 words) that can be stored and
    retrieved to improve future analyses.
    """
    try:
        from tradingagents.llm.client import get_llm_client

        market_context = (market_report or "")[:500] + "\n" + (fundamentals_report or "")[:300]
        prompt = _REFLECTION_PROMPT.format(
            ticker=ticker,
            trade_date=trade_date,
            action=action,
            confidence=confidence,
            decision_summary=(decision or "")[:800],
            market_context=market_context[:600],
        )

        llm = get_llm_client("quick")
        resp = llm.chat([{"role": "user", "content": prompt}])
        reflection = (resp.content or "").strip()
        logger.info("Reflection generated for %s (%d chars)", ticker, len(reflection))
        return reflection
    except Exception as exc:
        logger.warning("Reflection generation failed: %s", exc)
        return ""


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
    """Store an analysis result with auto-generated reflection."""
    entries = _load(ticker)

    # Remove existing entry for same date+depth (update-in-place)
    entries = [e for e in entries if not (e.get("trade_date") == trade_date and e.get("depth") == depth)]

    # Generate reflection lesson from the LLM
    reflection = generate_reflection(
        ticker=ticker, trade_date=trade_date, action=action,
        confidence=confidence, decision=decision,
        market_report=market_report, fundamentals_report=fundamentals_report,
    )

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
        "reflection": reflection,
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
    """Return a formatted string of past memories with reflection lessons."""
    memories = retrieve_memories(ticker, market, limit)
    if not memories:
        return ""

    lines = ["## 历史分析记录与反思教训 (Past Analysis & Lessons Learned)", ""]
    for i, m in enumerate(memories):
        tp = f", 目标价 {m['target_price']}" if m.get("target_price") else ""
        lines.append(
            f"{i+1}. **{m['trade_date']}** ({m.get('depth', '')}): "
            f"评级 **{m.get('action', 'N/A')}**, "
            f"置信度 {float(m.get('confidence', 0)):.0%}"
            f"{tp}"
        )
        # Include the reflection lesson if available
        reflection = m.get("reflection", "")
        if reflection:
            # Extract just the Lesson line for brevity
            for rline in reflection.split("\n"):
                rline = rline.strip()
                if rline.startswith("**Lesson**") or rline.startswith("**Watch**"):
                    clean = rline.replace("**Lesson**:", "  - 教训:").replace("**Watch**:", "  - 关注:").replace("**", "")
                    lines.append(clean)
            lines.append("")
    lines.append("*以上为历史分析记录与AI反思，请结合当前数据独立判断。*")
    lines.append("")
    return "\n".join(lines)
