"""Progress and token tracking for the analysis pipeline.

Thread-safe singleton updated by graph nodes, polled by UI.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

# Steps per analysis depth
STEPS_LIGHT = [
    "market_analyst",
    "fundamentals_analyst",
    "news_analyst",
    "research_manager",
    "portfolio_manager",
]

STEPS_MEDIUM = [
    "market_analyst",
    "social_analyst",
    "news_analyst",
    "fundamentals_analyst",
    "policy_analyst",
    "hot_money_analyst",
    "lockup_analyst",
    "quality_gate",
    "bull_researcher",
    "bear_researcher",
    "research_manager",
    "trader",
    "portfolio_manager",
]

STEPS_DEEP = [
    "market_analyst",
    "social_analyst",
    "news_analyst",
    "fundamentals_analyst",
    "policy_analyst",
    "hot_money_analyst",
    "lockup_analyst",
    "quality_gate",
    "bull_researcher",
    "bear_researcher",
    "research_manager",
    "trader",
    "aggressive_risk",
    "conservative_risk",
    "neutral_risk",
    "portfolio_manager",
]

STEP_LABELS = {
    "market_analyst": "Market / Technical Analysis",
    "social_analyst": "Social Sentiment",
    "news_analyst": "News & Macro",
    "fundamentals_analyst": "Fundamentals",
    "policy_analyst": "Policy Analysis",
    "hot_money_analyst": "Hot Money / Flow",
    "lockup_analyst": "Lockup / Insider",
    "quality_gate": "Quality Gate",
    "bull_researcher": "Bull Analyst",
    "bear_researcher": "Bear Analyst",
    "research_manager": "Research Manager",
    "trader": "Trader",
    "aggressive_risk": "Aggressive Risk",
    "conservative_risk": "Conservative Risk",
    "neutral_risk": "Neutral Risk",
    "portfolio_manager": "Portfolio Manager",
}

DEPTH_STEPS = {"light": STEPS_LIGHT, "medium": STEPS_MEDIUM, "deep": STEPS_DEEP}


@dataclass
class PipelineProgress:
    current_step: str = ""
    completed_steps: list[str] = field(default_factory=list)
    step_results: dict[str, object] = field(default_factory=dict)
    total_steps: int = 16
    steps: list[str] = field(default_factory=lambda: STEPS_MEDIUM.copy())
    depth: str = "medium"
    running: bool = False
    finished: bool = False
    error: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    symbol: str = ""
    trade_date: str = ""
    market: str = ""

    @property
    def progress_pct(self) -> float:
        return len(self.completed_steps) / self.total_steps * 100

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


_progress: Optional[PipelineProgress] = None
_lock = threading.Lock()
_on_update: Optional[Callable[[PipelineProgress], None]] = None


def get_progress() -> PipelineProgress:
    global _progress
    with _lock:
        if _progress is None:
            _progress = PipelineProgress()
        return _progress


def reset_progress(depth: str = "medium") -> PipelineProgress:
    global _progress
    with _lock:
        steps = DEPTH_STEPS.get(depth, STEPS_MEDIUM)
        _progress = PipelineProgress(steps=list(steps), total_steps=len(steps), depth=depth)
        from tradingagents.llm.client import reset_token_stats
        reset_token_stats()
        return _progress


def start_step(step_name: str) -> PipelineProgress:
    p = get_progress()
    with _lock:
        p.current_step = step_name
        p.running = True
    return p


def complete_step(step_name: str, result: str = "", tokens_in: int = 0, tokens_out: int = 0) -> PipelineProgress:
    p = get_progress()
    with _lock:
        if step_name not in p.completed_steps:
            p.completed_steps.append(step_name)
        if result:
            p.step_results[step_name] = result
        p.current_step = ""
        # Pull token stats
        from tradingagents.llm.client import token_stats
        ts = token_stats()
        p.tokens_in = ts["tokens_in"]
        p.tokens_out = ts["tokens_out"]
    if _on_update:
        _on_update(p)
    return p


def finish(error: str = "") -> PipelineProgress:
    p = get_progress()
    with _lock:
        p.running = False
        p.finished = True
        p.error = error
        p.current_step = ""
    if _on_update:
        _on_update(p)
    return p


def set_on_update(callback: Callable[[PipelineProgress], None]) -> None:
    global _on_update
    _on_update = callback
