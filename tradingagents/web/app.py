"""Streamlit Web UI — Professional Financial Dashboard.

Clean light theme, real-time step progress, token tracking, dashboard overview.
"""

from __future__ import annotations

# Print loading indicator ONCE (not on every Streamlit rerun)
import sys as _sys_boot, os as _os_boot
if _os_boot.environ.get("_TA_BOOTED") != "1":
    _os_boot.environ["_TA_BOOTED"] = "1"
    print("[TradingAgents] Loading...", file=_sys_boot.stderr, flush=True)

import json
import threading
import time
import warnings
from pathlib import Path

import pandas as pd
import streamlit as st

if _os_boot.environ.get("_TA_BOOTED_UI") != "1":
    _os_boot.environ["_TA_BOOTED_UI"] = "1"
    print("[TradingAgents] Streamlit loaded, starting UI...", file=_sys_boot.stderr, flush=True)

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed database.*")
warnings.filterwarnings("ignore", message=".*unclosed .*socket.*")

st.set_page_config(page_title="TradingAgents", page_icon="", layout="wide", initial_sidebar_state="expanded")

# ── CSS ─────────────────────────────────────────────────────────────────
st.markdown("""<style>
	    /* ====== QD Color System ======
	       Primary:    #1890FF  Ant Design Blue
	       Bullish:    #00E676  Vivid Green
	       Bearish:    #FF5252  Vivid Red
	       Warning:    #faad14  Amber/Gold
	       Sidebar:    #001529  Ant Design dark sidebar
	       Card BG:    #ffffff
	       Page BG:    #f0f2f5
	    */
	    .stApp { background: #f0f2f5; font-size: 0.88rem; }
	    .main .block-container { padding: 1.5rem 2rem; max-width: 1400px; }
	    /* Sidebar - Ant Design Dark */
	    section[data-testid="stSidebar"] {
	        background: #001529; border-right: none; min-width: 24rem !important;
	    }
	    section[data-testid="stSidebar"] h3 {
	        color: #fff !important; font-size: 1.6rem !important; font-weight: 700 !important;
	        letter-spacing: .01em !important;
	    }
	    section[data-testid="stSidebar"] .stCaption {
	        color: rgba(255,255,255,.55) !important; font-size: 0.88rem !important;
	    }
	    section[data-testid="stSidebar"] .stMarkdown,
	    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span,
	    section[data-testid="stSidebar"] label,
	    section[data-testid="stSidebar"] div { color: rgba(255,255,255,.85) !important; }
	    section[data-testid="stSidebar"] .stMarkdown p strong {
	        color: #fff !important; font-weight: 600 !important; font-size: 0.92rem !important;
	    }
	    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12) !important; }
	    .ig-label { font-size: 0.75rem !important; color: rgba(255,255,255,.45) !important;
	        font-weight: 600 !important; text-transform: uppercase; letter-spacing: .08em;
	        margin: 10px 0 4px 0; }
	    h2, h3 { color: #1f1f1f; font-weight: 600; }
	    .mc {
	        background: #fff; border: 1px solid #f0f0f0; border-radius: 8px;
	        padding: 16px 20px; box-shadow: 0 1px 2px rgba(0,0,0,.06);
	        transition: box-shadow .2s;
	    }
	    .mc:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
	    .mc .mcl { font-size: 0.75rem; color: #8c8c8c; text-transform: uppercase;
	        letter-spacing: .06em; font-weight: 500; margin-bottom: 4px; }
	    .mc .mcv { font-size: 1.75rem; font-weight: 700; color: #1f1f1f; }
	    .mc .mcs { font-size: 0.82rem; margin-top: 2px; color: #8c8c8c; }
	    .up { color: #FF5252 !important; } .down { color: #00E676 !important; }
	    .badge { display: inline-block; padding: 6px 24px; border-radius: 4px;
	        font-weight: 600; font-size: 1.1rem; letter-spacing: .02em; }
	    .badge-BUY { background: #f6ffed; color: #237804; border: 1px solid #b7eb8f; }
	    .badge-OVERWEIGHT { background: #e6f7ff; color: #096dd9; border: 1px solid #91d5ff; }
	    .badge-HOLD { background: #fffbe6; color: #ad6800; border: 1px solid #ffe58f; }
	    .badge-UNDERWEIGHT { background: #fff7e6; color: #d46b08; border: 1px solid #ffd591; }
	    .badge-SELL { background: #fff1f0; color: #cf1322; border: 1px solid #ffa39e; }
	    .srow { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
	    .sdot { width: 14px; text-align: center; font-size: 1.12rem; flex-shrink: 0; }
	    .slbl { font-size: 0.88rem; white-space: nowrap; }
	    .s-act .sdot { color: #1890FF; } .s-act .slbl { color: #1890FF; font-weight: 600; }
	    .s-done .sdot { color: #00E676; } .s-done .slbl { color: #00E676; }
	    .s-wait .sdot { color: #d9d9d9; } .s-wait .slbl { color: #bfbfbf; }
	    .tbox { text-align: center; padding: 8px 4px; background: rgba(255,255,255,.1);
	        border-radius: 6px; }
	    .tbox .tv { font-size: 1.1rem; font-weight: 700; color: #fff; }
	    .tbox .tl { font-size: 0.72rem; color: rgba(255,255,255,.45); text-transform: uppercase; }
	    .dash-panel {
	        background: #fff; border: 1px solid #f0f0f0; border-radius: 8px;
	        padding: 16px 20px; box-shadow: 0 1px 2px rgba(0,0,0,.06);
	        margin-bottom: 10px;
	    }
	    .dash-panel h4 { color: #1f1f1f; font-size: 1rem; font-weight: 600;
	        margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #f0f0f0; }
	    .dash-panel p { font-size: 0.92rem; color: #595959; line-height: 1.5; }
	    [data-baseweb="tab"] button,
	    [data-baseweb="tab"] p,
	    [data-baseweb="tab"] span,
	    button[data-baseweb="tab"] { font-size: 0.92rem !important; font-weight: 600 !important; }
	    .stTabs [data-baseweb="tab"] { font-size: 0.92rem !important; font-weight: 600 !important; }
	    .stTabs [data-baseweb="tab"][aria-selected="true"] { color: #1890FF !important; }
	    .stProgress > div > div > div > div { background: #1890FF; }
	    section[data-testid="stSidebar"] input[type="text"],
	    section[data-testid="stSidebar"] [data-baseweb="select"],
	    section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
	        border: 1px solid #434343 !important; border-radius: 6px !important;
	        background: #fff !important; color: #1f1f1f !important;
	    }
	    section[data-testid="stSidebar"] input[type="text"]::placeholder { color: #bfbfbf !important; }
	    section[data-testid="stSidebar"] [data-baseweb="select"] * { color: #1f1f1f !important; }
	    section[data-testid="stSidebar"] button[kind="primary"],
	    section[data-testid="stSidebar"] button[kind="secondary"] {
	        background: #1890FF !important; border-color: #1890FF !important; color: #fff !important;
	    }
	    section[data-testid="stSidebar"] button[kind="primary"]:hover,
	    section[data-testid="stSidebar"] button[kind="secondary"]:hover {
	        background: #40a9ff !important; border-color: #40a9ff !important;
	    }
	    .stButton button {
	        border-radius: 6px !important; font-size: 0.88rem !important; padding: 4px 16px !important;
	        color: #fff !important; border: 1px solid #1890FF !important;
	        background: #1890FF !important; font-weight: 500 !important;
	    }
	    .stButton button:hover { background: #40a9ff !important; border-color: #40a9ff !important; }
	    header, footer, #MainMenu,
	    [data-testid="stHeader"], [data-testid="stToolbar"],
	    [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
	    .health-dot-ok  { color: #00E676; }
	    .health-dot-down { color: #FF5252; }
	    .health-dot-unknown { color: #d9d9d9; }
	</style>""", unsafe_allow_html=True)

# ── Data source probes (single-threaded, each has internal timeout) ────

def _probe_futu():
    try:
        from tradingagents.data.sources.futu import _get_shared_futu
        return _get_shared_futu() is not None
    except Exception:
        return False


def _probe_ib():
    try:
        from tradingagents.data.sources.ib import _ensure_worker
        _ensure_worker()
        return True
    except Exception:
        return False


def _probe_tencent():
    """Probe Tencent Finance HTTP API — fast ping to qt.gtimg.cn."""
    try:
        import requests
        resp = requests.get("https://qt.gtimg.cn/q=sh600519", timeout=5)
        return resp.status_code == 200 and "~" in resp.text
    except Exception:
        return False


def _probe_eastmoney():
    """Probe Eastmoney HTTP API — verify K-line endpoint responds."""
    try:
        import requests
        resp = requests.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params={"secid": "1.600519", "klt": 101, "lmt": 1,
                    "fields1": "f1", "fields2": "f51"},
            timeout=5,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _probe_llm():
    """Probe DeepSeek API — quick connectivity check with 5s timeout."""
    try:
        from tradingagents.config import get_settings
        settings = get_settings()
        key = settings.deepseek_api_key
        if not key:
            return False
        import openai
        client = openai.OpenAI(api_key=key, base_url=settings.llm_base_url, timeout=5)
        client.chat.completions.create(
            model=settings.quick_think_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        return True
    except Exception:
        return False


def _probe_yahoo():
    """Probe Yahoo Finance HTTP API — quick chart data check."""
    try:
        from tradingagents.data.http.yahoo import fetch_kline
        rows = fetch_kline("AAPL", "us_stock", "1d", count=1, timeout=8)
        return len(rows) > 0
    except Exception:
        return False


# ── Health helpers ──────────────────────────────────────────────────────

HEALTH_HINTS = {
    "llm":       "Check DEEPSEEK_API_KEY in .env file and network connectivity.",
    "futu":      "Launch Futu OpenD (free download from futunn.com). It runs in system tray.",
    "ib":        "Start IB Gateway and log in to your Interactive Brokers account.",
    "tencent":    "Tencent Finance — fast, free, always available in China.",
    "eastmoney":  "Eastmoney — free, comprehensive A/HK/US market data.",
    "yahoo":      "Yahoo Finance — may be blocked in mainland China. Try VPN.",
}

HEALTH_CATEGORIES = {
    "LLM":        ["llm"],
    "A-Stock":    ["tencent", "eastmoney", "futu"],
    "US/HK":      ["yahoo", "eastmoney", "ib", "futu"],
}

def _update_health(key: str, ok: bool):
    """Thread-safe update of a single health status."""
    st.session_state[f"_health_{key}"] = "OK" if ok else "DOWN"

def _probe_all_now(keys: list[str] | None = None):
    """Probe multiple sources concurrently with a 5s overall timeout.
    If keys is None, probes all known sources."""
    if keys is None:
        keys = ["llm", "tencent", "eastmoney", "yahoo", "futu", "ib"]
    probes_map = {"llm": _probe_llm, "tencent": _probe_tencent,
                  "eastmoney": _probe_eastmoney, "yahoo": _probe_yahoo,
                  "futu": _probe_futu, "ib": _probe_ib}
    import concurrent.futures
    results = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(keys)) as ex:
            futures = {ex.submit(probes_map[k]): k for k in keys if k in probes_map}
            for fut in concurrent.futures.as_completed(futures, timeout=10):
                key = futures[fut]
                try:
                    results[key] = fut.result(timeout=0.1)
                except Exception:
                    results[key] = False
            # Any keys that didn't complete within 10s → mark DOWN
            for fut, key in list(futures.items()):
                if key not in results:
                    results[key] = False
                    fut.cancel()
    except concurrent.futures.TimeoutError:
        # Mark remaining as DOWN
        for key in keys:
            if key not in results:
                results[key] = False
    except Exception:
        for key in keys:
            if key not in results:
                results[key] = False
    for key, ok in results.items():
        _update_health(key, ok)


# ── Initialization — no probes, just mark ready ────────────────────────
def _init_data_sources():
    """Show brief startup indicator — probes run on demand, not at startup."""
    if st.session_state.get("_init_done"):
        return
    init_ph = st.empty()
    with init_ph.container():
        st.markdown("###  TradingAgents starting...")
        st.caption("UI ready — click Refresh to check data sources")
        import time as _time2
        _time2.sleep(0.3)
    init_ph.empty()
    st.session_state._init_done = True


# ── Pipeline runner (background thread) ─────────────────────────────────
def _run_pipeline(symbol: str, trade_date: str, market: str, depth: str, data_window: int):
    from tradingagents.config import reset_settings
    from tradingagents.llm.client import clear_client_cache, reset_token_stats
    from tradingagents.graph.progress import reset_progress, finish
    from tradingagents.graph.graph import TradingAgentsGraph

    reset_settings(); clear_client_cache(); reset_token_stats()
    p = reset_progress(depth)
    p.symbol = symbol; p.trade_date = trade_date; p.market = market
    try:
        graph = TradingAgentsGraph(debug=False)
        state, decision, signal = graph.propagate(symbol, trade_date, market=market, depth=depth, data_window=data_window)
        p2 = finish()
        p2.step_results["__state__"] = state
        p2.step_results["__decision__"] = decision
        p2.step_results["__signal__"] = signal

        # Save to analysis history
        try:
            rating = signal.get("action", "HOLD") if isinstance(signal, dict) else "HOLD"
            confidence = signal.get("confidence", 0) if isinstance(signal, dict) else 0
            name = ""
            try:
                from tradingagents.web.app import _fetch_stock_data
                info, _ = _fetch_stock_data(symbol, market)
                name = info.get("name", symbol)
            except Exception:
                name = symbol
            _save_to_history(symbol, trade_date, market, depth,
                           rating, confidence, name, state, decision, signal)
        except Exception:
            pass  # History save failure must not break the pipeline
    except Exception as exc:
        finish(error=str(exc))

# ── Stock info + K-line (single fetch, cached) ────────────────────────
@st.cache_data(show_spinner=False, ttl=1800)
def _fetch_stock_data(symbol: str, market: str, days: int = 30):
    """Return (info_dict, kline_dataframe). Single network call for both."""
    # Fast-fail: skip fetch if all relevant sources are known DOWN
    _relevant = {"a_stock": ["tencent", "eastmoney", "futu"],
                 "hk_stock": ["tencent", "eastmoney", "futu"],
                 "us_stock": ["yahoo", "eastmoney", "futu"]}.get(market, [])
    _all_down = all(st.session_state.get(f"_health_{k}", "?") == "DOWN" for k in _relevant)
    if _all_down:
        return {"symbol": symbol, "market": market, "name": symbol}, pd.DataFrame()

    from tradingagents.data import a_stock, hk_stock, us_stock
    if market == "hk_stock":
        mod = hk_stock
    elif market == "us_stock":
        mod = us_stock
    else:
        mod = a_stock
    try:
        end = pd.Timestamp.now().strftime("%Y-%m-%d")
        start = (pd.Timestamp.now() - pd.Timedelta(days=int(days * 1.6))).strftime("%Y-%m-%d")
        df = mod.get_kline_daily(symbol, start, end)
        # Note: health is probed on-demand — do NOT blindly mark sources OK here
        # since data may have come from a fallback source, not the primary
        info = {"symbol": symbol, "market": market, "name": symbol}
        if not df.empty:
            last = df.iloc[-1]
            for k in ("close", "pe", "pb", "change_pct", "volume", "turn", "amount"):
                try:
                    info[k] = float(pd.to_numeric(last[k], errors="coerce"))
                except Exception:
                    info[k] = None
            # Compute change_pct from close prices if missing (IB doesn't provide it)
            if info.get("change_pct") is None or (isinstance(info["change_pct"], float) and info["change_pct"] != info["change_pct"]):
                try:
                    close_vals = pd.to_numeric(df["close"], errors="coerce")
                    if len(close_vals) >= 2 and close_vals.iloc[-1] > 0:
                        prev = close_vals.iloc[-2]
                        curr = close_vals.iloc[-1]
                        info["change_pct"] = float((curr - prev) / prev * 100) if prev > 0 else 0.0
                except Exception:
                    pass
            # Volume ratio: last 5-day avg vs 20-day avg
            try:
                vol = pd.to_numeric(df["volume"], errors="coerce")
                if len(vol) >= 20:
                    info["vol_ratio"] = float(vol.iloc[-5:].mean() / vol.iloc[-20:].mean())
            except Exception:
                info["vol_ratio"] = None
        # Get display name — multi-source fallback per market
        info["name"] = _lookup_stock_name(symbol, market)
        # Enrich PE/PB/change_pct from quote if missing from K-line (Tencent K-line is OHLCV-only)
        if info.get("pe") is None or (isinstance(info["pe"], float) and info["pe"] != info["pe"]) or \
           info.get("pb") is None or (isinstance(info["pb"], float) and info["pb"] != info["pb"]) or \
           info.get("change_pct") is None or info.get("turn") is None:
            try:
                qdf = mod.get_quote(symbol)
                if not qdf.empty:
                    qr = qdf.iloc[0]
                    for k in ("pe", "pb", "change_pct", "turnover", "market_cap"):
                        qv = qr.get(k)
                        if qv is not None and (not isinstance(qv, float) or qv == qv):
                            if k == "turnover":
                                info["turn"] = float(qv) if qv else None
                            elif info.get(k) is None or (isinstance(info[k], float) and info[k] != info[k]):
                                info[k] = float(qv) if qv else None
                    # Also get name from quote if still unknown
                    qname = qr.get("name", "")
                    if qname and qname != symbol and info.get("name") == symbol:
                        info["name"] = str(qname)
            except Exception:
                pass
        # Enrich with extra metrics from Futu if available
        info = _enrich_stock_info(info, symbol, market)
        return info, df
    except Exception:
        return {"symbol": symbol, "market": market, "name": symbol}, pd.DataFrame()


def _enrich_stock_info(info: dict, symbol: str, market: str) -> dict:
    """Add extra metrics: market cap, float shares, etc. from Futu."""
    try:
        from tradingagents.data.sources.futu import _get_shared_futu
        futu_sym = symbol.strip().upper()
        if market == "a_stock":
            futu_sym = f"{'SH' if futu_sym.startswith('6') else 'SZ'}.{futu_sym}"
        elif market == "hk_stock":
            futu_sym = f"HK.{futu_sym:0>5}"
        else:
            futu_sym = f"US.{futu_sym}"
        ctx = _get_shared_futu()
        if ctx is None:
            return info
        ret, df = ctx.get_market_snapshot([futu_sym])
        # Shared connection — kept open
        if ret == 0 and df is not None and not df.empty:
            row = df.iloc[0]
            # Map Futu fields to our info dict
            field_map = {
                "total_market_val": "market_cap",      # 总市值
                "circular_market_val": "circular_cap", # 流通市值
                "issued_shares": "total_shares",       # 总股本
                "outstanding_shares": "float_shares",  # 流通股
                "amplitude": "amplitude",               # 振幅
                "turnover": "amount",                    # 成交额
                "turnover_rate": "turn",                 # 换手率
                "volume_ratio": "vol_ratio",            # 量比
                "pe_ratio": "pe_forward",               # PE-动
                "pe_ttm_ratio": "pe",                   # PE-TTM
                "pb_ratio": "pb",                       # 市净率
            }
            for src, dst in field_map.items():
                try:
                    val = row.get(src)
                    if val is not None and str(val) != "nan" and val > 0:
                        info[dst] = float(val)
                except Exception:
                    pass
            # Earnings status
            try:
                eps = row.get("earning_per_share") or row.get("net_profit")
                if eps is not None:
                    eps_val = float(eps)
                    info["is_profitable"] = "盈利" if eps_val > 0 else "亏损"
                else:
                    # Fallback: check PE sign
                    pe = info.get("pe")
                    if pe is not None and pe == pe and pe > 0:
                        info["is_profitable"] = "盈利"
                    elif pe is not None and pe == pe and pe < 0:
                        info["is_profitable"] = "亏损"
                    else:
                        info["is_profitable"] = "—"
            except Exception:
                info["is_profitable"] = "—"
    except Exception:
        pass
    return info


def _lookup_stock_name(symbol: str, market: str) -> str:
    """Look up company name from HTTP sources (Tencent / Eastmoney)."""
    s = symbol.strip().upper()
    # A-stock: Tencent → Eastmoney → Futu
    if market == "a_stock":
        try:
            from tradingagents.data.http.tencent import fetch_quote, normalize_cn_code
            q = fetch_quote(normalize_cn_code(s))
            if q and q.get("name") and q["name"] != s:
                return str(q["name"])
        except Exception:
            pass
        try:
            from tradingagents.data.http.eastmoney import fetch_snapshot, _a_secid
            snap = fetch_snapshot(_a_secid(s))
            if snap and snap.get("name") and snap["name"] != s:
                return str(snap["name"])
        except Exception:
            pass
        try:
            from tradingagents.data.sources.futu import _get_shared_futu
            ctx = _get_shared_futu()
            ret, df = ctx.get_market_snapshot([f"{'SH' if s.startswith('6') else 'SZ'}.{s}"])
            if ret == 0 and df is not None and not df.empty:
                name = df.iloc[0].get("name", "")
                if name and name != s:
                    return str(name)
        except Exception:
            pass
    # HK stock: Tencent → Eastmoney → Futu
    elif market == "hk_stock":
        try:
            from tradingagents.data.http.tencent import fetch_quote, normalize_hk_code
            q = fetch_quote(normalize_hk_code(s))
            if q and q.get("name") and q["name"] != s:
                return str(q["name"])
        except Exception:
            pass
        try:
            from tradingagents.data.http.eastmoney import fetch_snapshot, _hk_secid
            snap = fetch_snapshot(_hk_secid(s))
            if snap and snap.get("name") and snap["name"] != s:
                return str(snap["name"])
        except Exception:
            pass
        try:
            from tradingagents.data.sources.futu import _get_shared_futu
            ctx = _get_shared_futu()
            ret, df = ctx.get_market_snapshot([f"HK.{s:0>5}"])
            if ret == 0 and df is not None and not df.empty:
                name = df.iloc[0].get("name", "")
                if name and name != s:
                    return str(name)
        except Exception:
            pass
    # US stock: Yahoo HTTP → Eastmoney → Futu
    elif market == "us_stock":
        try:
            from tradingagents.data.http.yahoo import fetch_quote
            q = fetch_quote(s, "us_stock")
            if q and q.get("name") and q["name"] != s and len(q["name"]) < 50:
                return str(q["name"])
        except Exception:
            pass
        try:
            from tradingagents.data.http.eastmoney import fetch_snapshot, _us_secid
            snap = fetch_snapshot(_us_secid(s))
            if snap and snap.get("name") and snap["name"] != s:
                return str(snap["name"])
        except Exception:
            pass
        try:
            from tradingagents.data.sources.futu import _get_shared_futu
            ctx = _get_shared_futu()
            ret, df = ctx.get_market_snapshot([f"US.{s}"])
            if ret == 0 and df is not None and not df.empty:
                name = df.iloc[0].get("name", "")
                if name and name != s:
                    return str(name)
        except Exception:
            pass
    return s

# ── Cache helpers ───────────────────────────────────────────────────────
def _cache_path(symbol: str, depth: str) -> Path:
    from tradingagents.config import get_settings
    safe = symbol.strip().replace("/", "_").replace("\\", "_").replace("..", "")
    return get_settings().results_dir / safe / "TradingAgentsStrategy_logs" / f"latest_{depth}.json"


def _load_cached_result(symbol: str, depth: str) -> dict | None:
    """Load a previously saved analysis result for (symbol, depth)."""
    path = _cache_path(symbol, depth)
    if not path.exists():
        return None
    try:
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── Analysis History ────────────────────────────────────────────────────

def _history_index_path() -> Path:
    from tradingagents.config import get_settings
    return get_settings().results_dir / "_history.json"


def _load_history() -> list[dict]:
    """Load the full analysis history index (most recent first)."""
    path = _history_index_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_to_history(symbol: str, trade_date: str, market: str, depth: str,
                     rating: str, confidence: float, name: str,
                     state: dict, decision: str, signal: dict):
    """Append an analysis result to the JSON history, saving the full report."""
    from tradingagents.config import get_settings
    import datetime as _dt

    ts = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    safe = symbol.strip().replace("/", "_").replace("\\", "_").replace("..", "")

    # Save full result
    hist_dir = get_settings().results_dir / safe / "history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "symbol": symbol, "trade_date": trade_date, "market": market,
        "depth": depth, "rating": rating, "confidence": confidence,
        "name": name, "saved_at": ts,
        "state": state, "decision": decision, "signal": signal,
    }
    hist_file = hist_dir / f"{trade_date}_{depth}_{ts.replace(':', '-')}.json"
    try:
        hist_file.write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception:
        pass  # Don't block analysis for history save failures

    # Update index (keep latest 500 entries)
    idx = _load_history()
    idx.insert(0, {
        "symbol": symbol, "trade_date": trade_date, "market": market,
        "depth": depth, "rating": rating, "confidence": confidence,
        "name": name, "saved_at": ts,
    })
    # Deduplicate same symbol+date+depth
    seen = set()
    deduped = []
    for entry in idx:
        key = (entry["symbol"], entry["trade_date"], entry["depth"])
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    deduped = deduped[:500]
    try:
        _history_index_path().parent.mkdir(parents=True, exist_ok=True)
        _history_index_path().write_text(json.dumps(deduped, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _load_from_history(entry: dict) -> dict | None:
    """Load a full analysis result from its history entry."""
    from tradingagents.config import get_settings
    safe = entry["symbol"].strip().replace("/", "_").replace("\\", "_").replace("..", "")
    hist_dir = get_settings().results_dir / safe / "history"
    if not hist_dir.exists():
        return None
    # Find matching file by trade_date and depth
    td = entry.get("trade_date", "")
    depth = entry.get("depth", "")
    for f in sorted(hist_dir.iterdir(), reverse=True):
        if f.name.startswith(f"{td}_{depth}_") and f.suffix == ".json":
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


def _clear_history():
    """Remove the history index. Individual files remain but won't be listed."""
    path = _history_index_path()
    if path.exists():
        path.unlink()


# ── Auto-detect market from symbol ──────────────────────────────────────
def _detect_market(symbol: str) -> str | None:
    """Determine market from ticker format. Returns None if unrecognized.

    Valid formats:
      - A-stock: 6 digits (600519), or SH.xxx / SZ.xxx
      - HK stock: 1-5 digits (700, 9988), or xxx.HK
      - US stock: 1-5 letters (AAPL, TSLA, PATH)
    """
    s = symbol.strip().upper().replace(" ", "")
    if not s:
        return None
    # A-stock: 6-digit numeric
    if s.isdigit() and len(s) == 6:
        return "a_stock"
    # HK: 1-5 digit numeric
    if s.isdigit() and len(s) <= 5:
        return "hk_stock"
    # US: 1-5 ASCII letters (isascii() excludes CJK which also passes isalpha())
    if s.isascii() and s.isalpha() and len(s) <= 5:
        return "us_stock"
    # Explicit qualified formats
    if s.startswith(("SH.", "SZ.")):
        return "a_stock"
    if s.endswith(".HK"):
        return "hk_stock"
    # Anything else: company name, invalid code, etc.
    return None


# ── Session persistence ────────────────────────────────────────────────
_SESSION_FILE = Path.home() / ".tradingagents" / "session_state.json"


def _save_session(symbol: str, depth: str, data_window: int):
    try:
        _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SESSION_FILE.write_text(json.dumps({
            "symbol": symbol, "depth": depth, "data_window": data_window,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _load_session() -> dict:
    try:
        if _SESSION_FILE.exists():
            return json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _market_label(m: str | None) -> str:
    if m is None:
        return "Unrecognized"
    return {"a_stock": "A-Shares", "hk_stock": "Hong Kong", "us_stock": "US Stocks"}.get(m, m)


def _build_export_report(state: dict, symbol: str, trade_date: str, market: str, depth: str) -> str:
    """Build a complete Markdown report for export."""
    sections = [
        f"# TradingAgents Analysis Report",
        f"**Symbol**: {symbol} | **Date**: {trade_date} | **Market**: {_market_label(market)} | **Depth**: {depth}",
        "",
        "---",
        "",
    ]
    report_map = [
        ("Final Decision", "final_trade_decision"),
        ("Market / Technical Analysis", "market_report"),
        ("Sentiment Analysis", "sentiment_report"),
        ("News & Macro Analysis", "news_report"),
        ("Fundamental Analysis", "fundamentals_report"),
        ("Policy Analysis", "policy_report"),
        ("Hot Money / Capital Flow", "hot_money_report"),
        ("Lockup / Insider Analysis", "lockup_report"),
        ("Investment Plan", "investment_plan"),
        ("Trader Proposal", "trader_investment_plan"),
    ]
    for title, key in report_map:
        content = state.get(key, "") if isinstance(state, dict) else ""
        if content:
            sections.append(f"## {title}")
            sections.append("")
            sections.append(content)
            sections.append("")
            sections.append("---")
            sections.append("")

    signal = state.get("structured_decision", {}) if isinstance(state, dict) else {}
    if isinstance(signal, dict) and signal:
        sections.append("## Structured Decision")
        sections.append("")
        sections.append(f"- **Rating**: {signal.get('action', 'N/A')}")
        sections.append(f"- **Confidence**: {signal.get('confidence', 0):.0%}")
        sections.append(f"- **Risk Score**: {signal.get('risk_score', 0):.0%}")
        sections.append(f"- **Target Price**: {signal.get('target_price', 'N/A')}")
        sections.append("")

    sections.append("---")
    sections.append("*Generated by TradingAgents-dp*")
    return "\n".join(sections)


def _build_pdf_report(state: dict, symbol: str, trade_date: str, market: str, depth: str) -> bytes:
    """Build a professional PDF report with all tab content, CJK support, and clean layout."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    # ── Chinese font discovery (Windows + macOS) ──
    def _find_chinese_font():
        """Return (regular_path, bold_path, font_name) for CJK PDF rendering."""
        import sys as _sys2, platform as _platform

        # Build font search dirs based on OS
        font_dirs = []
        if _platform.system() == "Windows":
            font_dirs.append(Path("C:/Windows/Fonts"))
        elif _platform.system() == "Darwin":
            font_dirs.extend([
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library" / "Fonts",
            ])
        else:  # Linux / WSL
            font_dirs.extend([
                Path("/usr/share/fonts/truetype"),
                Path("/usr/share/fonts/opentype"),
                Path("/usr/share/fonts"),
                Path.home() / ".local" / "share" / "fonts",
                Path.home() / ".fonts",
            ])
        # Add _MEIPASS as last resort
        meipass = getattr(_sys2, "_MEIPASS", None)
        if meipass:
            font_dirs.append(Path(meipass) / "fonts")

        # Candidates: (regular_file, bold_file, family_name)
        if _platform.system() == "Windows":
            candidates = [
                ("msyh.ttc",  "msyhbd.ttc", "MicrosoftYaHei"),
                ("msyh.ttf",  "msyhbd.ttf", "MicrosoftYaHei"),
                ("simhei.ttf","simhei.ttf",  "SimHei"),
                ("simsun.ttc","simsunb.ttf", "SimSun"),
                ("simkai.ttf","simkai.ttf",  "KaiTi"),
            ]
        elif _platform.system() == "Darwin":  # macOS
            candidates = [
                ("PingFang.ttc",  "PingFang.ttc",  "PingFang"),
                ("STHeiti Light.ttc", "STHeiti Light.ttc", "STHeiti"),
                ("STHeiti Medium.ttc", "STHeiti Medium.ttc", "STHeiti"),
                ("Heiti SC.ttc", "Heiti SC.ttc", "Heiti SC"),
                ("NotoSansSC-Regular.otf", "NotoSansSC-Regular.otf", "NotoSansSC"),
            ]
        else:  # Linux / WSL
            candidates = [
                ("NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc", "NotoSansCJK"),
                ("NotoSansSC-Regular.otf",  "NotoSansSC-Bold.otf",  "NotoSansSC"),
                ("wqy-zenhei.ttc",          "wqy-zenhei.ttc",       "WenQuanYi"),
                ("wqy-microhei.ttc",        "wqy-microhei.ttc",     "WenQuanYiMicroHei"),
                ("DroidSansFallbackFull.ttf","DroidSansFallbackFull.ttf","DroidSans"),
            ]

        for font_dir in font_dirs:
            if not font_dir.is_dir():
                continue
            for reg, bold, family in candidates:
                # Use recursive glob to find fonts in subdirectories (e.g. opentype/noto/)
                rp_matches = list(font_dir.rglob(reg))
                bp_matches = list(font_dir.rglob(bold)) if bold != reg else rp_matches
                if rp_matches:
                    rp = rp_matches[0]
                    bp = bp_matches[0] if bp_matches else rp
                    return str(rp), str(bp), family
            # Fallback: any .ttc or .ttf in this font directory tree
            for ext in (".ttc", ".ttf", ".otf"):
                for f in font_dir.rglob(f"*{ext}"):
                    return str(f), str(f), f.stem

        raise FileNotFoundError(
            "No CJK font found. Install a Chinese font pack."
        )

    try:
        FONT_PATH, BOLD_PATH, FONT_NAME = _find_chinese_font()
    except FileNotFoundError as e:
        # Return a text-based error PDF instead of crashing the page
        import logging; logging.getLogger(__name__).warning("PDF font not found: %s", e)
        err_msg = (
            "PDF Export Failed — No Chinese Font Found\n\n"
            "Install a CJK font to enable PDF export:\n"
            "  Ubuntu/Debian: sudo apt install fonts-noto-cjk\n"
            "  macOS: built-in PingFang is auto-detected\n"
            "  Windows: built-in Microsoft YaHei is auto-detected\n"
        )
        pdf_err = FPDF()
        pdf_err.add_page()
        pdf_err.set_font("Helvetica", size=10)
        pdf_err.multi_cell(0, 6, err_msg)
        return bytes(pdf_err.output())

    class PDF(FPDF):
        def header(self):
            if self.page_no() > 1:
                self.set_font(FONT_NAME, size=7)
                self.set_text_color(120, 120, 120)
                self.cell(0, 4, f"TradingAgents  ·  {symbol}  ·  {trade_date}", align="C")
                self.ln(6)

        def footer(self):
            self.set_y(-12)
            self.set_font(FONT_NAME, size=7)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, str(self.page_no()), align="C")

        def section_title(self, title: str):
            self.set_font(FONT_NAME, size=13)
            self.set_text_color(0, 47, 167)  # Klein Blue
            self.set_fill_color(240, 245, 255)
            self.cell(0, 9, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
            self.ln(3)

        def _clean(self, s: str) -> str:
            """Strip emoji and non-renderable characters that CJK fonts lack."""
            return s.replace("⚠", "[!]").replace("️", "").replace("✔", "[v]").replace("❌", "[x]").replace("✓", "[v]")

        def body_text(self, text: str):
            if not text or not text.strip():
                return
            self.set_font(FONT_NAME, size=8.5)
            self.set_text_color(30, 30, 30)
            for line in text.split("\n"):
                line = self._clean(line.strip())
                line = line.strip()
                if not line:
                    self.ln(2)
                    continue
                self.set_x(self.l_margin)
                if line.startswith("### "):
                    self.set_font(FONT_NAME, size=10)
                    self.set_text_color(0, 0, 0)
                    self.multi_cell(0, 6, line[4:])
                    self.ln(1)
                    self.set_font(FONT_NAME, size=8.5)
                    self.set_text_color(30, 30, 30)
                elif line.startswith("## "):
                    self.set_font(FONT_NAME, size=11)
                    self.set_text_color(0, 47, 167)
                    self.multi_cell(0, 7, line[3:])
                    self.ln(1)
                    self.set_font(FONT_NAME, size=8.5)
                    self.set_text_color(30, 30, 30)
                elif line.startswith("# "):
                    self.set_font(FONT_NAME, size=13)
                    self.set_text_color(0, 47, 167)
                    self.multi_cell(0, 8, line[2:])
                    self.ln(1)
                    self.set_font(FONT_NAME, size=8.5)
                    self.set_text_color(30, 30, 30)
                elif line.startswith(("- ", "* ")):
                    self.multi_cell(0, 5, "· " + line[2:])
                elif line.startswith("**") and "**:" in line:
                    parts = line.split("**:", 1)
                    label = parts[0].replace("**", "").strip()
                    val = parts[1].strip() if len(parts) > 1 else ""
                    self.set_text_color(80, 80, 80)
                    label_w = self.get_string_width(label + ":  ")
                    self.cell(label_w, 5, label + ":  ")
                    self.set_text_color(30, 30, 30)
                    self.multi_cell(self.w - self.get_x() - self.r_margin, 5, val)
                    self.set_text_color(30, 30, 30)
                else:
                    self.multi_cell(0, 5, line)

        def kv_table(self, rows: list[tuple[str, str]]):
            """Simple key-value table with colored labels."""
            self.set_font(FONT_NAME, size=8.5)
            for label, value in rows:
                if self.get_y() > 250:
                    self.add_page()
                self.set_x(self.l_margin)
                self.set_fill_color(255, 241, 232)
                self.set_text_color(180, 60, 20)
                self.cell(38, 6, f" {label}", fill=True)
                self.set_text_color(30, 30, 30)
                self.multi_cell(self.w - self.get_x() - self.r_margin, 6, str(value)[:300])
                self.ln(0.5)

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font(FONT_NAME, "", FONT_PATH)
    pdf.add_font(FONT_NAME, "B", BOLD_PATH)

    # ── Cover page ──
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font(FONT_NAME, size=28)
    pdf.set_text_color(0, 47, 167)
    pdf.cell(0, 14, "TradingAgents", align="C")
    pdf.ln(16)
    pdf.set_font(FONT_NAME, size=18)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, "Investment Analysis Report", align="C")
    pdf.ln(18)

    # Rating badge on cover
    signal = state.get("structured_decision", {}) if isinstance(state, dict) else {}
    final_rating = signal.get("action", "N/A")
    rating_colors = {
        "BUY": (6, 95, 70), "OVERWEIGHT": (30, 64, 175),
        "HOLD": (146, 64, 14), "UNDERWEIGHT": (154, 52, 18), "SELL": (153, 27, 27),
    }
    rc, gc, bc = rating_colors.get(final_rating.upper(), (80, 80, 80))
    pdf.set_fill_color(rc, gc, bc)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(FONT_NAME, size=22)
    pdf.cell(50, 12, f" {final_rating.upper()} ", fill=True, align="C")
    pdf.ln(16)

    pdf.set_font(FONT_NAME, size=11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 7, f"Symbol: {symbol}    |    Date: {trade_date}    |    Market: {_market_label(market)}    |    Depth: {depth}", align="C")
    pdf.ln(12)

    # Confidence & Risk Score
    conf = signal.get("confidence", 0)
    risk = signal.get("risk_score", 0)
    tp = signal.get("target_price")
    pdf.set_font(FONT_NAME, size=10)
    pdf.set_text_color(60, 60, 60)
    metric_text = f"Confidence: {conf:.0%}    |    Risk Score: {risk:.0%}"
    if tp:
        currency = "¥" if market == "a_stock" else "$"
        metric_text += f"    |    Target Price: {currency}{tp:.2f}"
    pdf.cell(0, 7, metric_text, align="C")
    pdf.ln(8)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(30, pdf.get_y(), 180, pdf.get_y())

    # ── Section 1: Executive Summary ──
    pdf.add_page()
    pdf.section_title("1. Executive Summary — Portfolio Manager Decision")
    final_dec = state.get("final_trade_decision", "") if isinstance(state, dict) else ""
    if final_dec:
        pdf.body_text(final_dec)
    else:
        pdf.body_text("(No decision text available)")

    # ── Section 2: Decision Chain Summary ──
    pdf.ln(4)
    pdf.section_title("2. Decision Chain Overview")
    qg = state.get("data_quality_summary", "") if isinstance(state, dict) else ""
    if qg:
        pdf.body_text(qg)
        pdf.ln(3)

    # Debate summary
    debate_state = state.get("investment_debate_state", {}) if isinstance(state, dict) else {}
    debate_rounds = debate_state.get("count", 0) if isinstance(debate_state, dict) else 0
    if debate_rounds:
        pdf.body_text(f"Bull vs Bear Debate: {debate_rounds} rounds completed.")
    risk_state = state.get("risk_debate_state", {}) if isinstance(state, dict) else {}
    risk_rounds = risk_state.get("count", 0) if isinstance(risk_state, dict) else 0
    if risk_rounds:
        pdf.body_text(f"3-Way Risk Debate: {risk_rounds} rounds completed.")

    # ── Section 3: Analyst Reports ──
    pdf.ln(4)
    pdf.section_title("3. Analyst Reports")
    analyst_sections = [
        ("Market / Technical Analysis", "market_report"),
        ("Sentiment & Social Analysis", "sentiment_report"),
        ("News & Macro Analysis", "news_report"),
        ("Fundamental Analysis", "fundamentals_report"),
        ("Policy & Regulatory Analysis", "policy_report"),
        ("Hot Money / Capital Flow", "hot_money_report"),
        ("Lockup & Insider Analysis", "lockup_report"),
    ]
    for title, key in analyst_sections:
        content = state.get(key, "") if isinstance(state, dict) else ""
        if content and len(content.strip()) > 30:
            pdf.ln(2)
            pdf.set_font(FONT_NAME, size=11)
            pdf.set_text_color(0, 47, 167)
            pdf.cell(0, 7, title)
            pdf.ln(8)
            pdf.body_text(content)
            pdf.ln(2)
            # Thin separator
            pdf.set_draw_color(220, 220, 220)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(3)

    # ── Section 4: Debate Transcripts ──
    pdf.ln(4)
    pdf.section_title("4. Bull vs Bear Debate — Full Transcript")
    debate_history = debate_state.get("history", "") if isinstance(debate_state, dict) else ""
    if debate_history:
        pdf.body_text(debate_history)
    else:
        pdf.body_text("(No debate transcript)")

    pdf.ln(4)
    pdf.section_title("5. Risk Debate — Full Transcript")
    risk_history = risk_state.get("history", "") if isinstance(risk_state, dict) else ""
    if risk_history:
        pdf.body_text(risk_history)
    else:
        pdf.body_text("(No risk debate transcript)")

    # ── Section 5: Decision Details ──
    pdf.ln(4)
    pdf.section_title("6. Investment Plan (Research Manager)")
    invest_plan = state.get("investment_plan", "") if isinstance(state, dict) else ""
    if invest_plan:
        pdf.body_text(invest_plan)
    else:
        pdf.body_text("(No investment plan)")

    pdf.ln(4)
    pdf.section_title("7. Transaction Proposal (Trader)")
    trader_plan = state.get("trader_investment_plan", "") if isinstance(state, dict) else ""
    if trader_plan:
        pdf.body_text(trader_plan)
    else:
        pdf.body_text("(No trader plan)")

    # ── Colophon ──
    pdf.ln(8)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)
    pdf.set_font(FONT_NAME, size=7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Generated by TradingAgents-dp  ·  {trade_date}", align="C")

    # Suppress fonttools "MERG NOT subset" noise during output (harmless for TTC fonts)
    import contextlib, os as _os
    _devnull = open(_os.devnull, "w")
    with contextlib.redirect_stderr(_devnull):
        result = bytes(pdf.output())
    _devnull.close()
    return result


# ── System Health Bar ──────────────────────────────────────────────────

def _render_health_bar():
    """Render a compact system health dashboard at the top of the main area."""
    html_parts = []
    for cat, keys in HEALTH_CATEGORIES.items():
        chips = []
        for key in keys:
            status = st.session_state.get(f"_health_{key}", "?")
            if status == "OK":
                dot = '<span class="health-dot-ok">●</span>'
                lbl_color = "#00E676"
                label = "ON"
            elif status == "DOWN":
                hint = HEALTH_HINTS.get(key, "")
                dot = f'<span class="health-dot-down" title="{hint}">●</span>'
                lbl_color = "#FF5252"
                label = "OFF"
                label = f'<span title="{hint}" style="cursor:help">{label}</span>'
            else:
                dot = '<span class="health-dot-unknown">●</span>'
                lbl_color = "#bfbfbf"
                label = "—"
            chips.append(f'{dot} <span style="color:{lbl_color};font-size:0.72rem;font-weight:600">{key.upper()}</span> '
                        f'<span style="color:{lbl_color};font-size:0.65rem">{label}</span>')
        row = " &nbsp;│&nbsp; ".join(chips)
        html_parts.append(
            f'<span style="color:#8c8c8c;font-size:0.68rem;font-weight:600;text-transform:uppercase">{cat}</span>'
            f'<span style="margin-left:10px">{row}</span>'
        )
    full_html = " &nbsp;│&nbsp; ".join(html_parts)
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:8px 16px;margin-bottom:8px;line-height:2">'
        f'{full_html}</div>',
        unsafe_allow_html=True,
    )


# ── Main ────────────────────────────────────────────────────────────────
def run():
    from tradingagents.graph.progress import get_progress, STEP_LABELS

    # Show initialization progress on first load (probes data sources)
    _init_data_sources()


    # Init session keys
    if "_running" not in st.session_state: st.session_state._running = False
    if "_done" not in st.session_state: st.session_state._done = False
    if "_thread" not in st.session_state: st.session_state._thread = None
    if "_batch_queue" not in st.session_state: st.session_state._batch_queue = []
    if "_batch_running" not in st.session_state: st.session_state._batch_running = False
    if "_from_cache" not in st.session_state: st.session_state._from_cache = False
    if "_cached_result" not in st.session_state: st.session_state._cached_result = None
    if "_cached_symbol" not in st.session_state: st.session_state._cached_symbol = ""
    if "_cached_depth" not in st.session_state: st.session_state._cached_depth = ""

    # ═══ SIDEBAR ═══
    with st.sidebar:
        st.markdown("### TradingAgents")
        st.caption("AI-Powered Investment Research")
        st.divider()

        # Load last session
        last = _load_session()

        st.markdown('<div class="ig-label" style="margin-top:0">Stock Symbol</div>', unsafe_allow_html=True)
        symbol = st.text_input("symbol_input", last.get("symbol", "688775"), placeholder="输入股票代码", label_visibility="collapsed")

        st.markdown('<div class="ig-label">Analysis Date</div>', unsafe_allow_html=True)
        trade_date = st.date_input("date_input", pd.Timestamp.now(), label_visibility="collapsed").strftime("%Y-%m-%d")

        st.markdown('<div class="ig-label">Market</div>', unsafe_allow_html=True)
        market = _detect_market(symbol)
        st.markdown(f'<div style="color:rgba(255,255,255,.45);font-size:0.88rem;padding:2px 0">{_market_label(market)}</div>', unsafe_allow_html=True)

        # ── Analysis History ──
        st.divider()
        st.markdown("**Analysis History**")
        history = _load_history()
        if not history:
            st.caption("No history yet — run your first analysis.")
        else:
            st.caption(f"{len(history)} records")
            for i, entry in enumerate(history[:20]):
                sym = entry.get("symbol", "?")
                dt = entry.get("trade_date", "")[:10]
                rating = entry.get("rating", "HOLD")
                depth = entry.get("depth", "")
                name = entry.get("name", "") or sym
                conf = entry.get("confidence", 0)
                badge_color = {
                    "BUY": "#00E676", "OVERWEIGHT": "#1890FF",
                    "HOLD": "#faad14", "UNDERWEIGHT": "#fa541c",
                    "SELL": "#FF5252",
                }.get(rating.upper(), "#8c8c8c")
                cols = st.columns([8, 1.5])
                with cols[0]:
                    btn_label = f"{name} ({sym}) — {dt} · {depth}"
                    if st.button(btn_label, key=f"hist_{i}", use_container_width=True,
                                help=f"Rating: {rating} · Confidence: {conf:.0%}"):
                        full = _load_from_history(entry)
                        if full:
                            p = get_progress()
                            p.finished = True
                            p.step_results["__state__"] = full.get("state", {})
                            p.step_results["__decision__"] = full.get("decision", "")
                            p.step_results["__signal__"] = full.get("signal", {})
                            st.session_state._done = True
                            st.session_state._from_cache = True
                            st.session_state._cached_result = full
                            st.rerun()
                with cols[1]:
                    st.markdown(
                        f'<span style="display:inline-block;padding:2px 8px;border-radius:3px;'
                        f'background:{badge_color}22;color:{badge_color};font-size:0.7rem;'
                        f'font-weight:600;margin-top:6px">{rating}</span>',
                        unsafe_allow_html=True,
                    )
            if len(history) > 20:
                st.caption(f"... and {len(history) - 20} more")
            if st.button("Clear All History", type="secondary", use_container_width=True):
                _clear_history()
                st.rerun()

        # Validate ticker format
        if market is None:
            sym = symbol.strip()
            st.error(
                f"**'{sym}' is not a recognized ticker format.**\n\n"
                "Valid formats:\n\n"
                "- **A-Shares**: 6-digit code (e.g. 600519, 000001)\n"
                "- **HK Stocks**: 1-5 digit code (e.g. 700, 9988)\n"
                "- **US Stocks**: 1-5 letter symbol (e.g. AAPL, TSLA, PATH)\n"
                "- Qualified: SH.600519, 700.HK"
            )

        st.markdown('<div class="ig-label">Data Window</div>', unsafe_allow_html=True)
        dw_default = last.get("data_window", 30)
        dw_index = [30, 60, 120, 250].index(dw_default) if dw_default in [30, 60, 120, 250] else 0
        data_window = st.selectbox("window_select", [30, 60, 120, 250], index=dw_index,
                                   format_func=lambda x: f"{x} trading days ({x//21}月)",
                                   label_visibility="collapsed")

        st.markdown('<div class="ig-label">Analysis Depth</div>', unsafe_allow_html=True)
        depth_default = last.get("depth", "medium")
        depth_index = ["light", "medium", "deep"].index(depth_default) if depth_default in ["light", "medium", "deep"] else 1
        depth = st.selectbox("depth_select", ["light", "medium", "deep"], index=depth_index,
                             format_func=lambda x: {"light": "Light (5 steps, ~2 min)", "medium": "Medium (13 steps, ~8 min)", "deep": "Deep (16 steps, ~12 min)"}[x],
                             label_visibility="collapsed")

        # Persist current selection
        _save_session(symbol, depth, data_window)
        st.divider()

        # Batch analysis
        st.divider()
        st.markdown("**Batch Analysis**")
        batch_symbols = st.text_area("batch_input", placeholder="600519, 000001, 688775", label_visibility="collapsed", height=60)
        batch_list = [s.strip() for s in batch_symbols.replace("\n", ",").split(",") if s.strip()] if batch_symbols else []
        bcol1, bcol2 = st.columns([3, 1])
        with bcol1:
            if batch_list and st.button("Add to Queue", use_container_width=True):
                for s in batch_list:
                    if s not in st.session_state._batch_queue:
                        st.session_state._batch_queue.append(s)
                st.rerun()
        with bcol2:
            if st.session_state._batch_queue and st.button("Clear", use_container_width=True):
                st.session_state._batch_queue = []
                st.rerun()
        if st.session_state._batch_queue:
            st.caption(f"Queue ({len(st.session_state._batch_queue)}): {', '.join(st.session_state._batch_queue[:8])}" +
                      (f" ..." if len(st.session_state._batch_queue) > 8 else ""))

        # Run Analysis — ALWAYS at the bottom
        st.divider()
        can_run = not st.session_state._running and market is not None
        if st.button("▶  Run Analysis", type="primary", disabled=not can_run, use_container_width=True):
            # Quick health probe before starting pipeline
            _probe_all_now(["llm", "tencent", "eastmoney", "yahoo", "futu", "ib"])
            st.session_state._running = True
            st.session_state._done = False
            st.session_state._from_cache = False
            st.session_state._notified = False
            st.session_state._cached_result = None
            t = threading.Thread(target=_run_pipeline, args=(symbol, trade_date, market, depth, data_window), daemon=True)
            t.start()
            st.session_state._thread = t
            st.rerun()

        # Clear Report — remove cached analysis for current symbol+depth
        if st.button("Clear Report", type="secondary", use_container_width=True):
            cache_path = _cache_path(symbol, depth)
            if cache_path.exists():
                cache_path.unlink()
            st.session_state._done = False
            st.session_state._cached_result = None
            st.session_state._running = False
            st.rerun()

        # Report export — PDF + Markdown
        export_data = _load_cached_result(symbol, depth) or {}
        ec1, ec2 = st.columns(2)
        with ec1:
            st.download_button(
                label="Export Report (PDF)",
                data=_build_pdf_report(export_data, symbol, trade_date, market, depth),
                file_name=f"{symbol}_{trade_date}_{depth}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with ec2:
            st.download_button(
                label="Export Report (Markdown)",
                data=_build_export_report(export_data, symbol, trade_date, market, depth),
                file_name=f"{symbol}_{trade_date}_{depth}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        # Token display (always visible)
        st.divider()
        p_now = get_progress()
        st.markdown("**Token Usage**")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="tbox"><div class="tv">{p_now.tokens_in:,}</div><div class="tl">Input</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="tbox"><div class="tv">{p_now.tokens_out:,}</div><div class="tl">Output</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="tbox"><div class="tv">{p_now.tokens_total:,}</div><div class="tl">Total</div></div>', unsafe_allow_html=True)

    # ═══ CACHE CHECK ═══
    # When user changes symbol/depth, auto-load cached result if exists
    cache_key = f"{symbol}|{depth}"
    if cache_key != f"{st.session_state._cached_symbol}|{st.session_state._cached_depth}" and not st.session_state._running:
        st.session_state._cached_symbol = symbol
        st.session_state._cached_depth = depth
        cached = _load_cached_result(symbol, depth)
        st.session_state._cached_result = cached
        if cached:
            st.session_state._done = True
            st.session_state._from_cache = True

    # ═══ MAIN ═══
    if market is None:
        _render_health_bar()
        st.info("Enter a valid ticker symbol to view stock data and run analysis.")
        return

    import datetime as _dt

    # On first load (no prior analysis), skip data fetch to avoid blocking UI
    # User clicks Refresh to explicitly load stock data
    _first_visit = not st.session_state.get("_data_loaded", False)
    if _first_visit:
        st.session_state._data_loaded = True
        info = {"symbol": symbol, "market": market, "name": symbol}
        kline_df = pd.DataFrame()
        st.info("Welcome! Click **Refresh** to load stock data, or **Run Analysis** to start.")
    else:
        info, kline_df = _fetch_stock_data(symbol, market)

    # System Health Dashboard
    _render_health_bar()

    # Stock header + refresh
    rcol1, rcol2 = st.columns([25, 2])
    with rcol1:
        st.caption(f"Data as of {_dt.datetime.now().strftime('%H:%M:%S')} · 30 min cache")
    with rcol2:
        if st.button("Refresh", key="refresh_data_btn", help="Refresh stock data & K-line chart"):
            _fetch_stock_data.clear()
            # Reset data source health + fast-fail flags for fresh detection
            for k in ("tencent", "eastmoney", "yahoo", "futu", "ib"):
                st.session_state.pop(f"_health_{k}", None)
            try:
                from tradingagents.data.sources.futu import _reset_futu_flag
                _reset_futu_flag()
            except Exception:
                pass
            # Quick probe of core sources so health bar shows status
            _probe_all_now(["llm", "tencent", "eastmoney", "yahoo", "futu", "ib"])
            st.rerun()

    def _mc(label, value, fmt=None, color_class=""):
        if value is None or (isinstance(value, float) and value != value):
            display = "—"
        elif fmt == "pct":
            sgn = "+" if value >= 0 else ""
            display = f"{sgn}{value:.2f}%"
        elif fmt == "pe":
            if value < 0:
                display = "亏损"
            elif value == 0:
                display = "—"
            elif value > 9999:
                display = "亏损"
            else:
                display = f"{value:.1f}"
        elif fmt == "f2":
            display = f"{value:.2f}"
        elif fmt == "big":
            if abs(value) >= 1e8: display = f"{value/1e8:.2f}亿"
            elif abs(value) >= 1e4: display = f"{value/1e4:.0f}万"
            else: display = f"{value:.0f}"
        elif fmt == "shares":
            if abs(value) >= 1e8: display = f"{value/1e8:.2f}亿股"
            else: display = f"{value/1e4:.0f}万股"
        else:
            display = str(value)[:16]
        st.markdown(f'<div class="mc"><div class="mcl">{label}</div><div class="mcv {color_class}">{display}</div></div>', unsafe_allow_html=True)

    # Row 1
    r1 = st.columns(7)
    with r1[0]: _mc("Symbol", symbol)
    with r1[1]: _mc("Name", str(info.get("name", "—")))
    with r1[2]:
        close = info.get("close")
        _mc("Price", f"¥{close:.2f}" if close and close == close else None)
    with r1[3]:
        chg = info.get("change_pct")
        cls = "up" if (chg or 0) >= 0 else "down"
        _mc("Change", chg, fmt="pct", color_class=cls)
    with r1[4]: _mc("PE-TTM", info.get("pe"), fmt="pe")
    with r1[5]: _mc("PE-动", info.get("pe_forward"), fmt="pe")
    with r1[6]: _mc("Turnover%", info.get("turn"), fmt="f2")

    # Row 2
    r2 = st.columns(7)
    with r2[0]: _mc("Market Cap", info.get("market_cap"), fmt="big")
    with r2[1]: _mc("成交额", info.get("amount"), fmt="big")
    with r2[2]: _mc("量比", info.get("vol_ratio"), fmt="f2")
    with r2[3]: _mc("流通股", info.get("float_shares"), fmt="shares")
    with r2[4]: _mc("总股本", info.get("total_shares"), fmt="shares")
    with r2[5]: _mc("盈利?", info.get("is_profitable", "—"))
    with r2[6]: _mc("PB", info.get("pb"), fmt="f2")

    st.markdown('<div style="margin-top:16px"></div>', unsafe_allow_html=True)

    # ═══ K-line chart ═══
    if not kline_df.empty:
        try:
            import plotly.graph_objects as go
            kdf = kline_df.copy()
            kdf["date"] = pd.to_datetime(kdf["date"])
            for c in ("open","high","low","close","volume"):
                if c in kdf.columns:
                    kdf[c] = pd.to_numeric(kdf[c], errors="coerce")
            kdf = kdf.dropna(subset=["open","high","low","close"])

            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=kdf["date"], open=kdf["open"], high=kdf["high"],
                low=kdf["low"], close=kdf["close"],
                name="Price", increasing_line_color="#FF5252", decreasing_line_color="#00E676",
            ))
            fig.add_trace(go.Bar(
                x=kdf["date"], y=kdf["volume"], name="Volume",
                marker_color="rgba(37,99,235,0.3)", yaxis="y2",
            ))
            fig.update_layout(
                title=dict(text=f"{symbol}  {info.get('name', '')}", font=dict(color="#1f1f1f")),
                xaxis_title="", yaxis_title="Price",
                template="plotly_white",
                height=400,
                margin=dict(l=0, r=0, t=50, b=0),
                showlegend=False,
                xaxis_rangeslider_visible=False,
                yaxis=dict(gridcolor="#f0f0f0", zerolinecolor="#f0f0f0"),
                yaxis2=dict(title="", overlaying="y", side="right", showgrid=False, visible=False),
                hovermode="x unified",
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        except Exception:
            pass

    st.divider()

    # ═══ STATE: RUNNING ═══
    if st.session_state._running:
        p = get_progress()

        # Check if finished (pipeline thread completed)
        if p.finished:
            st.session_state._running = False
            st.session_state._done = True
            st.rerun()

        completed = p.completed_steps
        current = p.current_step
        n_done = len(completed)
        active_steps = p.steps
        pct = n_done / len(active_steps) if active_steps else 0

        st.progress(pct)
        cur_label = STEP_LABELS.get(current, "Initializing...")
        st.caption(f"**{n_done}/{len(active_steps)}** steps · Now: {cur_label}")

        # Step grid
        cols = st.columns(4)
        for i, s in enumerate(active_steps):
            with cols[i % 4]:
                if s in completed:
                    st.markdown(f'<div class="srow s-done"><span class="sdot">✓</span><span class="slbl">{STEP_LABELS[s]}</span></div>', unsafe_allow_html=True)
                elif s == current:
                    st.markdown(f'<div class="srow s-act"><span class="sdot">◉</span><span class="slbl">{STEP_LABELS[s]}</span></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="srow s-wait"><span class="sdot">○</span><span class="slbl">{STEP_LABELS[s]}</span></div>', unsafe_allow_html=True)

        if p.error:
            st.error(f"Pipeline error: {p.error}")
            st.session_state._running = False

        time.sleep(0.5)
        st.rerun()

    # ═══ STATE: DONE ═══
    if st.session_state._done:
        p = get_progress()
        state = p.step_results.get("__state__", {})
        decision = p.step_results.get("__decision__", "")

        # Completion notification + batch queue drain
        if not st.session_state.get("_notified", False):
            st.session_state._notified = True
            st.toast("Analysis complete!")
            st.toast("Open report tabs to review results.")
            # Auto-drain batch queue
            if st.session_state._batch_queue:
                st.session_state._batch_queue.pop(0)

        # Fallback: use cached result if pipeline didn't populate state (e.g. page reload after crash)
        if (not isinstance(state, dict) or not state) and st.session_state._cached_result:
            cached = st.session_state._cached_result
            state = cached
            decision = cached.get("final_trade_decision", "")
        if not isinstance(state, dict): state = {}
        if not isinstance(decision, str): decision = str(decision)

        # Show cache indicator
        if st.session_state._from_cache and st.session_state._cached_result:
            cached_date = st.session_state._cached_result.get("trade_date", "unknown")
            cached_depth = st.session_state._cached_result.get("depth", "")
            st.info(f"Showing cached analysis · Date: **{cached_date}** · Depth: **{cached_depth}** · Click **Run Analysis** to refresh.")

        # Rating
        rating = "HOLD"
        for r in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
            if r.lower() in decision.lower():
                rating = r.upper(); break

        st.markdown(f'<span class="badge badge-{rating}">{rating}</span>', unsafe_allow_html=True)

        # ── Dashboard Tab ──
        dashboard_tab = st.tabs(["Dashboard"])[0]
        with dashboard_tab:
            signal = state.get("structured_decision", {}) if isinstance(state, dict) else {}
            debate = state.get("investment_debate_state", {}) if isinstance(state, dict) else {}
            rounds = debate.get("count", 0) if isinstance(debate, dict) else 0
            qg = state.get("data_quality_summary", "")
            n_ok = qg.count(": A") + qg.count(": B") if qg else 0

            # KPI cards row
            if isinstance(signal, dict) and signal:
                dc1, dc2, dc3, dc4, dc5 = st.columns(5)
                with dc1:
                    st.markdown(f'<div class="mc"><div class="mcl">Final Rating</div><div class="mcv">{signal.get("action", rating)}</div></div>', unsafe_allow_html=True)
                with dc2:
                    conf = signal.get("confidence", 0)
                    st.markdown(f'<div class="mc"><div class="mcl">Confidence</div><div class="mcv">{conf:.0%}</div><div class="mcs">Risk Score: {signal.get("risk_score", 0):.0%}</div></div>', unsafe_allow_html=True)
                with dc3:
                    tp = signal.get("target_price")
                    tp_str = f"{'¥' if market == 'a_stock' else '$'}{tp:.2f}" if tp else "—"
                    st.markdown(f'<div class="mc"><div class="mcl">Target Price</div><div class="mcv">{tp_str}</div></div>', unsafe_allow_html=True)
                with dc4:
                    st.markdown(f'<div class="mc"><div class="mcl">Data Quality</div><div class="mcv">{n_ok}/7</div><div class="mcs">A/B grade reports</div></div>', unsafe_allow_html=True)
                with dc5:
                    st.markdown(f'<div class="mc"><div class="mcl">Debate Rounds</div><div class="mcv">{rounds}</div><div class="mcs">Bull vs Bear</div></div>', unsafe_allow_html=True)
            else:
                dc1, dc2, dc3, dc4 = st.columns(4)
                with dc1:
                    st.markdown(f'<div class="mc"><div class="mcl">Final Rating</div><div class="mcv">{rating}</div></div>', unsafe_allow_html=True)
                with dc2:
                    st.markdown(f'<div class="mc"><div class="mcl">Data Quality</div><div class="mcv">{n_ok}/7</div><div class="mcs">A/B grade reports</div></div>', unsafe_allow_html=True)
                with dc3:
                    st.markdown(f'<div class="mc"><div class="mcl">Debate Rounds</div><div class="mcv">{rounds}</div><div class="mcs">Bull vs Bear</div></div>', unsafe_allow_html=True)
                with dc4:
                    consensus = "—"
                    st.markdown(f'<div class="mc"><div class="mcl">Analyst Consensus</div><div class="mcv">{consensus}</div></div>', unsafe_allow_html=True)

            st.markdown('<div style="margin-top:12px"></div>', unsafe_allow_html=True)

            # ── Decision Summary Table ──
            st.markdown("#### Portfolio Manager — Decision Summary")
            dec_fields = []
            key_labels = {
                "rating": "Rating", "confidence": "Confidence",
                "reasoning": "Reasoning", "risk_assessment": "Risk Assessment",
                "position_advice": "Position Advice", "time_horizon": "Time Horizon",
                "executive_summary": "Executive Summary",
                "investment_thesis": "Investment Thesis",
            }
            # Format 1: Python dict literal {'key': 'value', ...}
            if decision.strip().startswith("{") and decision.strip().endswith("}"):
                try:
                    import ast
                    data = ast.literal_eval(decision.strip())
                    if isinstance(data, dict):
                        for k, v in data.items():
                            label = key_labels.get(k, k.replace("_", " ").title())
                            if True:
                                dec_fields.append((label, str(v) if not isinstance(v, str) else v))
                except Exception:
                    pass
            # Format 2: Markdown **Key**: value
            if not dec_fields:
                for line in decision.split("\n"):
                    line = line.strip()
                    if line.startswith("**") and "**:" in line:
                        parts = line.split("**: ", 1)
                        key = parts[0].replace("**", "").strip()
                        val = parts[1].strip()
                        if val:
                            label = key_labels.get(key.lower(), key)
                            dec_fields.append((label, val))
            # Format 3: SignalProcessor structured data
            if not dec_fields and isinstance(signal, dict) and signal:
                for k in ("reasoning", "risk_score", "confidence"):
                    if signal.get(k):
                        dec_fields.append((key_labels.get(k, k.title()), str(signal[k])))

            if dec_fields:
                rows = "".join(
                    f'<tr><td style="padding:10px 16px;color:#1f1f1f;font-weight:600;white-space:nowrap;border-bottom:1px solid #f0f0f0;vertical-align:top;width:160px;font-size:0.92rem">{k}</td>'
                    f'<td style="padding:10px 16px;color:#434343;border-bottom:1px solid #f0f0f0;font-size:0.92rem;line-height:1.55">{v}</td></tr>'
                    for k, v in dec_fields
                )
                st.markdown(f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px;background:#fff;border-radius:8px;border:1px solid #f0f0f0"><tr><th colspan="2" style="text-align:left;padding:10px 16px;background:#e6f7ff;color:#096dd9;font-size:0.88rem;font-weight:600;border-radius:8px 8px 0 0">Portfolio Manager Decision</th></tr>{rows}</table>', unsafe_allow_html=True)
            else:
                clean = " ".join(l.strip() for l in (decision or "").split("\n") if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("**Rating"))
                if clean:
                    st.markdown(f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px;background:#fff;border-radius:8px;border:1px solid #f0f0f0"><tr><th style="text-align:left;padding:10px 16px;background:#e6f7ff;color:#096dd9;font-size:0.88rem;font-weight:600;border-radius:8px 8px 0 0">Summary</th></tr><tr><td style="padding:10px 16px;color:#434343;font-size:0.92rem;line-height:1.55">{clean[:600]}</td></tr></table>', unsafe_allow_html=True)

            # ── 7-Analyst Reports ──
            st.markdown("#### 7-Analyst Reports")
            import re as _re
            analyst_reports = [
                ("Market/Tech", "market_report", "K-line, Technical indicators, Price/Volume history"),
                ("Sentiment", "sentiment_report", "News headlines, Market breadth, Social sentiment"),
                ("News", "news_report", "Eastmoney/Sina (A-stock), IB News/Yfinance (US/HK)"),
                ("Fundamentals", "fundamentals_report", "PE/PB, Financial statements, Profitability metrics"),
                ("Policy", "policy_report", "Policy news, Regulatory announcements, Macro data"),
                ("Hot Money", "hot_money_report", "Fund flow (北向资金), Capital flow, Volume analysis"),
                ("Lockup", "lockup_report", "Lockup expiry data, Insider transactions, Share pledge"),
            ]
            report_rows = ""
            for label, key, data_input in analyst_reports:
                content = state.get(key, "") if isinstance(state, dict) else ""
                # Extract first meaningful sentence after the [DIRECTION] line
                finding = "—"
                if content:
                    lines = content.split("\n")
                    for line in lines:
                        clean = line.strip().lstrip("#-* ").strip()
                        if clean and len(clean) > 25 and not clean.startswith("[DIRECTION]") and not clean.startswith("[KPI]"):
                            finding = clean[:150] + ("…" if len(clean) > 150 else "")
                            break
                report_rows += (
                    f'<tr>'
                    f'<td style="padding:8px 12px;color:#1f1f1f;font-size:0.88rem;font-weight:600;border-bottom:1px solid #e6f7ff;white-space:nowrap;vertical-align:top;width:140px">{label}</td>'
                    f'<td style="padding:8px 12px;color:#595959;font-size:0.82rem;border-bottom:1px solid #e6f7ff;white-space:nowrap;vertical-align:top;width:150px">{data_input}</td>'
                    f'<td style="padding:8px 12px;color:#434343;font-size:0.85rem;border-bottom:1px solid #e6f7ff;line-height:1.4">{finding}</td>'
                    f'</tr>'
                )
            st.markdown(
                f'<div class="dash-panel" style="background:#fff;border-color:#f0f0f0"><table style="width:100%;border-collapse:collapse;background:#fff">'
                f'<tr><th style="text-align:left;padding:8px 12px;color:#096dd9;font-size:0.78rem;text-transform:uppercase;background:#e6f7ff">Analyst</th>'
                f'<th style="text-align:left;padding:8px 12px;color:#096dd9;font-size:0.78rem;text-transform:uppercase;background:#e6f7ff">Data Input</th>'
                f'<th style="text-align:left;padding:8px 12px;color:#096dd9;font-size:0.78rem;text-transform:uppercase;background:#e6f7ff">Key Finding</th></tr>'
                f'{report_rows}</table></div>',
                unsafe_allow_html=True,
            )

            # ── Decision Chain Summary — 6 key agents ──
            st.markdown("#### Decision Chain Summary")
            import re as _re2

            def _first_meaningful(text, max_len=160):
                """Extract first substantive sentence from text, skipping headers/labels."""
                if not text:
                    return "—"
                for line in text.split("\n"):
                    s = line.strip().lstrip("#-*• ").strip()
                    # Skip header lines, formatting garbage, and too-short fragments
                    if not s or len(s) < 20:
                        continue
                    if s.startswith(("```", "---", "===", "[DIRECTION]", "[KPI]")):
                        continue
                    if ":" in s[:40] and len(s.split(":")[0]) < 25:
                        # This is a labeled line like "Recommendation: Buy" — use it
                        return s[:max_len] + ("…" if len(s) > max_len else "")
                    if len(s) > 30 and any(
                        kw in s.lower()
                        for kw in ["buy", "sell", "hold", "overweight", "underweight",
                                   "bullish", "bearish", "看好", "看空", "买入", "卖出",
                                   "growth", "risk", "position", "entry", "stop",
                                   "recommend", "recommendation", "rating", "target"]
                    ):
                        return s[:max_len] + ("…" if len(s) > max_len else "")
                # Fallback: first line over 20 chars
                for line in text.split("\n"):
                    s = line.strip().lstrip("#-*• ").strip()
                    if len(s) > 20:
                        return s[:max_len] + ("…" if len(s) > max_len else "")
                return text[:max_len]

            def _extract_rating(text):
                """Extract rating keyword from text."""
                for kw in ["Buy", "Overweight", "Hold", "Underweight", "Sell",
                           "买入", "增持", "持有", "减持", "卖出"]:
                    if kw.lower() in text.lower():
                        return kw
                return None

            chain_items = []

            # ── 1. Quality Gate ──
            qg = state.get("data_quality_summary", "") if isinstance(state, dict) else ""
            n_a = qg.count(": A") + qg.count(": B") if qg else 0
            n_total = 7
            # Find flagged/failed analysts
            flagged = []
            for line in qg.split("\n"):
                if "⚠ Flagged" in line:
                    flagged_part = line.split(":", 1)[-1].strip() if ":" in line else ""
                    flagged = [f.strip() for f in flagged_part.split(",") if f.strip()]
                    break
            if flagged:
                qg_output = f"{n_a}/{n_total} passed. Issues: {', '.join(flagged[:3])}"
            elif n_a == n_total:
                qg_output = f"All {n_total} reports passed quality review"
            else:
                qg_output = f"{n_a}/{n_total} reports passed quality review"
            chain_items.append(("Quality Gate", "7 Analyst Reports", qg_output))

            # ── 2. Bull vs Bear Debate ──
            debate = state.get("investment_debate_state", {}) if isinstance(state, dict) else {}
            rounds = debate.get("count", 0) if isinstance(debate, dict) else 0
            bull_hist = debate.get("bull_history", "") if isinstance(debate, dict) else ""
            bear_hist = debate.get("bear_history", "") if isinstance(debate, dict) else ""

            def _extract_side_conclusion(history: str, max_len: int = 200) -> str:
                """Extract the last substantive paragraph from one side's debate history."""
                if not history:
                    return ""
                # Split on "Bull Analyst:" or "Bear Analyst:" to get individual arguments
                # Take the last segment and find the most substantive sentence group
                segments = history.split("\n")
                # Collect last 5 lines that are actual content (not labels)
                content_lines = []
                for line in reversed(segments):
                    s = line.strip()
                    if not s or len(s) < 20:
                        continue
                    if s.startswith(("Bull Analyst:", "Bear Analyst:", "---")):
                        if content_lines:
                            break  # hit next argument label, stop
                    content_lines.append(s)
                    if len(" ".join(reversed(content_lines))) > max_len:
                        break
                result = " ".join(reversed(content_lines))
                return result[:max_len] + ("…" if len(result) > max_len else "")

            bull_conclusion = _extract_side_conclusion(bull_hist)
            bear_conclusion = _extract_side_conclusion(bear_hist)

            if bull_conclusion and bear_conclusion:
                debate_output = (
                    f'<b style="color:#60a5fa">Bull</b>: {bull_conclusion}'
                    f'<br><br>'
                    f'<b style="color:#f87171">Bear</b>: {bear_conclusion}'
                )
            elif rounds > 0:
                debate_output = f"Debate completed ({rounds} rounds) — see full report for details"
            else:
                debate_output = "Debate not started"
            chain_items.append(("Bull vs Bear Debate", "7 Analyst Reports, Quality Gate summary", debate_output))

            # ── 3. Research Manager ──
            invest_plan = state.get("investment_plan", "") if isinstance(state, dict) else ""
            rm_rec = ""
            rm_rationale = ""
            for line in invest_plan.split("\n"):
                s = line.strip()
                if ("Recommendation" in s or "推荐" in s) and len(s) > 10:
                    rm_rec = s[:120]
                elif ("Rationale" in s or "理由" in s or "原因" in s) and len(s) > 10:
                    rm_rationale = s[:160]
            if not rm_rec:
                # Look for rating keyword directly
                rating = _extract_rating(invest_plan)
                if rating:
                    rm_rec = f"Recommendation: **{rating}**"
                elif invest_plan:
                    rm_rec = _first_meaningful(invest_plan, 140)
            if rm_rationale:
                rm_rec = f"{rm_rec} — {rm_rationale}"
            chain_items.append(("Research Manager", "Bull vs Bear debate history", rm_rec or "Investment plan generated"))

            # ── 4. Trader ──
            trader_plan = state.get("trader_investment_plan", "") if isinstance(state, dict) else ""
            tr_action = ""
            tr_entry = ""
            tr_stop = ""
            for line in trader_plan.split("\n"):
                s = line.strip()
                lower = s.lower()
                if ("action" in lower or "direction" in lower or "方向" in s) and len(s) > 8:
                    tr_action = s[:100]
                elif ("entry" in lower or "入场" in s or "买入价" in s) and len(s) > 8:
                    tr_entry = s[:80]
                elif ("stop" in lower or "止损" in s) and len(s) > 8:
                    tr_stop = s[:80]
            if not tr_action:
                rating = _extract_rating(trader_plan)
                if rating:
                    tr_action = f"Action: **{rating.upper()}**"
                elif trader_plan:
                    tr_action = _first_meaningful(trader_plan, 140)
            extras = " | ".join(p for p in [tr_entry, tr_stop] if p)
            if extras:
                tr_action = f"{tr_action} ({extras})" if tr_action else extras
            chain_items.append(("Trader", "Research Manager's investment plan", tr_action or "Transaction plan generated"))

            # ── 5. Risk Debate ──
            risk = state.get("risk_debate_state", {}) if isinstance(state, dict) else {}
            risk_rounds = risk.get("count", 0) if isinstance(risk, dict) else 0
            agg_hist = risk.get("aggressive_history", "") if isinstance(risk, dict) else ""
            con_hist = risk.get("conservative_history", "") if isinstance(risk, dict) else ""
            neu_hist = risk.get("neutral_history", "") if isinstance(risk, dict) else ""

            # Try to find the structured stance from each analyst
            agg_stance = _extract_rating(agg_hist[-500:]) or ""
            con_stance = _extract_rating(con_hist[-500:]) or ""
            neu_stance = _extract_rating(neu_hist[-500:]) or ""

            if risk_rounds > 0:
                stances = []
                for label, stance in [("Aggressive", agg_stance), ("Conservative", con_stance), ("Neutral", neu_stance)]:
                    if stance:
                        stances.append(f"{label}: {stance}")
                if stances:
                    risk_output = "; ".join(stances)
                else:
                    risk_output = f"3-party debate: {risk_rounds} rounds — see full report"
            else:
                risk_output = "Risk debate not started"
            chain_items.append(("Risk Debate", "Trader's proposal, Research Manager's plan", risk_output))

            # ── 6. Portfolio Manager ──
            final_dec = state.get("final_trade_decision", "") if isinstance(state, dict) else ""
            pm_rating = signal.get("action", rating) if isinstance(signal, dict) else rating
            pm_conf = signal.get("confidence", 0) if isinstance(signal, dict) else 0
            # Try to extract executive summary from the structured output
            pm_summary = ""
            for line in final_dec.split("\n"):
                s = line.strip().lstrip("#-*• ").strip()
                if ("Executive Summary" in s or "执行摘要" in s or "executive_summary" in s.lower()) and len(s) > 20:
                    pm_summary = s[:180]
                    break
            if not pm_summary:
                pm_summary = _first_meaningful(final_dec, 160)
            if pm_summary:
                pm_output = f"**{pm_rating}** ({pm_conf:.0%} conf) — {pm_summary}"
            else:
                pm_output = f"**{pm_rating}** (confidence: {pm_conf:.0%})"
            chain_items.append(("Portfolio Manager", "Risk debate, Trader's plan, Research Manager's plan", pm_output))

            chain_rows = "".join(
                f'<tr><td style="padding:8px 12px;color:#1f1f1f;font-size:0.88rem;font-weight:600;border-bottom:1px solid #f0f0f0;white-space:nowrap;vertical-align:top;width:160px">{k}</td>'
                f'<td style="padding:8px 12px;color:#8c8c8c;font-size:0.82rem;border-bottom:1px solid #f0f0f0;white-space:nowrap;vertical-align:top;width:140px">{d}</td>'
                f'<td style="padding:8px 12px;color:#434343;font-size:0.85rem;border-bottom:1px solid #f0f0f0;line-height:1.4">{v}</td></tr>'
                for k, d, v in chain_items
            )
            st.markdown(
                f'<div class="dash-panel" style="background:#fff;border-color:#f0f0f0"><table style="width:100%;border-collapse:collapse;background:#fff">'
                f'<tr><th style="text-align:left;padding:8px 12px;color:#096dd9;font-size:0.78rem;text-transform:uppercase;background:#e6f7ff">Agent</th>'
                f'<th style="text-align:left;padding:8px 12px;color:#096dd9;font-size:0.78rem;text-transform:uppercase;background:#e6f7ff">Input</th>'
                f'<th style="text-align:left;padding:8px 12px;color:#096dd9;font-size:0.78rem;text-transform:uppercase;background:#e6f7ff">Decision / Conclusion</th></tr>'
                f'{chain_rows}</table></div>',
                unsafe_allow_html=True,
            )

        # ═══ Analyst Reports ═══
        st.markdown("---")
        st.markdown("## Analyst Reports")
        analyst_labels = ["Market", "Sentiment", "News", "Fundamentals", "Policy", "Hot Money", "Lockup"]
        analyst_keys = [
            ("Market/Tech", "market_report"), ("Sentiment", "sentiment_report"),
            ("News", "news_report"), ("Fundamentals", "fundamentals_report"),
            ("Policy", "policy_report"), ("Hot Money", "hot_money_report"),
            ("Lockup", "lockup_report"),
        ]
        analyst_tabs = st.tabs(analyst_labels)
        for tab, (label, key) in zip(analyst_tabs, analyst_keys):
            with tab:
                content = state.get(key, "") if isinstance(state, dict) else ""
                if content:
                    st.markdown(content)
                else:
                    st.info(f"No **{label}** report generated.")

        # ═══ Decision Chain ═══
        st.markdown("---")
        st.markdown("## Decision Chain")
        decision_labels = ["Invest Plan", "Trader Plan", "Debate", "Risk Debate", "PM Decision"]
        decision_tabs = st.tabs(decision_labels)

        # ── Invest Plan ──
        with decision_tabs[0]:
            content = state.get("investment_plan", "") if isinstance(state, dict) else ""
            if content:
                st.markdown(content)
            else:
                st.info("No investment plan generated.")

        # ── Trader Plan ──
        with decision_tabs[1]:
            content = state.get("trader_investment_plan", "") if isinstance(state, dict) else ""
            if content:
                st.markdown(content)
            else:
                st.info("No trader plan generated.")

        # ── Debate (Bull vs Bear full transcript) ──
        with decision_tabs[2]:
            debate_state = state.get("investment_debate_state", {}) if isinstance(state, dict) else {}
            debate_history = debate_state.get("history", "") if isinstance(debate_state, dict) else ""
            debate_rounds = debate_state.get("count", 0) if isinstance(debate_state, dict) else 0
            if debate_history:
                st.caption(f"**{debate_rounds} rounds** of adversarial debate between Bull and Bear researchers")
                st.markdown("---")
                st.markdown(debate_history)
            else:
                st.info("No debate transcript available.")

        # ── Risk Debate (3-way full transcript) ──
        with decision_tabs[3]:
            risk_state = state.get("risk_debate_state", {}) if isinstance(state, dict) else {}
            risk_history = risk_state.get("history", "") if isinstance(risk_state, dict) else ""
            risk_rounds = risk_state.get("count", 0) if isinstance(risk_state, dict) else 0
            if risk_history:
                st.caption(f"**{risk_rounds} rounds** of 3-way risk debate (Aggressive · Conservative · Neutral)")
                st.markdown("---")
                st.markdown(risk_history)
            else:
                st.info("No risk debate transcript available.")

        # ── PM Decision (full Portfolio Manager report) ──
        with decision_tabs[4]:
            content = state.get("final_trade_decision", "") if isinstance(state, dict) else ""
            if content:
                st.markdown(content)
            else:
                st.info("No portfolio manager decision available.")

    # ═══ STATE: BATCH PROCESSING ═══
    if not st.session_state._running and st.session_state._batch_queue and not st.session_state._batch_running:
        pass  # Manual trigger via Run Analysis

    # ═══ STATE: IDLE ═══
    if not st.session_state._running and not st.session_state._done:
        if st.session_state._batch_queue:
            st.info(f"Queue has {len(st.session_state._batch_queue)} symbols. Click **Run Analysis** to process '{st.session_state._batch_queue[0]}'.")
        else:
            st.info("Enter a stock symbol and click **Run Analysis** to start.")


if __name__ == "__main__":
    run()
