# TradingAgents-dp

Multi-agent LLM investment analysis framework.  7 specialist analysts debate,
a portfolio manager decides.  A-shares, Hong Kong, and US markets.

> Based on [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
> (Apache 2.0), simplified and adapted for DeepSeek only.

```
7 Analysts → Quality Gate → Bull/Bear Debate → Research Manager
→ Trader → Risk Debate → Portfolio Manager
```

## Quick Start

### Requirements

- Python 3.10+
- A [DeepSeek API key](https://platform.deepseek.com)

### Install

**Windows (PowerShell):**
```powershell
.\install.ps1
```
**macOS / Linux:**
```bash
bash install.sh
```

This creates a virtual environment, installs dependencies, and sets up `.env`.

**Manual install** (any OS):
```bash
python3 -m venv venv
source venv/bin/activate      # Windows: .\venv\Scripts\activate
pip install -e .
```

### Configure

Edit `.env` and add your key:

```env
DEEPSEEK_API_KEY=sk-your-key-here
```

If you skip this step, you can set the key later via the **Settings** page in the
web UI (gear icon, top-left).

All other settings have sensible defaults.

### Run

```bash
tradingagents-web                         # Web dashboard (recommended)
tradingagents -s 600519 -d 2026-05-15     # CLI
tradingagents-api                         # REST API → http://localhost:8000/docs
```

Open http://localhost:8501 in your browser.

## Features

### Analysis Pipeline

| Mode   | Steps | Time   | Best for                          |
|--------|-------|--------|-----------------------------------|
| Light  | 5     | ~2 min | Quick scan, screening             |
| Medium | 13    | ~8 min | Daily decisions, review           |
| Deep   | 16    | ~12 min| Large positions, high uncertainty |

### Dashboard

- **12 stock metrics**: Price, Change%, PE-TTM, PB, Market Cap, Turnover%, PE-动,
  成交额, 量比, 流通股, 总股本, 盈利?
- **Interactive K-line chart**: candlestick + volume, red-up/green-down
- **7-Analyst Reports table**: analyst name, data input, key finding per row
- **Decision Chain summary**: Quality Gate → Bull/Bear Debate → Research Manager →
  Trader → Risk Debate → Portfolio Manager
- **Portfolio Manager Decision card**: structured table with rating, confidence,
  reasoning, risk assessment
- **Multi-strategy backtest**: MA crossover, MACD signal cross, RSI mean-reversion
- **Real-time progress**: per-step status with token tracking (input/output/total)
- **Analysis history**: auto-saved per run, browsable table with PDF export
- **Settings page**: DeepSeek key, Futu/IB toggles (default OFF)
- **Result caching**: auto-loads previous analysis for same symbol+depth
- **Session persistence**: last symbol/depth/window restored on reload

### Data Sources

Pure HTTP architecture.  No registration, no local software required.
Futu/IB are optional last-resort fallbacks, disabled by default.

| Market     | Primary    | Secondary  | Tertiary | Last Resort  |
|------------|------------|------------|----------|--------------|
| A-Share    | Tencent    | Eastmoney  | Yahoo    | Futu         |
| Hong Kong  | Tencent    | Eastmoney  | Yahoo    | Futu / IB    |
| US         | Yahoo      | Eastmoney  | —        | Futu / IB    |

- **Tencent Finance** (`qt.gtimg.cn`) — free, no auth, fast.  K-line (daily/weekly/monthly)
  and real-time quotes covering A-shares and HK stocks.
- **Eastmoney** (`eastmoney.com`) — free, comprehensive A/HK/US data including
  fund flow, northbound flow, news, and financial snapshots.
- **Yahoo Finance** — US stock K-line and quotes via the `yfinance` library.
  May be rate-limited or blocked in mainland China.

**Proxy**: The system auto-detects the Windows proxy from registry.  Per-domain
connectivity is probed on first use and cached — direct connection preferred,
proxy used as fallback.  Click Refresh to re-detect.

**Futu / IB**: Disabled by default.  Enable in Settings → Refresh.  When enabled,
they sit at the end of the fallback chain and only activate if HTTP sources fail.

### LLM

DeepSeek only (via OpenAI-compatible SDK).  Two reasoning tiers:

- **Quick think** (`deepseek-chat`): Analysts, debaters, trader
- **Deep think** (`deepseek-reasoner`): Research Manager, Portfolio Manager

API key priority: `.env DEEPSEEK_API_KEY` > **Settings** page UI input > empty.

## Architecture

```
tradingagents/
├── config.py               # Pydantic Settings (reads .env)
├── exceptions.py           # Unified exception hierarchy
├── logging.py              # structlog structured logging
├── llm/client.py           # DeepSeek client (quick + deep think)
├── data/
│   ├── a_stock.py          # A-share (Tencent → Eastmoney → Yahoo → Futu)
│   ├── hk_stock.py         # Hong Kong (Tencent → Eastmoney → Yahoo → Futu/IB)
│   ├── us_stock.py         # US (Yahoo → Eastmoney → Futu/IB)
│   ├── schema.py           # Pydantic data validation
│   ├── cache.py            # Parquet local cache
│   ├── retry.py            # Exponential backoff + multi-source fallback chain
│   ├── http/               # Pure HTTP data sources (Tencent, Eastmoney, Yahoo)
│   └── sources/            # Futu / IB adapters (optional, last resort)
├── agents/
│   ├── base.py             # Agent base class
│   ├── schemas.py          # Pydantic inter-agent contracts
│   └── prompts/            # 15 Jinja2 templates ([DIRECTION]/[KPI] output)
├── graph/
│   ├── builder.py          # LangGraph topology (3 depth modes)
│   ├── nodes.py            # Node functions with LLM retry
│   ├── state.py            # AgentState TypedDict
│   ├── data_context.py     # Pre-fetch real data per analyst
│   ├── progress.py         # Thread-safe progress tracker
│   ├── signal_processor.py # Structured JSON extraction
│   ├── memory_store.py     # JSON-based analysis memory + LLM reflection
│   └── news_filter.py      # Relevance scoring + dedup
├── backtesting/            # Backtrader engine + A-stock rules
├── cli/                    # Typer + Rich terminal UI
└── web/                    # Streamlit dashboard
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
print(signal["action"])       # Buy / Overweight / Hold / Underweight / Sell
print(signal["confidence"])   # 0.85
```

## Configuration

| Variable              | Default                        | Description                  |
|-----------------------|--------------------------------|------------------------------|
| `DEEPSEEK_API_KEY`    | —                              | Your API key (required)      |
| `TA_LLM_BASE_URL`     | `https://api.deepseek.com`     | Endpoint override            |
| `TA_PROXY_URL`        | —                              | Force proxy for all HTTP     |
| `TA_ANALYSIS_DEPTH`   | `medium`                       | `light` / `medium` / `deep`  |
| `TA_DATA_WINDOW`      | `120`                          | Trading days to analyze      |
| `TA_MAX_DEBATE_ROUNDS`| `1`                            | Bull/Bear rounds             |
| `TA_OUTPUT_LANGUAGE`  | `Chinese`                      | Report language              |
| `TA_DATA_CACHE_DIR`   | `~/.tradingagents/cache`       | Data cache                   |
| `TA_RESULTS_DIR`      | `~/.tradingagents/results`     | Saved reports + history      |

## Changes from Original TradingAgents

- **Data layer**: Replaced Baostock/efinance/akshare/yfinance with pure HTTP
  sources (Tencent, Eastmoney, Yahoo via yfinance).  No library dependencies
  beyond `requests` + `yfinance`.
- **Per-domain connectivity**: Auto-detects direct vs proxy per host, with
  automatic fallback on connection errors.
- **UI redesign**: QuantDinger-inspired color system, page-based navigation
  (Dashboard / Settings / History), compact metric cards, dedicated Settings
  and History pages with PDF export.
- **Futu/IB optional**: Both disabled by default.  Enable in Settings when needed.
  System gracefully degrades when they are OFF.
- **Graceful degradation**: All data endpoints return empty DataFrames on failure
  instead of raising exceptions — the dashboard shows "—" for unavailable data.
- **Analysis history**: Auto-saved with per-run PDF export, browsable table.
- **LLM probe**: Health bar shows real-time DeepSeek connectivity.

Original paper: [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138)

## License

Apache 2.0
