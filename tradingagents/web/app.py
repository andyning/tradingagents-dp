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
    /* Run button: Prussian blue */
    section[data-testid="stSidebar"] button[kind="primary"] {
        background: #0D3869 !important; border-color: #0D3869 !important; color: #fff !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"]:hover {
        background: #0a2d55 !important; border-color: #0a2d55 !important;
    }
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
        state, decision = graph.propagate(symbol, trade_date, market=market, depth=depth, data_window=data_window)
        p2 = finish()
        p2.step_results["__state__"] = state
        p2.step_results["__decision__"] = decision
    except Exception as exc:
        finish(error=str(exc))

# ── Stock info + K-line (single fetch, cached) ────────────────────────
@st.cache_data(show_spinner=False, ttl=1800)
def _fetch_stock_data(symbol: str, market: str, days: int = 30):
    """Return (info_dict, kline_dataframe). Single network call for both."""
    try:
        from tradingagents.data import a_stock, hk_stock, us_stock
        mod = {"a_stock": a_stock, "hk_stock": hk_stock, "us_stock": us_stock}.get(market, a_stock)
        end = pd.Timestamp.now().strftime("%Y-%m-%d")
        start = (pd.Timestamp.now() - pd.Timedelta(days=int(days * 1.6))).strftime("%Y-%m-%d")
        df = mod.get_kline_daily(symbol, start, end)
        info = {"symbol": symbol, "market": market, "name": symbol}
        if not df.empty:
            last = df.iloc[-1]
            for k in ("close", "pe", "pb", "change_pct", "volume", "turn"):
                try:
                    info[k] = float(pd.to_numeric(last[k], errors="coerce"))
                except Exception:
                    info[k] = None
        try:
            from tradingagents.data.sources.efinance import EfinanceSource
            q = EfinanceSource().quote(symbol)
            if not q.empty:
                for c in q.columns:
                    if "名称" in str(c) or "name" in str(c).lower():
                        info["name"] = str(q.iloc[0][c]); break
        except Exception:
            pass
        return info, df
    except Exception:
        return {"symbol": symbol, "market": market, "name": symbol}, pd.DataFrame()

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


# ── Main ────────────────────────────────────────────────────────────────
def run():
    from tradingagents.graph.progress import get_progress, STEP_LABELS

    # Init session keys
    if "_running" not in st.session_state: st.session_state._running = False
    if "_done" not in st.session_state: st.session_state._done = False
    if "_thread" not in st.session_state: st.session_state._thread = None
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
        market = st.selectbox("market_select", ["a_stock", "hk_stock", "us_stock"], index=0,
                              format_func=lambda x: {"a_stock": "A-Shares (A股)", "hk_stock": "Hong Kong (港股)", "us_stock": "US (美股)"}[x],
                              label_visibility="collapsed")

        st.markdown('<div class="ig-label">Data Window</div>', unsafe_allow_html=True)
        data_window = st.selectbox("window_select", [30, 60, 120, 250], index=0,
                                   format_func=lambda x: f"{x} trading days ({x//21}月)",
                                   label_visibility="collapsed")

        st.markdown('<div class="ig-label">Analysis Depth</div>', unsafe_allow_html=True)
        depth = st.selectbox("depth_select", ["light", "medium", "deep"], index=1,
                             format_func=lambda x: {"light": "Light (5 steps, ~2 min)", "medium": "Medium (13 steps, ~8 min)", "deep": "Deep (16 steps, ~12 min)"}[x],
                             label_visibility="collapsed")
        st.divider()

        can_run = not st.session_state._running
        if st.button("▶  Run Analysis", type="primary", disabled=not can_run, use_container_width=True):
            st.session_state._running = True
            st.session_state._done = False
            st.session_state._from_cache = False
            st.session_state._cached_result = None
            t = threading.Thread(target=_run_pipeline, args=(symbol, trade_date, market, depth, data_window), daemon=True)
            t.start()
            st.session_state._thread = t
            st.rerun()

        # Token display
        p_now = get_progress()
        if st.session_state._running or st.session_state._done:
            st.divider()
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
    info, kline_df = _fetch_stock_data(symbol, market)

    # Stock header
    cols = st.columns(7)
    items = [
        ("Symbol", symbol),
        ("Name", str(info.get("name", "—"))),
        ("Price", f"¥{info['close']:.2f}" if info.get("close") and info["close"] == info["close"] else "—"),
        ("Change", info.get("change_pct")),
        ("PE", info.get("pe")),
        ("PB", info.get("pb")),
        ("Turnover", f"{info.get('turn', 0):.2f}%" if info.get("turn") and info["turn"] == info["turn"] else "—"),
    ]
    for i, (label, value) in enumerate(items):
        with cols[i]:
            if label == "Change" and isinstance(value, (int, float)) and value == value:
                cls = "up" if value >= 0 else "down"
                sgn = "+" if value >= 0 else ""
                st.markdown(f'<div class="mc"><div class="mcl">{label}</div><div class="mcv {cls}">{sgn}{value:.2f}%</div></div>', unsafe_allow_html=True)
            elif label == "PE" and isinstance(value, (int, float)) and value == value:
                st.markdown(f'<div class="mc"><div class="mcl">{label}</div><div class="mcv">{value:.1f}</div></div>', unsafe_allow_html=True)
            elif label == "PB" and isinstance(value, (int, float)) and value == value:
                st.markdown(f'<div class="mc"><div class="mcl">{label}</div><div class="mcv">{value:.2f}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="mc"><div class="mcl">{label}</div><div class="mcv">{value}</div></div>', unsafe_allow_html=True)

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
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
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

        tabs = st.tabs(["Dashboard", "Market/Tech", "Sentiment", "News", "Fundamentals",
                         "Policy", "Hot Money", "Lockup", "Invest Plan", "Trader Plan"])

        report_keys = [
            ("Market/Tech", "market_report"), ("Sentiment", "sentiment_report"),
            ("News", "news_report"), ("Fundamentals", "fundamentals_report"),
            ("Policy", "policy_report"), ("Hot Money", "hot_money_report"),
            ("Lockup", "lockup_report"), ("Invest Plan", "investment_plan"),
            ("Trader Plan", "trader_investment_plan"),
        ]

        # ── Tab 0: Dashboard ──
        with tabs[0]:
            dc1, dc2, dc3, dc4 = st.columns(4)
            with dc1:
                st.markdown(f'<div class="mc"><div class="mcl">Final Rating</div><div class="mcv">{rating}</div></div>', unsafe_allow_html=True)
            with dc2:
                qg = state.get("data_quality_summary", "")
                n_ok = qg.count(": A") + qg.count(": B") if qg else 0
                st.markdown(f'<div class="mc"><div class="mcl">Data Quality</div><div class="mcv">{n_ok}/7</div><div class="mcs">A/B grade reports</div></div>', unsafe_allow_html=True)
            with dc3:
                st.markdown(f'<div class="mc"><div class="mcl">Tokens Used</div><div class="mcv">{p.tokens_total:,}</div><div class="mcs">in {p.tokens_in:,} · out {p.tokens_out:,}</div></div>', unsafe_allow_html=True)
            with dc4:
                debate = state.get("investment_debate_state", {}) if isinstance(state, dict) else {}
                rounds = debate.get("count", 0) if isinstance(debate, dict) else 0
                st.markdown(f'<div class="mc"><div class="mcl">Debate Rounds</div><div class="mcv">{rounds}</div><div class="mcs">Bull vs Bear</div></div>', unsafe_allow_html=True)

            st.markdown('<div style="margin-top:12px"></div>', unsafe_allow_html=True)
            with st.container():
                st.markdown('<div class="dash-panel"><h4>Final Decision</h4></div>', unsafe_allow_html=True)
                # Parse decision into clean table — handle both markdown and JSON fallback
                import json as _json
                fields = {}
                # Try JSON fallback format first
                if decision.strip().startswith("{"):
                    try:
                        data = _json.loads(decision.strip().replace("'", '"'))
                        key_map = {
                            "rating": "Rating", "confidence": "Confidence",
                            "reasoning": "Reasoning", "risk_assessment": "Risk Assessment",
                            "position_advice": "Position Advice", "time_horizon": "Time Horizon",
                        }
                        for k, v in data.items():
                            if isinstance(v, str) and len(v) > 3:
                                fields[key_map.get(k, k.title())] = v
                            elif not isinstance(v, (dict, list)):
                                fields[key_map.get(k, k.title())] = str(v)
                    except Exception:
                        pass
                # Try markdown format: **Key**: value
                if not fields:
                    for line in decision.split("\n"):
                        line = line.strip()
                        if line.startswith("**") and ":**" in line:
                            # **Key**: value on same line
                            parts = line.split(":**", 1)
                            key = parts[0].replace("**", "").strip()
                            value = parts[1].strip()
                            if value:
                                fields[key] = value
                        elif line.startswith("**") and line.endswith("**"):
                            # **Key** on its own line — value on next non-empty line
                            pass  # handled below
                # Fallback: just show first 3 meaningful paragraphs
                if not fields:
                    parts = [p.strip() for p in decision.split("\n\n") if len(p.strip()) > 20]
                    for i, p in enumerate(parts[:5]):
                        key = p.split("\n")[0].replace("**", "").strip()[:60]
                        value = "\n".join(p.split("\n")[1:]).strip()[:300] if "\n" in p else p
                        if len(value) > 10:
                            fields[key] = value
                if fields:
                    rows = "".join(
                        f'<tr><td style="padding:8px 16px;color:#6b7280;font-weight:600;white-space:nowrap;border-bottom:1px solid #f1f5f9;vertical-align:top">{k}</td>'
                        f'<td style="padding:8px 16px;color:#111827;border-bottom:1px solid #f1f5f9">{v}</td></tr>'
                        for k, v in fields.items()
                    )
                    st.markdown(f'<table style="width:100%;border-collapse:collapse;font-size:0.88rem">{rows}</table>', unsafe_allow_html=True)
                else:
                    st.markdown(decision)

            st.markdown("#### Analyst Summaries")
            sc = st.columns(3)
            for i, (label, key) in enumerate(report_keys):
                content = state.get(key, "") if isinstance(state, dict) else ""
                summary = ""
                if content:
                    for line in content.split("\n"):
                        clean = line.strip().lstrip("#").strip()
                        if len(clean) > 30 and not clean.startswith("*"):
                            summary = clean[:140] + "…" if len(clean) > 140 else clean
                            break
                with sc[i % 3]:
                    st.markdown(f'<div class="dash-panel"><h4>{label}</h4><p>{summary or "(see full report tab)"}</p></div>', unsafe_allow_html=True)

        # ── Tabs 1-9: Reports ──
        for tab, (label, key) in zip(tabs[1:], report_keys):
            with tab:
                content = state.get(key, "") if isinstance(state, dict) else ""
                if content:
                    st.markdown(content)
                else:
                    st.info(f"No {label} report generated.")

    # ═══ STATE: IDLE ═══
    if not st.session_state._running and not st.session_state._done:
        st.info("Enter a stock symbol and click **Run Analysis** to start.")


if __name__ == "__main__":
    run()
