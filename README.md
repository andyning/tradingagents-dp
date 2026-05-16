# TradingAgents-dp

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
.\install.ps1
notepad .env          # add your DeepSeek key
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

### Futu OpenD (recommended — fast, multi-market)

[Futu OpenAPI](https://support.futunn.com/topic464) provides real-time and historical data for A-shares, HK, and US stocks. No brokerage account required.

1. Download **Futu_OpenD-GUI** from [https://support.futunn.com/topic464](https://support.futunn.com/topic464)
2. Install and launch OpenD — login with phone number
3. F icon appears in system tray — OpenD runs on `localhost:11111`

Starting quota (no deposit): 100 subscriptions + 100 K-line requests per session. Sufficient for personal use. Quota can be increased by depositing funds or trading via Futu. When limit is hit, the system auto-falls back to Baostock/akshare/efinance/yfinance.

### Run

```powershell
tradingagents-web      # Web dashboard (recommended)
tradingagents -s 600519 -d 2026-05-15   # CLI
tradingagents-api                         # REST API → http://localhost:8000/docs
```

## Features

### Analysis Pipeline

| Mode | Steps | Time | Best for |
|------|-------|------|----------|
| **Light** | 5 | ~2 min | Quick scan, screening |
| **Medium** | 13 | ~8 min | Daily decisions, review |
| **Deep** | 16 | ~12 min | Large positions, high uncertainty |

### Dashboard

Professional financial dashboard with:
- **14 stock metrics**: Symbol, Name, Price, Change, PE-TTM, Forward PE, Turnover, Market Cap, Amount, Volume Ratio, Float Shares, Total Shares, Profitability, PB
- **Interactive K-line chart**: candlestick + volume, red-up/green-down (Chinese convention)
- **Analyst Voting Table**: 7 analysts each output `[DIRECTION]` + `[KPI]` structured line, tally shown as "Bull N · Bear M · Neutral K"
- **Portfolio Manager Decision Summary**: structured table from SignalProcessor (rating, confidence, risk score, reasoning, position advice, time horizon)
- **Multi-strategy backtest**: MA crossover, MACD signal cross, RSI mean-reversion compared side-by-side
- **Industry PE comparison**: percentile ranking vs peer stocks
- **Real-time progress**: per-step status with token tracking
- **Report export**: one-click Markdown download
- **Result caching**: auto-loads previous analysis for same symbol+depth, saves tokens
- **Session persistence**: last symbol/depth/window restored on reload

### Memory & Reflection

Each analysis stores structured results (rating, confidence, KPIs) to a per-ticker JSON file. Before the next analysis, past records are retrieved and injected as context. An LLM-based reflection generator produces structured lessons (Reasoning, Lesson, Watch) stored alongside each decision.

### Data Sources

Baostock/akshare/efinance are free with no registration. Futu requires OpenD login (no brokerage account needed) with a starting quota of 100 requests/session. IB requires a Paper or Live trading account with IB Gateway running locally. yfinance is free but often rate-limited in China.

| Market | Primary | Secondary | Tertiary | Fallback |
|--------|---------|-----------|----------|----------|
| A-Share | Futu | Baostock | efinance | yfinance |
| Hong Kong | Futu | IB | akshare | efinance |
| US | IB | Futu | akshare | efinance |

IB requires [IB Gateway](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php) running locally with Paper Trading account (port 4002).

Market auto-detected from ticker format: 6-digit → A-share, 4-5 digit → HK, alphabetic → US. Data Sources Status panel shows real-time ON/OFF indicators.

### LLM

DeepSeek only (via OpenAI-compatible SDK). Two reasoning tiers:

- **Quick think** (`deepseek-chat`): Analysts, debaters, trader
- **Deep think** (`deepseek-reasoner`): Research Manager, Portfolio Manager

## Architecture

```
tradingagents/
├── config.py              # Pydantic Settings (reads .env)
├── exceptions.py          # Unified exception hierarchy
├── logging.py             # structlog structured logging
├── llm/client.py          # DeepSeek (quick + deep think)
├── data/
│   ├── a_stock.py         # A-share (Futu → Baostock → efinance → yfinance)
│   ├── hk_stock.py        # Hong Kong (Futu → akshare → efinance → yfinance)
│   ├── us_stock.py        # US (Futu → akshare → efinance → yfinance)
│   ├── schema.py          # Pydantic data validation
│   ├── cache.py           # Parquet local cache + negative cache
│   ├── retry.py           # Exponential backoff + multi-source fallback
│   └── sources/           # futu, baostock, efinance, akshare, yfinance
├── agents/
│   ├── base.py            # Agent base class
│   ├── schemas.py         # Pydantic inter-agent contracts
│   └── prompts/           # 15 Jinja2 templates ([DIRECTION]/[KPI] structured output)
├── graph/
│   ├── builder.py         # LangGraph topology (3 depth modes)
│   ├── nodes.py           # Node functions with LLM retry
│   ├── state.py           # AgentState TypedDict
│   ├── data_context.py    # Pre-fetch real data per analyst + backtest + industry
│   ├── progress.py        # Thread-safe progress tracker
│   ├── signal_processor.py # Structured JSON extraction (14 regex patterns)
│   ├── memory_store.py    # JSON-based analysis memory + LLM reflection
│   └── news_filter.py     # Relevance scoring + dedup
├── backtesting/           # Backtrader engine + A-stock rules
├── cli/                   # Typer + Rich terminal UI
└── web/                   # FastAPI + Streamlit dashboard
```

## Python API

```python
from tradingagents.graph import TradingAgentsGraph

graph = TradingAgentsGraph()
state, decision, signal = graph.propagate(
    "600519",           # ticker
    "2026-05-15",       # date
    market="a_stock",
    depth="medium",     # light / medium / deep
)
print(signal["action"])  # Buy / Hold / Sell
print(signal["confidence"])  # 0.85
```

## Backtesting

```python
from tradingagents.backtesting.engine import run_backtest
from tradingagents.backtesting.reporter import generate_report

metrics = run_backtest("600519", "2024-01-01", "2024-12-31")
print(generate_report(metrics))
```

A-stock rules: T+1 settlement, price limits (±10%/±20%/±5%), minimum lot (100/200), commission (0.025%), stamp duty (0.05% sell only).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | Your API key (required) |
| `TA_LLM_BASE_URL` | `https://api.deepseek.com` | Endpoint override |
| `TA_ANALYSIS_DEPTH` | `medium` | `light` / `medium` / `deep` |
| `TA_DATA_WINDOW` | `120` | Trading days to analyze |
| `TA_MAX_DEBATE_ROUNDS` | `1` | Bull/Bear rounds |
| `TA_MAX_RISK_DISCUSS_ROUNDS` | `1` | Risk debate rounds |
| `TA_OUTPUT_LANGUAGE` | `Chinese` | Report language |
| `TA_DATA_CACHE_DIR` | `~/.tradingagents/cache` | Data cache |
| `TA_RESULTS_DIR` | `~/.tradingagents/results` | Saved reports |

## Credits

Based on [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache 2.0), simplified and adapted for DeepSeek only.

Key modifications:
- LLM layer stripped to DeepSeek only
- Data layer rewritten with Futu/Baostock/efinance/akshare/yfinance + multi-level fallback
- 15 structured Jinja2 prompt templates with `[DIRECTION]/[KPI]` output format
- Three analysis depths (Light/Medium/Deep)
- Professional dashboard with analyst voting, decision summary, multi-strategy backtest
- SignalProcessor: 14 regex patterns + LLM extraction for structured decisions
- Memory system with LLM-based reflection learning
- Market auto-detection, session persistence, data source health status

Original paper: [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)

## License

Apache 2.0
