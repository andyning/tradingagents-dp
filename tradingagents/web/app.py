"""Streamlit Web UI — Professional Financial Dashboard.

Clean light theme, real-time step progress, token tracking, dashboard overview.
"""

from __future__ import annotations

import threading
import time
import warnings

import pandas as pd
import streamlit as st

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed database.*")
warnings.filterwarnings("ignore", message=".*unclosed .*socket.*")

st.set_page_config(page_title="TradingAgents", page_icon="", layout="wide", initial_sidebar_state="expanded")

# ── CSS ─────────────────────────────────────────────────────────────────
st.markdown("""<style>
    .stApp { background: #f8fafc; }
    .main .block-container { padding: 1.5rem 2rem; max-width: 1400px; }
    /* Sidebar — Mars Green */
    section[data-testid="stSidebar"] { background: #018474; border-right: none; }
    section[data-testid="stSidebar"] h3 { color: #fff !important; font-size: 1.6rem !important; font-weight: 800 !important; letter-spacing: .02em !important; }
    section[data-testid="stSidebar"] .stCaption { color: rgba(255,255,255,.7) !important; font-size: 0.8rem !important; }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div { color: #fff !important; }
    section[data-testid="stSidebar"] .stMarkdown p strong { color: #fff !important; font-weight: 700 !important; font-size: 0.82rem !important; letter-spacing: .04em !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.2) !important; }
    /* Sidebar input labels: bold */
    .ig-label { font-size: 0.7rem !important; color: rgba(255,255,255,.8) !important; font-weight: 700 !important; text-transform: uppercase; letter-spacing: .06em; margin: 10px 0 4px 0; }
    h2, h3 { color: #111827; font-weight: 600; }
    .mc { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px 16px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
    .mc .mcl { font-size: 0.68rem; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; font-weight: 500; }
    .mc .mcv { font-size: 1.25rem; font-weight: 700; color: #111827; }
    .mc .mcs { font-size: 0.78rem; margin-top: 2px; }
    .up { color: #059669; } .down { color: #dc2626; }
    .badge { display: inline-block; padding: 5px 20px; border-radius: 6px; font-weight: 700; font-size: .95rem; letter-spacing: .03em; }
    .badge-BUY { background: #d1fae5; color: #065f46; border: 1px solid #10b981; }
    .badge-OVERWEIGHT { background: #dbeafe; color: #1e40af; border: 1px solid #3b82f6; }
    .badge-HOLD { background: #fef3c7; color: #92400e; border: 1px solid #f59e0b; }
    .badge-UNDERWEIGHT { background: #ffedd5; color: #9a3412; border: 1px solid #f97316; }
    .badge-SELL { background: #fee2e2; color: #991b1b; border: 1px solid #ef4444; }
    .srow { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
    .sdot { width: 14px; text-align: center; font-size: .7rem; flex-shrink: 0; }
    .slbl { font-size: .78rem; white-space: nowrap; }
    .s-act .sdot { color: #2563eb; } .s-act .slbl { color: #2563eb; font-weight: 600; }
    .s-done .sdot { color: #059669; } .s-done .slbl { color: #059669; }
    .s-wait .sdot { color: #d1d5db; } .s-wait .slbl { color: #9ca3af; }
    .tbox { text-align: center; padding: 8px 4px; background: rgba(255,255,255,.15); border-radius: 6px; }
    .tbox .tv { font-size: .88rem; font-weight: 700; color: #fff; }
    .tbox .tl { font-size: .62rem; color: rgba(255,255,255,.7); text-transform: uppercase; }
    .dash-panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 2px rgba(0,0,0,.04); margin-bottom: 10px; }
    .dash-panel h4 { color: #111827; font-size: .85rem; font-weight: 600; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #f1f5f9; }
    .dash-panel p { font-size: .8rem; color: #4b5563; line-height: 1.5; }
    .stProgress > div > div > div > div { background: #2563eb; }
    /* Input field emphasis */
    section[data-testid="stSidebar"] input[type="text"],
    section[data-testid="stSidebar"] [data-baseweb="select"],
    section[data-testid="stSidebar"] [data-testid="stDateInput"] input {
        border: 1.5px solid rgba(255,255,255,.4) !important; border-radius: 6px !important; background: #fff !important; color: #111827 !important;
    }
    section[data-testid="stSidebar"] input[type="text"]::placeholder { color: #9ca3af !important; }
    section[data-testid="stSidebar"] [data-baseweb="select"] * { color: #111827 !important; }
    /* Run & Clear buttons: Prussian blue */
    section[data-testid="stSidebar"] button[kind="primary"],
    section[data-testid="stSidebar"] button[kind="secondary"] {
        background: #0D3869 !important; border-color: #0D3869 !important; color: #fff !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"]:hover,
    section[data-testid="stSidebar"] button[kind="secondary"]:hover {
        background: #0a2d55 !important; border-color: #0a2d55 !important;
    }
    header, footer, #MainMenu { visibility: hidden; }
    /* Refresh button — match Prussian blue */
    .stButton button { border-radius: 6px !important; font-size: 0.78rem !important; padding: 4px 12px !important;
        color: #fff !important; border: 1px solid #0D3869 !important; background: #0D3869 !important; font-weight: 500 !important; }
    .stButton button:hover { background: #0a2d55 !important; border-color: #0a2d55 !important; }
    header, footer, #MainMenu { visibility: hidden; }
</style>""", unsafe_allow_html=True)

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
    except Exception as exc:
        finish(error=str(exc))

# ── Stock info + K-line (single fetch, cached) ────────────────────────
@st.cache_data(show_spinner=False, ttl=1800)
def _fetch_stock_data(symbol: str, market: str, days: int = 30):
    """Return (info_dict, kline_dataframe). Single network call for both."""
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
        info = {"symbol": symbol, "market": market, "name": symbol}
        if not df.empty:
            last = df.iloc[-1]
            for k in ("close", "pe", "pb", "change_pct", "volume", "turn", "amount"):
                try:
                    info[k] = float(pd.to_numeric(last[k], errors="coerce"))
                except Exception:
                    info[k] = None
            # Volume ratio: last 5-day avg vs 20-day avg
            try:
                vol = pd.to_numeric(df["volume"], errors="coerce")
                if len(vol) >= 20:
                    info["vol_ratio"] = float(vol.iloc[-5:].mean() / vol.iloc[-20:].mean())
            except Exception:
                info["vol_ratio"] = None
        # Get display name — multi-source fallback per market
        info["name"] = _lookup_stock_name(symbol, market)
        # Enrich with extra metrics from Futu if available
        info = _enrich_stock_info(info, symbol, market)
        return info, df
    except Exception:
        return {"symbol": symbol, "market": market, "name": symbol}, pd.DataFrame()


def _enrich_stock_info(info: dict, symbol: str, market: str) -> dict:
    """Add extra metrics: market cap, float shares, etc. from Futu."""
    try:
        from futu import OpenQuoteContext
        futu_sym = symbol.strip().upper()
        if market == "a_stock":
            futu_sym = f"{'SH' if futu_sym.startswith('6') else 'SZ'}.{futu_sym}"
        elif market == "hk_stock":
            futu_sym = f"HK.{futu_sym:0>5}"
        else:
            futu_sym = f"US.{futu_sym}"
        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        ret, df = ctx.get_market_snapshot([futu_sym])
        ctx.close()
        if ret == 0 and df is not None and not df.empty:
            row = df.iloc[0]
            # Map Futu fields to our info dict
            field_map = {
                "market_cap": "market_cap",        # 总市值
                "circular_cap": "circular_cap",    # 流通市值
                "total_shares": "total_shares",    # 总股本
                "float_shares": "float_shares",    # 流通股
                "amplitude": "amplitude",           # 振幅
                "pe_forward": "pe_forward",         # PE-动 (forward PE)
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
                eps = row.get("eps_ttm") or row.get("basic_eps")
                if eps is not None:
                    eps_val = float(eps)
                    info["is_profitable"] = "盈利" if eps_val > 0 else "亏损"
                else:
                    info["is_profitable"] = "—"
            except Exception:
                info["is_profitable"] = "—"
    except Exception:
        pass
    return info


def _lookup_stock_name(symbol: str, market: str) -> str:
    """Look up company name from available data sources."""
    s = symbol.strip().upper()
    # A-stock: Baostock → Futu
    if market == "a_stock":
        try:
            import baostock as bs
            prefix = "sh." if s.startswith("6") else "sz."
            bs.login()
            rs = bs.query_stock_basic(code=f"{prefix}{s}")
            while rs.next():
                row = rs.get_row_data()
                if len(row) > 1 and row[1] and row[1] != s:
                    bs.logout()
                    return str(row[1])
            bs.logout()
        except Exception:
            pass
        try:
            from futu import OpenQuoteContext
            ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
            ret, df = ctx.get_market_snapshot([f"{'SH' if s.startswith('6') else 'SZ'}.{s}"])
            ctx.close()
            if ret == 0 and df is not None and not df.empty:
                name = df.iloc[0].get("name", "")
                if name and name != s:
                    return str(name)
        except Exception:
            pass
    # HK stock: Futu → yfinance
    elif market == "hk_stock":
        try:
            from futu import OpenQuoteContext
            ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
            ret, df = ctx.get_market_snapshot([f"HK.{s:0>5}"])
            ctx.close()
            if ret == 0 and df is not None and not df.empty:
                name = df.iloc[0].get("name", "")
                if name and name != s:
                    return str(name)
        except Exception:
            pass
        try:
            import yfinance as yf
            t = yf.Ticker(f"{s:0>4}.HK")
            info = t.info
            name = info.get("longName") or info.get("shortName") or ""
            if name and name != s:
                return str(name)
        except Exception:
            pass
    # US stock: yfinance → Futu
    elif market == "us_stock":
        try:
            import yfinance as yf
            t = yf.Ticker(s)
            info = t.info
            name = info.get("longName") or info.get("shortName") or ""
            if name and name != s and len(name) < 50:
                return str(name)
        except Exception:
            pass
        try:
            from futu import OpenQuoteContext
            ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
            ret, df = ctx.get_market_snapshot([f"US.{s}"])
            ctx.close()
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


# ── Auto-detect market from symbol ──────────────────────────────────────
def _detect_market(symbol: str) -> str:
    """Guess the market from the ticker format."""
    s = symbol.strip().upper().replace(" ", "")
    if not s:
        return "a_stock"
    if s.isalpha() and len(s) <= 5:
        return "us_stock"
    if s.isdigit() and len(s) == 6:
        return "a_stock"
    if s.isdigit() and len(s) <= 5:
        return "hk_stock"
    if s.startswith("SH.") or s.startswith("SZ."):
        return "a_stock"
    if s.endswith(".HK"):
        return "hk_stock"
    return "a_stock"


def _market_label(m: str) -> str:
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


def _check_data_sources():
    """Quick health check — runs once per session, skips heavy network tests on startup."""
    if st.session_state.get("_health_checked"):
        return
    st.session_state._health_checked = True
    # Run checks in background thread to avoid blocking UI
    def _bg_health():
        # Baostock
        try:
            import baostock as bs
            lg = bs.login()
            st.session_state._health_baostock = "OK" if lg.error_code == "0" else "DOWN"
            bs.logout()
        except Exception:
            st.session_state._health_baostock = "DOWN"
        # Futu
        try:
            from futu import OpenQuoteContext
            ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
            ctx.close()
            st.session_state._health_futu = "OK"
        except Exception:
            st.session_state._health_futu = "DOWN"
        # Eastmoney
        try:
            import requests
            r = requests.get("https://push2.eastmoney.com/api/qt/stock/get", timeout=3,
                            headers={"User-Agent": "Mozilla/5.0"})
            st.session_state._health_eastmoney = "OK" if r.status_code == 200 else "DOWN"
        except Exception:
            st.session_state._health_eastmoney = "DOWN"

    threading.Thread(target=_bg_health, daemon=True).start()


# ── Main ────────────────────────────────────────────────────────────────
def run():
    from tradingagents.graph.progress import get_progress, STEP_LABELS

    # Run health check once per session
    _check_data_sources()

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
        st.caption("Multi-Agent Investment Research")
        st.divider()

        # Input section with visual emphasis
        st.markdown("""
        <style>
        .input-group { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px; padding: 2px 12px 8px 12px; margin-bottom: 8px; }
        .input-group .ig-label { font-size: 0.7rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin: 8px 0 2px 0; }
        </style>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ig-label" style="margin-top:0">Stock Symbol</div>', unsafe_allow_html=True)
        symbol = st.text_input("symbol_input", "688775", placeholder="输入股票代码", label_visibility="collapsed")

        st.markdown('<div class="ig-label">Analysis Date</div>', unsafe_allow_html=True)
        trade_date = st.date_input("date_input", pd.Timestamp.now(), label_visibility="collapsed").strftime("%Y-%m-%d")

        st.markdown('<div class="ig-label">Market</div>', unsafe_allow_html=True)
        market = _detect_market(symbol)
        st.markdown(f'<div style="color:rgba(255,255,255,.45);font-size:0.78rem;padding:4px 0">{_market_label(market)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="ig-label">Data Window</div>', unsafe_allow_html=True)
        data_window = st.selectbox("window_select", [30, 60, 120, 250], index=0,
                                   format_func=lambda x: f"{x} trading days ({x//21}月)",
                                   label_visibility="collapsed")

        st.markdown('<div class="ig-label">Analysis Depth</div>', unsafe_allow_html=True)
        depth = st.selectbox("depth_select", ["light", "medium", "deep"], index=1,
                             format_func=lambda x: {"light": "Light (5 steps, ~2 min)", "medium": "Medium (13 steps, ~8 min)", "deep": "Deep (16 steps, ~12 min)"}[x],
                             label_visibility="collapsed")
        st.divider()

        # Data source health — vertical layout with large dots
        st.divider()
        st.markdown("**Data Sources**")
        for label, key in [("Futu", "futu"), ("Baostock", "baostock"), ("Eastmoney", "eastmoney")]:
            status = st.session_state.get(f"_health_{key}", "?")
            color = {"OK": "green", "?": "gray"}.get(status, "orange")
            st.markdown(
                f'<span style="font-size:1.2rem;color:{color};margin-right:8px">●</span>'
                f'<span style="color:rgba(255,255,255,.9);font-size:0.78rem">{label}</span>'
                f'<span style="color:rgba(255,255,255,.4);font-size:0.7rem;margin-left:6px">({status})</span>',
                unsafe_allow_html=True,
            )

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
        can_run = not st.session_state._running
        if st.button("▶  Run Analysis", type="primary", disabled=not can_run, use_container_width=True):
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

        # Token display (always visible)
        st.divider()
        p_now = get_progress()
        st.markdown("**Token Usage**")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="tbox"><div class="tv">{p_now.tokens_in:,}</div><div class="tl">Input</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="tbox"><div class="tv">{p_now.tokens_out:,}</div><div class="tl">Output</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="tbox"><div class="tv">{p_now.tokens_total:,}</div><div class="tl">Total</div></div>', unsafe_allow_html=True)

        # Report export (always visible when analysis done)
        p_done = get_progress()
        state_done = p_done.step_results.get("__state__", {})
        if isinstance(state_done, dict) and state_done:
            report_md = _build_export_report(state_done, symbol, trade_date, market, depth)
            st.download_button(
                label="Export Report (Markdown)",
                data=report_md,
                file_name=f"{symbol}_{trade_date}_{depth}.md",
                mime="text/markdown",
                use_container_width=True,
            )

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
    import datetime as _dt
    info, kline_df = _fetch_stock_data(symbol, market)

    # Stock header + refresh
    rcol1, rcol2 = st.columns([25, 2])
    with rcol1:
        st.caption(f"Data as of {_dt.datetime.now().strftime('%H:%M:%S')} · 30 min cache")
    with rcol2:
        if st.button("Refresh", key="refresh_data_btn", help="Refresh stock data & K-line chart"):
            _fetch_stock_data.clear()
            st.rerun()

    def _mc(label, value, fmt=None, color_class=""):
        if value is None or (isinstance(value, float) and value != value):
            display = "—"
        elif fmt == "pct":
            sgn = "+" if value >= 0 else ""
            display = f"{sgn}{value:.2f}%"
        elif fmt == "pe":
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
                name="Price", increasing_line_color="#059669", decreasing_line_color="#dc2626",
            ))
            fig.add_trace(go.Bar(
                x=kdf["date"], y=kdf["volume"], name="Volume",
                marker_color="rgba(37,99,235,0.3)", yaxis="y2",
            ))
            fig.update_layout(
                title=f"{symbol}  {info.get('name', '')}",
                xaxis_title="", yaxis_title="Price (¥)",
                template="plotly_white",
                height=420,
                margin=dict(l=0, r=0, t=50, b=0),
                showlegend=False,
                xaxis_rangeslider_visible=False,
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

        tab_labels = [
            "Dashboard 总览", "Market 技术", "Sentiment 舆情", "News 新闻", "Fundamentals 基本面",
            "Policy 政策", "Hot Money 资金", "Lockup 解禁", "Invest Plan 投资计划", "Trader Plan 交易方案",
        ]
        tabs = st.tabs(tab_labels)

        report_keys = [
            ("Market/Tech 技术分析", "market_report"), ("Sentiment 舆情分析", "sentiment_report"),
            ("News 新闻分析", "news_report"), ("Fundamentals 基本面分析", "fundamentals_report"),
            ("Policy 政策分析", "policy_report"), ("Hot Money 资金分析", "hot_money_report"),
            ("Lockup 解禁分析", "lockup_report"), ("Invest Plan 投资计划", "investment_plan"),
            ("Trader Plan 交易方案", "trader_investment_plan"),
        ]

        # ── Tab 0: Dashboard ──
        with tabs[0]:
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
            st.markdown("#### Investment Director — Decision Summary")
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
                    f'<tr><td style="padding:10px 16px;color:#6b7280;font-weight:600;white-space:nowrap;border-bottom:1px solid #f1f5f9;vertical-align:top;width:160px">{k}</td>'
                    f'<td style="padding:10px 16px;color:#111827;border-bottom:1px solid #f1f5f9;font-size:0.88rem;line-height:1.55">{v}</td></tr>'
                    for k, v in dec_fields
                )
                st.markdown(f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px">{rows}</table>', unsafe_allow_html=True)
            else:
                clean = " ".join(l.strip() for l in (decision or "").split("\n") if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("**Rating"))
                if clean:
                    st.markdown(f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px"><tr><td style="padding:10px 16px;color:#6b7280;font-weight:600;white-space:nowrap;border-bottom:1px solid #f1f5f9;vertical-align:top;width:160px">Summary</td><td style="padding:10px 16px;color:#111827;border-bottom:1px solid #f1f5f9;font-size:0.88rem;line-height:1.55">{clean[:600]}</td></tr></table>', unsafe_allow_html=True)

            # ── 7 Analysts Votes ──
            st.markdown("#### 7-Analysts Voting Summary")
            import re as _re
            analyst_labels = [
                ("Market/Tech 技术分析", "market_report"), ("Sentiment 舆情分析", "sentiment_report"),
                ("News 新闻分析", "news_report"), ("Fundamentals 基本面分析", "fundamentals_report"),
                ("Policy 政策分析", "policy_report"), ("Hot Money 资金分析", "hot_money_report"),
                ("Lockup 解禁分析", "lockup_report"),
            ]
            votes = []
            dir_colors = {"看多": "#059669", "看空": "#dc2626", "中性": "#6b7280", "放弃": "#9ca3af"}
            for label, key in analyst_labels:
                content = state.get(key, "") if isinstance(state, dict) else ""
                direction = "—"
                kpi = "—"
                if content:
                    m = _re.search(r'\[DIRECTION\]\s*:\s*(.+?)\s*\|', content)
                    if m:
                        direction = m.group(1).strip()
                    m2 = _re.search(r'\[KPI\]\s*:\s*(.+?)$', content, _re.MULTILINE)
                    if m2:
                        kpi = m2.group(1).strip()[:120]
                votes.append((label, direction, kpi))

            rows_html = ""
            bull = sum(1 for _, d, _ in votes if d == "看多")
            bear = sum(1 for _, d, _ in votes if d == "看空")
            neutral = sum(1 for _, d, _ in votes if d in ("中性", "放弃", "—"))
            for label, d, kpi in votes:
                color = dir_colors.get(d, "#9ca3af")
                kpi_display = kpi if kpi and kpi != "—" else "—"
                rows_html += (
                    f'<tr>'
                    f'<td style="padding:8px 12px;color:#374151;font-size:0.85rem;font-weight:600;border-bottom:1px solid #f1f5f9;white-space:nowrap">{label}</td>'
                    f'<td style="padding:8px 12px;color:{color};font-weight:700;font-size:0.85rem;border-bottom:1px solid #f1f5f9;white-space:nowrap">{d}</td>'
                    f'<td style="padding:8px 12px;color:#6b7280;font-size:0.82rem;border-bottom:1px solid #f1f5f9">{kpi_display}</td>'
                    f'</tr>'
                )
            tally = f"Bull {bull} · Bear {bear} · Neutral/Abstain {neutral}"
            tally_color = "#059669" if bull > bear else "#dc2626" if bear > bull else "#6b7280"
            st.markdown(
                f'<div class="dash-panel"><h4>7-Analyst Votes <span style="font-weight:400;color:{tally_color};font-size:0.85rem">({tally})</span></h4>'
                f'<table style="width:100%;border-collapse:collapse">'
                f'<tr><th style="text-align:left;padding:6px 12px;color:#9ca3af;font-size:0.7rem;text-transform:uppercase">Analyst</th>'
                f'<th style="text-align:left;padding:6px 12px;color:#9ca3af;font-size:0.7rem;text-transform:uppercase">Direction</th>'
                f'<th style="text-align:left;padding:6px 12px;color:#9ca3af;font-size:0.7rem;text-transform:uppercase">Key KPIs</th></tr>'
                f'{rows_html}</table></div>',
                unsafe_allow_html=True,
            )

        # ── Tabs 1-9: Reports ──
        for tab, (label, key) in zip(tabs[1:], report_keys):
            with tab:
                content = state.get(key, "") if isinstance(state, dict) else ""
                if content:
                    st.markdown(content)
                else:
                    st.info(f"No {label} report generated.")

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
