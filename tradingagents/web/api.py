"""FastAPI REST API for the TradingAgents analysis pipeline."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tradingagents.config import get_settings
from tradingagents.graph import TradingAgentsGraph
from tradingagents.logging import setup_logging

setup_logging()

app = FastAPI(
    title="TradingAgents API",
    description="Multi-agent A-share investment analysis",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Request / Response models ----

class AnalysisRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker (e.g. 600519)")
    trade_date: str = Field(..., description="Analysis date YYYY-MM-DD")
    market: str = Field(default="a_stock", description="Market: a_stock, hk_stock, us_stock")
    debug: bool = False


class AnalysisResponse(BaseModel):
    symbol: str
    trade_date: str
    rating: str
    decision: str
    market_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    fundamentals_report: str = ""
    policy_report: str = ""
    hot_money_report: str = ""
    lockup_report: str = ""
    investment_plan: str = ""
    trader_plan: str = ""
    final_trade_decision: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.3.0"


# ---- Endpoints ----

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(req: AnalysisRequest):
    """Run the full multi-agent analysis pipeline for a stock."""
    try:
        graph = TradingAgentsGraph(debug=req.debug)
        state, decision = graph.propagate(req.symbol, req.trade_date, market=req.market)

        rating = _extract_rating(decision)

        return AnalysisResponse(
            symbol=req.symbol,
            trade_date=req.trade_date,
            rating=rating,
            decision=decision,
            market_report=state.get("market_report", ""),
            sentiment_report=state.get("sentiment_report", ""),
            news_report=state.get("news_report", ""),
            fundamentals_report=state.get("fundamentals_report", ""),
            policy_report=state.get("policy_report", ""),
            hot_money_report=state.get("hot_money_report", ""),
            lockup_report=state.get("lockup_report", ""),
            investment_plan=state.get("investment_plan", ""),
            trader_plan=state.get("trader_investment_plan", ""),
            final_trade_decision=decision,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _extract_rating(text: str) -> str:
    for r in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
        if r.lower() in text.lower():
            return r
    return "Unknown"


def main():
    """Entry point for `tradingagents-api`."""
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "tradingagents.web.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
