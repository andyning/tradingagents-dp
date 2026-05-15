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


# Price extraction regexes (Chinese financial text)
_PRICE_PATTERNS = [
    r'目标价[位格]?[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'目标[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'价格[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'价位[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'合理[价位格]?[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'估值[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'[¥\$](\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)元',
    r'(\d+(?:\.\d+)?)美元',
    r'建议[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'预期[：:]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'看[到至]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'上涨[到至]\s*[¥\$]?(\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)\s*[¥\$]',
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
            f"3. confidence and risk_score default to 0.7 and 0.5 if not clear\n\n"
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

            return {
                "action": _normalize_action(action),
                "confidence": float(data.get("confidence", 0.7)),
                "risk_score": float(data.get("risk_score", 0.5)),
                "target_price": tp or _extract_price_from_text(text),
                "reasoning": data.get("reasoning", text[:200]),
            }
    except Exception as exc:
        logger.debug("SignalProcessor LLM path failed: %s, using regex fallback", exc)

    # ── Tier 2: Regex-only fallback (no LLM) ──
    action = _extract_action(text)
    tp = _extract_price_from_text(text)

    return {
        "action": action,
        "confidence": 0.7,
        "risk_score": 0.5,
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
