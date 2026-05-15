"""News relevance filter — keeps only news relevant to the target stock.

Three-tier filtering:
  1. Keyword match (company name, ticker, industry terms)
  2. Heuristic scoring (title length, source credibility, recency)
  3. De-duplication (similar titles merged)

All free. No ML model needed.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from tradingagents.logging import get_logger

logger = get_logger(__name__)

# Generic financial noise to filter out
_NOISE_KEYWORDS = [
    "advertisement", "sponsored", "promoted", "subscribe",
    "广告", "推广", "赞助", "订阅", "免责声明",
]


def filter_news(
    news_list: list[dict[str, Any]],
    symbol: str,
    company_name: str = "",
    max_items: int = 15,
) -> list[dict[str, Any]]:
    """Filter and score news items for relevance to a stock.

    Args:
        news_list: List of dicts with 'title', 'source', 'summary', 'publish_time'
        symbol: Stock ticker
        company_name: Optional company name for keyword matching
        max_items: Maximum items to return after filtering

    Returns:
        Filtered and scored list, best first
    """
    if not news_list:
        return []

    # Build keyword set
    keywords = {symbol}
    if company_name:
        keywords.add(company_name.lower())
        # Add partial name matches (first 2 chars of Chinese name)
        if any('一' <= c <= '鿿' for c in company_name):
            for i in range(2, min(len(company_name), 6)):
                keywords.add(company_name[:i])

    scored = []
    for item in news_list:
        title = (item.get("title") or "").strip()
        if not title:
            continue

        # Noise filter
        if any(nk in title.lower() for nk in _NOISE_KEYWORDS):
            continue

        # Keyword relevance score
        title_lower = title.lower()
        kw_hits = sum(1 for kw in keywords if kw.lower() in title_lower)

        # Base score: 0 = irrelevant, each keyword hit adds 1
        score = kw_hits * 1.0

        # Bonus: title contains ticker exactly
        if symbol.lower() in title_lower:
            score += 2.0

        # Bonus: reasonable title length (not too short, not too long)
        tlen = len(title)
        if 15 < tlen < 150:
            score += 0.5

        # Source credibility bonus (known financial sources)
        source = (item.get("source") or "").lower()
        credible_sources = ["reuters", "bloomberg", "wsj", "ft.com", "cnbc",
                            "财新", "证券时报", "上海证券报", "21世纪", "第一财经",
                            "华尔街见闻", "东方财富", "雪球", "新浪财经"]
        if any(cs in source for cs in credible_sources):
            score += 0.5

        # Recency bonus (prefer newer)
        try:
            pub = item.get("publish_time")
            if pub:
                if isinstance(pub, str):
                    pub = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                age_hours = (datetime.now() - pub.replace(tzinfo=None)).total_seconds() / 3600
                if age_hours < 24:
                    score += 1.0
                elif age_hours < 72:
                    score += 0.5
        except Exception:
            pass

        if score > 0:
            scored.append({**item, "_score": score})

    # Deduplicate by similar titles
    scored = _deduplicate(scored)

    # Sort by score desc, take top N
    scored.sort(key=lambda x: x.get("_score", 0), reverse=True)
    result = scored[:max_items]

    # Remove internal score key
    for item in result:
        item.pop("_score", None)

    logger.debug("News filter: %d -> %d items (symbol=%s)", len(news_list), len(result), symbol)
    return result


def _deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicate items with highly similar titles."""
    seen = set()
    result = []
    for item in items:
        title = (item.get("title") or "").strip()
        # Simple fingerprint: first 30 chars + last 10 chars
        fp = title[:30] + title[-10:] if len(title) > 40 else title
        if fp not in seen:
            seen.add(fp)
            result.append(item)
    return result
