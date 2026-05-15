"""Persistent memory store for trading decisions.

Uses ChromaDB for vector similarity search. Each analysis run is stored
as a (situation_embedding, decision_metadata) pair. Before the next
analysis, similar past situations are retrieved and injected as context
so the LLM learns from history.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from tradingagents.config import get_settings
from tradingagents.logging import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_client = None
_collections: dict[str, Any] = {}


def _get_client():
    """Lazy-init ChromaDB client with Windows compatibility."""
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client
        try:
            import chromadb
            persist_dir = str(get_settings().data_cache_dir / "chromadb")
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=persist_dir)
            logger.info("ChromaDB initialized at %s", persist_dir)
        except Exception as exc:
            logger.warning("ChromaDB unavailable (%s), using in-memory fallback", exc)
            try:
                import chromadb
                _client = chromadb.Client()
            except Exception:
                _client = None
                logger.warning("Memory store disabled")
    return _client


def _get_collection(name: str):
    """Get or create a named collection."""
    global _collections
    if name in _collections:
        return _collections[name]

    client = _get_client()
    if client is None:
        return None

    with _lock:
        if name in _collections:
            return _collections[name]
        try:
            coll = client.get_collection(name=name)
        except Exception:
            try:
                coll = client.create_collection(name=name)
            except Exception:
                try:
                    coll = client.get_collection(name=name)
                except Exception as e:
                    logger.warning("Collection %s unavailable: %s", name, e)
                    return None
        _collections[name] = coll
        return coll


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
    """Store an analysis result in the memory store."""
    coll = _get_collection("trading_memory")
    if coll is None:
        return

    try:
        # Build situation description (what the market looked like)
        situation = (
            f"Ticker: {ticker} | Date: {trade_date} | Market: {market}\n"
            f"Market Report: {market_report[:800]}\n"
            f"Fundamentals: {fundamentals_report[:500]}\n"
            f"News: {news_report[:500]}"
        )

        # Build metadata
        metadata = {
            "ticker": ticker,
            "trade_date": trade_date,
            "market": market,
            "depth": depth,
            "action": action,
            "confidence": confidence,
            "risk_score": risk_score,
            "target_price": str(target_price) if target_price else "",
            "stored_at": datetime.now().isoformat(),
        }

        # Store with ticker as document id prefix for easy retrieval
        doc_id = f"{ticker}_{trade_date}_{depth}"
        coll.add(
            documents=[situation],
            metadatas=[metadata],
            ids=[doc_id],
        )
        logger.info("Memory stored: %s", doc_id)
    except Exception as exc:
        logger.warning("Failed to store memory: %s", exc)


def retrieve_memories(
    ticker: str,
    market: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve past analyses for the same ticker.

    Returns list of dicts with keys: ticker, trade_date, action, confidence,
    risk_score, decision_summary, similarity.
    """
    coll = _get_collection("trading_memory")
    if coll is None:
        return []

    try:
        # Query with the ticker as a simple filter
        query_text = f"Ticker: {ticker} | Market: {market}"
        results = coll.query(
            query_texts=[query_text],
            n_results=min(limit, 10),
            where={"ticker": ticker},
        )

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        memories = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            doc = results["documents"][0][i] if results.get("documents") else ""
            dist = results["distances"][0][i] if results.get("distances") else 0
            similarity = max(0, 1 - dist) if dist else 0

            memories.append({
                "ticker": meta.get("ticker", ticker),
                "trade_date": meta.get("trade_date", ""),
                "action": meta.get("action", ""),
                "confidence": float(meta.get("confidence", 0)),
                "risk_score": float(meta.get("risk_score", 0)),
                "target_price": meta.get("target_price", ""),
                "similarity": round(similarity, 3),
            })

        # Sort by most recent first
        memories.sort(key=lambda m: m["trade_date"], reverse=True)
        return memories

    except Exception as exc:
        logger.debug("Memory retrieval skipped: %s", exc)
        return []


def get_memory_context(ticker: str, market: str, limit: int = 5) -> str:
    """Return a formatted string of past memories for prompt injection.

    Returns empty string if no memories found.
    """
    memories = retrieve_memories(ticker, market, limit)
    if not memories:
        return ""

    lines = ["## 历史分析记录 (Past Analysis Memory)", ""]
    for i, m in enumerate(memories):
        tp = f", 目标价 {m['target_price']}" if m.get("target_price") else ""
        lines.append(
            f"{i+1}. **{m['trade_date']}**: 评级 **{m['action']}**, "
            f"置信度 {m['confidence']:.0%}, 风险 {m['risk_score']:.0%}{tp}"
        )
    lines.append("")
    lines.append("*以上为历史分析记录，仅供参考。请结合当前数据独立判断。*")
    lines.append("")
    return "\n".join(lines)
