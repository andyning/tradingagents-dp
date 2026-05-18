"""SignalProcessor — extracts structured JSON from Portfolio Manager's final output.

Patterns adopted from TradingAgents-CN. Two-tier extraction:
  1. LLM-based: small LLM call to parse the decision text into JSON
  2. Fallback: 14+ regex patterns + smart price estimation (no LLM needed)
"""

from __future__ import annotations

import json
import re
from typing import Any

from tradingagents.llm.client import get_llm_client
from tradingagents.logging import get_logger

logger = get_logger(__name__)

# Action mapping — handle English, Chinese, and variants
ACTION_MAP = {
    "buy": "买入", "hold": "持有", "sell": "卖出",
    "BUY": "买入", "HOLD": "持有", "SELL": "卖出",
    "购买": "买入", "保持": "持有", "出售": "卖出",
    "purchase": "买入", "keep": "持有", "dispose": "卖出",
    "买入": "买入", "持有": "持有", "卖出": "卖出",
    "增持": "增持", "减持": "减持",
}

# Unify to 5-tier rating
def _normalize_action(action: str) -> str:
    a = action.strip()
    if a in ("买入", "buy", "BUY", "增持"):
        return "Buy"
    if a in ("卖出", "sell", "SELL", "减持"):
        return "Sell"
    return "Hold"


# Price extraction regexes for Chinese financial text.
# Each regex captures a decimal number in group(1). Ordered by specificity —
# more specific patterns (目标价位:) are checked first to avoid false positives.
_PRICE_PATTERNS = [
    r'目标价[位格]?[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',     # 目标价位: 45.50 / 目标价：45.50
    r'目标[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',              # 目标: 45.50
    r'价格[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',              # 价格: 45.50
    r'价位[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',              # 价位: 45.50
    r'合理[价位格]?[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',      # 合理价位: 45.50 / 合理估值：45.50
    r'估值[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',              # 估值: 45.50
    r'[¥\$](\d+(?:\.\d+)?)',                           # ¥45.50 / $190
    r'(\d+(?:\.\d+)?)元',                              # 45.50元
    r'(\d+(?:\.\d+)?)美元',                             # 190美元
    r'建议[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',              # 建议: 45.50
    r'预期[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',              # 预期: 45.50
    r'看[到至]\s*[¥\$]?(\d+(?:\.\d+)?)',              # 看到45.50 / 看至50
    r'上涨[到至]\s*[¥\$]?(\d+(?:\.\d+)?)',             # 上涨到45.50
    r'(\d+(?:\.\d+)?)\s*[¥\$]',                        # 45.50¥ (number before symbol)
]


def extract_decision(decision_text: str, symbol: str = None, market: str = "a_stock") -> dict[str, Any]:
    """Extract structured decision from Portfolio Manager's final output.

    Returns dict with keys: action, confidence, risk_score, target_price, reasoning
    """
    if not decision_text or not isinstance(decision_text, str) or not decision_text.strip():
        return _default_decision()

    text = decision_text.strip()

    # ── Tier 1: LLM-based extraction ──
    try:
        currency = "CNY" if market == "a_stock" else "HKD" if market == "hk_stock" else "USD"
        currency_symbol = "¥" if market == "a_stock" else "HK$" if market == "hk_stock" else "$"

        prompt = (
            f"Extract structured investment decision from the following report.\n"
            f"The stock ({symbol or 'unknown'}) trades in {currency} ({currency_symbol}).\n\n"
            f"Return ONLY valid JSON:\n"
            f'{{"action": "买入/持有/卖出", "target_price": number_or_null,\n'
            f' "confidence": 0.0-1.0, "risk_score": 0.0-1.0,\n'
            f' "reasoning": "brief Chinese summary"}}\n\n'
            f"Rules:\n"
            f"1. action MUST be 买入, 持有, or 卖出 (Chinese only)\n"
            f"2. target_price in {currency_symbol}, null if not mentioned\n"
            f"3. confidence (0.3-0.95) must reflect conviction level from the report's evidence strength, not a default\n"
            f"4. risk_score (0.1-0.9) must reflect downside risk severity, not a default\n\n"
            f"Report:\n{text[:3000]}"
        )

        llm = get_llm_client("quick")
        resp = llm.chat([{"role": "user", "content": prompt}], json_mode=True)
        raw = resp.content or ""

        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            action = data.get("action", "持有")
            action = ACTION_MAP.get(action, "持有")

            tp = data.get("target_price")
            if tp is not None and tp != "null" and tp != "":
                try:
                    tp = float(str(tp).replace("$", "").replace("¥", "").replace("￥", ""))
                except (ValueError, TypeError):
                    tp = _extract_price_from_text(text)

            # Use LLM values, but validate they're in reasonable ranges
            raw_conf = float(data.get("confidence", -1))
            raw_risk = float(data.get("risk_score", -1))
            # If LLM returned clearly bogus values (>0.95 or <0.2), use regex extraction
            confidence = raw_conf if 0.2 <= raw_conf <= 0.95 else _extract_confidence(text)
            risk_score = raw_risk if 0.1 <= raw_risk <= 0.9 else _extract_risk_score(text)

            return {
                "action": _normalize_action(action),
                "confidence": confidence,
                "risk_score": risk_score,
                "target_price": tp or _extract_price_from_text(text),
                "reasoning": data.get("reasoning", text[:200]),
            }
    except Exception as exc:
        logger.debug("SignalProcessor LLM path failed: %s, using regex fallback", exc)

    # ── Tier 2: Regex-only fallback (no LLM) ──
    action = _extract_action(text)
    tp = _extract_price_from_text(text)

    # Try to extract confidence from text clues
    confidence = _extract_confidence(text)
    risk_score = _extract_risk_score(text)

    return {
        "action": action,
        "confidence": confidence,
        "risk_score": risk_score,
        "target_price": tp,
        "reasoning": text[:300],
    }


def _extract_action(text: str) -> str:
    """Extract action from text using regex."""
    tl = text.lower()
    for keyword, action in [("买入", "Buy"), ("buy", "Buy"), ("增持", "Buy"),
                             ("卖出", "Sell"), ("sell", "Sell"), ("减持", "Sell"),
                             ("持有", "Hold"), ("hold", "Hold")]:
        if keyword in tl:
            return action
    return "Hold"


def _extract_confidence(text: str) -> float:
    """Extract confidence from text cues. Falls back to 0.6 if no clues found."""
    tl = text.lower()
    # Explicit percentages
    m = re.search(r'(?:confidence|置信度|把握)[^\d]*(\d{1,2}(?:\.\d)?)\s*%', tl)
    if m:
        val = float(m.group(1)) / 100
        return max(0.3, min(0.95, val))
    # Strong conviction phrases
    if any(w in tl for w in ("强烈建议", "强烈推荐", "高确定性", "high conviction", "strong buy", "strong sell")):
        return 0.85
    if any(w in tl for w in ("明确看多", "明确看空", "clearly bullish", "clearly bearish")):
        return 0.80
    if any(w in tl for w in ("建议买入", "建议卖出", "recommend buy", "recommend sell")):
        return 0.75
    if any(w in tl for w in ("建议持有", "建议观望", "recommend hold", "wait and see")):
        return 0.65
    if any(w in tl for w in ("不确定", "风险较高", "uncertain", "high risk")):
        return 0.55
    return 0.65  # Neutral default — higher than 0.5 to avoid uniform look


def _extract_risk_score(text: str) -> float:
    """Extract risk score from text cues."""
    tl = text.lower()
    m = re.search(r'(?:risk|风险)[^\d]*(\d{1,2}(?:\.\d)?)\s*%', tl)
    if m:
        val = float(m.group(1)) / 100
        return max(0.1, min(0.9, val))
    if any(w in tl for w in ("高风险", "极高风险", "very high risk", "extreme risk")):
        return 0.75
    if any(w in tl for w in ("较高风险", "high risk", "elevated risk")):
        return 0.60
    if any(w in tl for w in ("中等风险", "moderate risk", "medium risk")):
        return 0.45
    if any(w in tl for w in ("较低风险", "低风险", "low risk", "minimal risk")):
        return 0.30
    if any(w in tl for w in ("防御性", "defensive", "conservative")):
        return 0.35
    # Inversely correlated with confidence: higher confidence → lower perceived risk
    conf = _extract_confidence(text)
    return max(0.3, min(0.7, 0.95 - conf + 0.2))


def _extract_price_from_text(text: str) -> float | None:
    """Extract target price using 14 regex patterns."""
    for pattern in _PRICE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


def _default_decision() -> dict[str, Any]:
    return {
        "action": "Hold",
        "confidence": 0.5,
        "risk_score": 0.5,
        "target_price": None,
        "reasoning": "No decision data available",
    }
