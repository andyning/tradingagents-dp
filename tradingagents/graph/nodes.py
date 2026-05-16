"""LangGraph node functions — each node is an agent in the pipeline.

Phase 1: 7 Analysts (market, social, news, fundamentals, policy, hot_money, lockup)
Phase 2: Quality Gate → Bull/Bear Debate → Research Manager
Phase 3: Trader
Phase 4: Three-way Risk Debate → Portfolio Manager
"""

from __future__ import annotations

from typing import Any

from tradingagents.agents.base import render_prompt
from tradingagents.agents.schemas import (
    PortfolioDecision,
    ResearchPlan,
    TraderProposal,
    render_pm_decision,
    render_research_plan,
    render_trader_proposal,
)
from tradingagents.config import get_settings
from tradingagents.graph.data_context import (
    for_backtest,
    for_fundamentals_analyst,
    for_hot_money_analyst,
    for_industry_comparison,
    for_lockup_analyst,
    for_market_analyst,
    for_news_analyst,
    for_policy_analyst,
    for_sentiment_analyst,
)
from tradingagents.graph.progress import complete_step, start_step
from tradingagents.llm.client import DeepSeekClient, get_llm_client
from tradingagents.logging import get_logger

logger = get_logger(__name__)


def _quick_llm() -> DeepSeekClient:
    return get_llm_client("quick")


def _deep_llm() -> DeepSeekClient:
    return get_llm_client("deep")


def _lang_instruction() -> str:
    lang = get_settings().output_language
    if lang.lower() == "chinese":
        return "Write your report in Chinese (Simplified). Use professional financial terminology."
    return ""


def _market_name(market: str) -> str:
    return {"a_stock": "A-stock", "hk_stock": "Hong Kong", "us_stock": "US"}.get(market, market)


def _base_context(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": state.get("company_of_interest", ""),
        "trade_date": state.get("trade_date", ""),
        "market": _market_name(state.get("market", "a_stock")),
        "language_instruction": _lang_instruction(),
    }


def _call_llm_with_retry(messages: list[dict], mode: str = "quick", max_retries: int = 3) -> str:
    """Call LLM with retry on transient failures."""
    llm = get_llm_client(mode)
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = llm.chat(messages)
            return resp.content or ""
        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                time = __import__("time")
                time.sleep(2 * (attempt + 1))
                logger.warning("LLM retry %d/%d after: %s", attempt + 1, max_retries, exc)
    logger.error("LLM failed after %d retries: %s", max_retries, last_error)
    return ""


def _run_analyst(step: str, template: str, state: dict[str, Any], data_context: str) -> str:
    """Common pattern: render prompt, prepend real data, call LLM with progress tracking."""
    start_step(step)
    ctx = _base_context(state)
    prompt = render_prompt(template, **ctx)
    full_prompt = f"{prompt}\n\n---\n\n{data_context}"
    content = _call_llm_with_retry([{"role": "user", "content": full_prompt}])
    complete_step(step, content)
    return content


# ============================================================================
# Phase 1: Analyst Nodes
# ============================================================================

def market_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    data = for_market_analyst(state)
    content = _run_analyst("market_analyst", "market_analyst.j2", state, data)
    logger.info("Market analyst completed (%d chars)", len(content))
    return {"market_report": content, "sender": "market_analyst"}


def social_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    data = for_sentiment_analyst(state)
    content = _run_analyst("social_analyst", "social_analyst.j2", state, data)
    logger.info("Social analyst completed (%d chars)", len(content))
    return {"sentiment_report": content, "sender": "social_analyst"}


def news_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    data = for_news_analyst(state)
    content = _run_analyst("news_analyst", "news_analyst.j2", state, data)
    logger.info("News analyst completed (%d chars)", len(content))
    return {"news_report": content, "sender": "news_analyst"}


def fundamentals_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    data = for_fundamentals_analyst(state)
    backtest = for_backtest(state)
    industry = for_industry_comparison(state)
    data = data + "\n\n" + backtest + "\n\n" + industry
    content = _run_analyst("fundamentals_analyst", "fundamentals_analyst.j2", state, data)
    logger.info("Fundamentals analyst completed (%d chars)", len(content))
    return {"fundamentals_report": content, "sender": "fundamentals_analyst"}


def policy_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    data = for_policy_analyst(state)
    content = _run_analyst("policy_analyst", "policy_analyst.j2", state, data)
    logger.info("Policy analyst completed (%d chars)", len(content))
    return {"policy_report": content, "sender": "policy_analyst"}


def hot_money_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    data = for_hot_money_analyst(state)
    content = _run_analyst("hot_money_analyst", "hot_money_analyst.j2", state, data)
    logger.info("Hot money analyst completed (%d chars)", len(content))
    return {"hot_money_report": content, "sender": "hot_money_analyst"}


def lockup_analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    data = for_lockup_analyst(state)
    content = _run_analyst("lockup_analyst", "lockup_analyst.j2", state, data)
    logger.info("Lockup analyst completed (%d chars)", len(content))
    return {"lockup_report": content, "sender": "lockup_analyst"}


# ============================================================================
# Phase 2: Quality Gate
# ============================================================================

ANALYST_NAMES = {
    "market": "Market/Tech", "social": "Sentiment", "news": "News",
    "fundamentals": "Fundamentals", "policy": "Policy",
    "hot_money": "Hot Money", "lockup": "Lockup",
}

FAILURE_MARKERS = ["无法获取", "cannot retrieve", "don't have access",
                   "unable to fetch", "工具调用失败", "I cannot", "模拟", "simulate"]


def quality_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Hard checks + LLM review of all analyst reports."""
    start_step("quality_gate")
    symbol = state.get("company_of_interest", "")
    reports = {
        "market": state.get("market_report", ""),
        "social": state.get("sentiment_report", ""),
        "news": state.get("news_report", ""),
        "fundamentals": state.get("fundamentals_report", ""),
        "policy": state.get("policy_report", ""),
        "hot_money": state.get("hot_money_report", ""),
        "lockup": state.get("lockup_report", ""),
    }

    # ── Hard checks ──
    hard_grades = {}
    hard_fail = []
    for name, content in reports.items():
        cl = content.strip() if content else ""
        # Legitimate skip: analyst explicitly says "放弃" or "不适用" or "not applicable"
        is_skip = any(w in cl for w in ["放弃", "不适用", "not applicable"]) and len(cl) > 30
        if not cl or len(cl) < 100:
            hard_grades[name] = "F"; hard_fail.append(name)
        elif any(m.lower() in cl.lower() for m in FAILURE_MARKERS):
            hard_grades[name] = "D"; hard_fail.append(name)
        elif is_skip and len(cl) < 800:
            hard_grades[name] = "B"  # Legitimate skip — not a failure
        elif len(cl) > 1500:
            hard_grades[name] = "A"
        elif len(cl) > 500:
            hard_grades[name] = "B"
        else:
            hard_grades[name] = "C"

    # ── LLM review (batch all 7 reports, single call) ──
    llm_grades = {}
    try:
        review_parts = [
            "You are a quality assurance reviewer. Grade each analyst report below on three dimensions:",
            "- **Data Completeness** (A-F): Did they use the real data provided? Fabricated data = F.",
            "- **Analysis Depth** (A-F): Surface-level summary vs. insightful, specific analysis.",
            "- **Actionability** (A-F): Can a trader act on this? Specific numbers/levels = A.",
            "",
            "Output format (one line per analyst):",
            "ANALYST | COMPLETENESS | DEPTH | ACTIONABILITY | 1-sentence justification",
            "",
        ]
        for name, content in reports.items():
            snippet = (content or "")[:600]
            review_parts.append(f"--- {ANALYST_NAMES.get(name, name)} ---\n{snippet}\n")

        review_prompt = "\n".join(review_parts)
        resp = _quick_llm().chat([{"role": "user", "content": review_prompt}])
        review_text = resp.content or ""

        # Parse grades from LLM response
        for line in review_text.split("\n"):
            line = line.strip()
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                analyst_part = parts[0].lower()
                for key in reports:
                    if key in analyst_part or ANALYST_NAMES.get(key, "").lower() in analyst_part:
                        try:
                            grades_list = [p.strip().upper() for p in parts[1:4]]
                            score = sum(
                                5 if g == "A" else 4 if g == "B" else 3 if g == "C"
                                else 2 if g == "D" else 1
                                for g in grades_list if g in "ABCDF"
                            ) / 3
                            if score >= 4.5: llm_grades[key] = "A"
                            elif score >= 3.5: llm_grades[key] = "B"
                            elif score >= 2.5: llm_grades[key] = "C"
                            elif score >= 1.5: llm_grades[key] = "D"
                            else: llm_grades[key] = "F"
                        except Exception:
                            pass
                        break
    except Exception as exc:
        logger.warning("LLM quality review failed: %s", exc)

    # ── Merge grades ──
    final_grades = {}
    failures = []
    for name in reports:
        h = hard_grades.get(name, "C")
        l = llm_grades.get(name, h)
        # If hard check failed (D/F), LLM can't override — stays failed
        if h in ("D", "F"):
            final_grades[name] = h; failures.append(name)
        else:
            # Use LLM grade but don't let it drop below C on a passed hard check
            grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
            final = max(grade_order.get(l, 3), grade_order.get(h, 3))
            for g, v in grade_order.items():
                if v == final: final_grades[name] = g; break

    summary_parts = [f"Quality Gate — {symbol}"]
    for name in reports:
        h = hard_grades.get(name, "?")
        l = llm_grades.get(name, "—")
        f = final_grades.get(name, "?")
        analyst = ANALYST_NAMES.get(name, name)
        summary_parts.append(f"  {analyst}: {f} (hard={h}, llm={l})")
    if failures:
        summary_parts.append(f"  ⚠ Flagged: {', '.join(ANALYST_NAMES.get(f, f) for f in failures)}")

    summary = "\n".join(summary_parts)
    logger.info("Quality gate: hard_fail=%s llm_reviewed=%d",
                failures, len(llm_grades))
    complete_step("quality_gate")

    return {
        "data_quality_summary": summary,
        "sender": "quality_gate",
    }


# ============================================================================
# Phase 2b: Bull / Bear Debate
# ============================================================================

def _debate_context(state: dict[str, Any]) -> dict[str, Any]:
    debate = state.get("investment_debate_state", {})
    return {
        **_base_context(state),
        "market_report": state.get("market_report", ""),
        "sentiment_report": state.get("sentiment_report", ""),
        "news_report": state.get("news_report", ""),
        "fundamentals_report": state.get("fundamentals_report", ""),
        "policy_report": state.get("policy_report", ""),
        "hot_money_report": state.get("hot_money_report", ""),
        "lockup_report": state.get("lockup_report", ""),
        "data_quality_summary": state.get("data_quality_summary", ""),
        "history": debate.get("history", ""),
        "current_response": debate.get("current_response", ""),
    }


def bull_researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("bull_researcher")
    ctx = _debate_context(state)
    prompt = render_prompt("bull_researcher.j2", **ctx)
    response = _quick_llm().chat([{"role": "user", "content": prompt}])
    argument = f"Bull Analyst: {response.content}"

    debate = state.get("investment_debate_state", {})
    new_debate = {
        "history": debate.get("history", "") + "\n" + argument,
        "bull_history": debate.get("bull_history", "") + "\n" + argument,
        "bear_history": debate.get("bear_history", ""),
        "current_response": argument,
        "count": debate.get("count", 0) + 1,
        "judge_decision": "",
    }
    logger.info("Bull researcher: round %d", new_debate["count"])
    complete_step("bull_researcher")
    return {"investment_debate_state": new_debate, "sender": "bull_researcher"}


def bear_researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("bear_researcher")
    ctx = _debate_context(state)
    prompt = render_prompt("bear_researcher.j2", **ctx)
    response = _quick_llm().chat([{"role": "user", "content": prompt}])
    argument = f"Bear Analyst: {response.content}"

    debate = state.get("investment_debate_state", {})
    new_debate = {
        "history": debate.get("history", "") + "\n" + argument,
        "bear_history": debate.get("bear_history", "") + "\n" + argument,
        "bull_history": debate.get("bull_history", ""),
        "current_response": argument,
        "count": debate.get("count", 0) + 1,
        "judge_decision": "",
    }
    logger.info("Bear researcher: round %d", new_debate["count"])
    complete_step("bear_researcher")
    return {"investment_debate_state": new_debate, "sender": "bear_researcher"}


# ============================================================================
# Phase 2c: Research Manager (deep think)
# ============================================================================

def research_manager_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("research_manager")
    debate = state.get("investment_debate_state", {})
    ctx = {
        **_base_context(state),
        "debate_history": debate.get("history", ""),
        "judge_decision": debate.get("judge_decision", ""),
    }
    prompt = render_prompt("research_manager.j2", **ctx)

    # Structured output via JSON schema
    schema = ResearchPlan.model_json_schema()
    result = _deep_llm().structured(
        [{"role": "user", "content": prompt}], schema, schema_name="research_plan"
    )

    try:
        plan = ResearchPlan.model_validate(result)
        md = render_research_plan(plan)
        rec_str = plan.recommendation.value
    except Exception:
        md = result.get("rationale", "") or str(result)
        rec_str = result.get("recommendation", "unknown") if isinstance(result, dict) else "unknown"
        logger.warning("Research manager: structured output fallback")

    logger.info("Research manager: recommendation=%s", rec_str)
    complete_step("research_manager")
    return {"investment_plan": md, "sender": "research_manager"}


# ============================================================================
# Phase 3: Trader
# ============================================================================

def trader_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("trader")
    ctx = {
        **_base_context(state),
        "investment_plan": state.get("investment_plan", ""),
    }
    prompt = render_prompt("trader.j2", **ctx)

    schema = TraderProposal.model_json_schema()
    result = _quick_llm().structured(
        [{"role": "user", "content": prompt}], schema, schema_name="trader_proposal"
    )

    try:
        proposal = TraderProposal.model_validate(result)
        md = render_trader_proposal(proposal)
        action_str = proposal.action.value
    except Exception:
        md = result.get("reasoning", "") or str(result)
        action_str = result.get("action", "unknown") if isinstance(result, dict) else "unknown"

    logger.info("Trader: action=%s", action_str)
    complete_step("trader")
    return {"trader_investment_plan": md, "sender": "trader"}


# ============================================================================
# Phase 4: Three-way Risk Debate
# ============================================================================

def _risk_context(state: dict[str, Any]) -> dict[str, Any]:
    risk = state.get("risk_debate_state", {})
    return {
        **_base_context(state),
        "investment_plan": state.get("investment_plan", ""),
        "trader_plan": state.get("trader_investment_plan", ""),
        "history": risk.get("history", ""),
        "current_response": risk.get("current_aggressive_response", ""),
    }


def aggressive_risk_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("aggressive_risk")
    ctx = _risk_context(state)
    risk = state.get("risk_debate_state", {})
    ctx["current_response"] = risk.get("current_conservative_response", "")

    prompt = render_prompt("risk_aggressive.j2", **ctx)
    response = _quick_llm().chat([{"role": "user", "content": prompt}])
    argument = f"Aggressive Analyst: {response.content}"

    new_risk = {
        "aggressive_history": risk.get("aggressive_history", "") + "\n" + argument,
        "conservative_history": risk.get("conservative_history", ""),
        "neutral_history": risk.get("neutral_history", ""),
        "history": risk.get("history", "") + "\n" + argument,
        "latest_speaker": "aggressive",
        "current_aggressive_response": argument,
        "current_conservative_response": risk.get("current_conservative_response", ""),
        "current_neutral_response": risk.get("current_neutral_response", ""),
        "judge_decision": "",
        "count": risk.get("count", 0) + 1,
    }
    complete_step("aggressive_risk")
    return {"risk_debate_state": new_risk, "sender": "aggressive_risk"}


def conservative_risk_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("conservative_risk")
    ctx = _risk_context(state)
    risk = state.get("risk_debate_state", {})
    ctx["current_response"] = risk.get("current_aggressive_response", "")

    prompt = render_prompt("risk_conservative.j2", **ctx)
    response = _quick_llm().chat([{"role": "user", "content": prompt}])
    argument = f"Conservative Analyst: {response.content}"

    new_risk = {
        "aggressive_history": risk.get("aggressive_history", ""),
        "conservative_history": risk.get("conservative_history", "") + "\n" + argument,
        "neutral_history": risk.get("neutral_history", ""),
        "history": risk.get("history", "") + "\n" + argument,
        "latest_speaker": "conservative",
        "current_aggressive_response": risk.get("current_aggressive_response", ""),
        "current_conservative_response": argument,
        "current_neutral_response": risk.get("current_neutral_response", ""),
        "judge_decision": "",
        "count": risk.get("count", 0) + 1,
    }
    complete_step("conservative_risk")
    return {"risk_debate_state": new_risk, "sender": "conservative_risk"}


def neutral_risk_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("neutral_risk")
    ctx = _risk_context(state)
    risk = state.get("risk_debate_state", {})
    ctx["current_response"] = risk.get("current_conservative_response", "")

    prompt = render_prompt("risk_neutral.j2", **ctx)
    response = _quick_llm().chat([{"role": "user", "content": prompt}])
    argument = f"Neutral Analyst: {response.content}"

    new_risk = {
        "aggressive_history": risk.get("aggressive_history", ""),
        "conservative_history": risk.get("conservative_history", ""),
        "neutral_history": risk.get("neutral_history", "") + "\n" + argument,
        "history": risk.get("history", "") + "\n" + argument,
        "latest_speaker": "neutral",
        "current_aggressive_response": risk.get("current_aggressive_response", ""),
        "current_conservative_response": risk.get("current_conservative_response", ""),
        "current_neutral_response": argument,
        "judge_decision": "",
        "count": risk.get("count", 0) + 1,
    }
    complete_step("neutral_risk")
    return {"risk_debate_state": new_risk, "sender": "neutral_risk"}


# ============================================================================
# Phase 4b: Portfolio Manager (deep think) — Final Decision
# ============================================================================

def portfolio_manager_node(state: dict[str, Any]) -> dict[str, Any]:
    start_step("portfolio_manager")
    risk = state.get("risk_debate_state", {})
    past_context = state.get("past_context", "")
    lessons_line = ""

    if past_context:
        lessons_line = f"- Lessons from prior decisions:\n{past_context}\n"

    symbol = state.get("company_of_interest", "")
    market = _market_name(state.get("market", "a_stock"))

    ctx = {
        "symbol": symbol,
        "trade_date": state.get("trade_date", ""),
        "market": market,
        "instrument_context": f"Trading analysis for {symbol} on {market} market.",
        "investment_plan": state.get("investment_plan", ""),
        "trader_plan": state.get("trader_investment_plan", ""),
        "history": risk.get("history", ""),
        "lessons_line": lessons_line,
        "language_instruction": _lang_instruction(),
    }

    prompt = render_prompt("portfolio_manager.j2", **ctx)

    schema = PortfolioDecision.model_json_schema()
    result = _deep_llm().structured(
        [{"role": "user", "content": prompt}], schema, schema_name="portfolio_decision"
    )

    try:
        decision = PortfolioDecision.model_validate(result)
        md = render_pm_decision(decision)
        rating_str = decision.rating.value
    except Exception:
        md = result.get("investment_thesis", "") or str(result)
        rating_str = result.get("rating", "unknown") if isinstance(result, dict) else "unknown"
        logger.warning("Portfolio manager: structured output fallback")

    logger.info("Portfolio manager: rating=%s", rating_str)
    complete_step("portfolio_manager")
    return {"final_trade_decision": md, "sender": "portfolio_manager"}
