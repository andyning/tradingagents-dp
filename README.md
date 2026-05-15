# TradingAgents

Multi-agent LLM investment analysis framework. 7 specialist analysts debate, a portfolio manager decides. A-shares, Hong Kong, and US markets.

> Based on [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) — simplified and adapted for DeepSeek only.

```
7 Analysts → Quality Gate → Bull/Bear Debate → Research Manager
→ Trader → Risk Debate → Portfolio Manager
```

## Quick Start

### Requirements

- Python 3.10+
- A [DeepSeek API key](https://platform.deepseek.com)

### Install

```powershell
# 1. Run the install script
.\install.ps1

# 2. Add your API key to .env
notepad .env
```

Or manually:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -e .
```

### Configure

Edit `.env`:

```env
DEEPSEEK_API_KEY=sk-your-key-here
```

All other settings have sensible defaults.

### Futu OpenD (recommended — fast, free, multi-market)

[Futu OpenAPI](https://support.futunn.com/topic464) provides free real-time and historical data for A-shares, HK, and US stocks. No account or deposit required.

1. Download **Futu_OpenD-GUI** from [https://support.futunn.com/topic464](https://support.futunn.com/topic464)
2. Install and launch OpenD — login with your phone number (no brokerage account needed)
3. A F icon appears in the system tray — OpenD is running on `localhost:11111`

When OpenD is running, it automatically becomes the primary data source. If not running, the system falls back to Baostock/akshare/efinance/yfinance.

### Run

```powershell
# Web dashboard (recommended)
tradingagents-web

# CLI
tradingagents -s 600519 -d 2026-05-15

# REST API
tradingagents-api
# → http://localhost:8000/docs
```

## Analysis Depth

Three tiers for speed vs thoroughness:

| Mode | Steps | Time | Best for |
|------|-------|------|----------|
| **Light** | 5 | ~2 min | Quick scan, candidate screening |
| **Medium** | 13 | ~8 min | Daily decisions, weekly review |
| **Deep** | 16 | ~12 min | Large positions, high uncertainty |

**Light**: Market/Tech → Fundamentals → News → Research Manager → Portfolio Manager

**Medium**: 7 Analysts → Quality Gate → Bull/Bear Debate → Research Manager → Trader → Portfolio Manager

**Deep**: Full pipeline with three-way risk debate (Aggressive / Conservative / Neutral)

## Architecture

```
tradingagents/
├── config.py              # Pydantic Settings (reads .env)
├── exceptions.py          # Unified exception hierarchy
├── logging.py             # structlog structured logging
├── llm/client.py          # DeepSeek (quick + deep think)
├── data/
│   ├── a_stock.py         # A-share (Baostock → efinance → akshare fallback)
│   ├── hk_stock.py        # Hong Kong (efinance → yfinance)
│   ├── us_stock.py        # US (yfinance → efinance)
│   ├── schema.py          # Pydantic data validation
│   ├── cache.py           # Parquet local cache
│   ├── retry.py           # Exponential backoff + multi-source fallback
│   └── sources/           # Data source adapters
├── agents/
│   ├── base.py            # Agent base class
│   ├── schemas.py         # Pydantic inter-agent contracts
│   └── prompts/           # 15 Jinja2 prompt templates
├── graph/
│   ├── builder.py         # LangGraph topology (3 depth modes)
│   ├── nodes.py           # Node functions
│   ├── state.py           # AgentState TypedDict
│   ├── data_context.py    # Pre-fetch real data per analyst
│   └── progress.py        # Thread-safe progress tracker
├── backtesting/           # Backtrader engine + A-stock rules
├── cli/                   # Typer + Rich terminal UI
└── web/                   # FastAPI + Streamlit dashboard
```

### Data Sources

All free. No registration needed. Futu OpenD recommended for best speed.

| Market | Primary | Secondary | Tertiary | Fallback |
|--------|---------|-----------|----------|----------|
| A-Share | Futu | Baostock | efinance | yfinance |
| Hong Kong | Futu | akshare | efinance | yfinance |
| US | Futu | akshare | efinance | yfinance |

Futu OpenD must be running locally. If not, the chain auto-falls back.

### LLM

DeepSeek only (via OpenAI-compatible SDK). Two reasoning tiers:

- **Quick think** (`deepseek-chat`): Analysts, debaters, trader
- **Deep think** (`deepseek-reasoner`): Research Manager, Portfolio Manager

## Python API

```python
from tradingagents.graph import TradingAgentsGraph

graph = TradingAgentsGraph()
state, decision = graph.propagate(
    "600519",           # ticker
    "2026-05-15",       # date
    market="a_stock",
    depth="medium",     # light / medium / deep
)
print(decision)
```

## Backtesting

```python
from tradingagents.backtesting.engine import run_backtest
from tradingagents.backtesting.reporter import generate_report

metrics = run_backtest("600519", "2024-01-01", "2024-12-31")
print(generate_report(metrics))
```

A-stock rules modeled: T+1 settlement, price limits (±10%/±20%/±5%), minimum lot sizes (100/200 shares), commission (0.025%) and stamp duty (0.05% sell only).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | Your API key (required) |
| `TA_LLM_BASE_URL` | `https://api.deepseek.com` | Endpoint override |
| `TA_ANALYSIS_DEPTH` | `medium` | `light` / `medium` / `deep` |
| `TA_MAX_DEBATE_ROUNDS` | `1` | Bull/Bear rounds |
| `TA_MAX_RISK_DISCUSS_ROUNDS` | `1` | Risk debate rounds |
| `TA_OUTPUT_LANGUAGE` | `Chinese` | Report language |
| `TA_DATA_CACHE_DIR` | `~/.tradingagents/cache` | Data cache |
| `TA_RESULTS_DIR` | `~/.tradingagents/results` | Saved reports |

## Disclaimer

This project is for educational and research purposes only. It does not constitute investment advice. All analysis reports are AI-generated and may contain errors. Consult licensed professionals for investment decisions.

## Credits

This project is based on [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents), a multi-agent LLM trading framework (Apache 2.0). It has been simplified and adapted to work exclusively with DeepSeek.

Key modifications:
- Stripped LLM layer to DeepSeek only (removed 10+ providers)
- Rewrote data layer with Baostock/efinance/akshare/yfinance and multi-level fallback
- Extracted prompts to Jinja2 templates with real data pre-fetching
- Added three analysis depths (Light/Medium/Deep)
- Professional web dashboard with progress tracking and token statistics

Original paper: [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)

## License

Apache 2.0
