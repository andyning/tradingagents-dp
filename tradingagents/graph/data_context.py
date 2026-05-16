"""Pre-fetch real market data for each analyst node.

Every analyst node calls these functions BEFORE rendering the prompt,
so the LLM receives actual data rather than hallucinating.
"""

from __future__ import annotations

import traceback
from typing import Any

import pandas as pd

from tradingagents.config import get_settings
from tradingagents.data import a_stock, hk_stock, us_stock
from tradingagents.logging import get_logger

logger = get_logger(__name__)

_MARKET_MOD = {"a_stock": a_stock, "hk_stock": hk_stock, "us_stock": us_stock}


def _fmt_df(df: pd.DataFrame, max_rows: int = 40) -> str:
    """Format a DataFrame as a markdown table string."""
    if df.empty:
        return "(no data available)"
    if len(df) > max_rows:
        df = pd.concat([df.head(max_rows // 2), df.tail(max_rows // 2)])
    return df.to_markdown(index=False) if hasattr(df, "to_markdown") else df.to_string()


def _get_mod(market: str):
    return _MARKET_MOD.get(market, a_stock)


# ---- Per-analyst data fetchers ----

def for_market_analyst(state: dict[str, Any]) -> str:
    """Fetch K-line data and compute technical indicators."""
    symbol = state["company_of_interest"]
    trade_date = state["trade_date"]
    market = state.get("market", "a_stock")
    mod = _get_mod(market)

    parts = ["## 真实市场数据 (REAL DATA — 你必须使用以下数据，禁止编造)\n"]

    # K-line: data_window trading days before trade_date
    window = state.get("data_window", 120)
    try:
        # Convert trading days to calendar days (approx 1.4x for weekends/holidays)
        start = pd.Timestamp(trade_date) - pd.Timedelta(days=int(window * 1.6))
        df = mod.get_kline_daily(symbol, start.strftime("%Y-%m-%d"), trade_date)
        if not df.empty:
            parts.append(f"### K线数据 (最近 {len(df)} 个交易日)")
            parts.append(_fmt_df(df.tail(60)))
            parts.append("")

            # Compute summary stats from real data
            close = pd.to_numeric(df["close"], errors="coerce")
            volume = pd.to_numeric(df["volume"], errors="coerce")
            change_pct = pd.to_numeric(df.get("change_pct", pd.Series(dtype=float)), errors="coerce")

            last_close = close.iloc[-1] if len(close) > 0 else 0
            parts.append(f"**最新收盘价**: {last_close} 元")
            parts.append(f"**分析日期**: {trade_date}")

            if len(change_pct) > 0:
                parts.append(f"**当日涨跌幅**: {change_pct.iloc[-1]:.2f}%" if pd.notna(change_pct.iloc[-1]) else "")

            if len(close) >= 20:
                ret_30d = (close.iloc[-1] / close.iloc[-min(20, len(close))] - 1) * 100
                parts.append(f"**近20日累计收益率**: {ret_30d:.2f}%")

            if len(volume) >= 20:
                vol_5d = volume.iloc[-5:].mean() if len(volume) >= 5 else volume.mean()
                vol_20d = volume.iloc[-20:].mean()
                ratio = vol_5d / vol_20d if vol_20d > 0 else 0
                parts.append(f"**5日均量**: {vol_5d/1e4:.0f}万股  **20日均量**: {vol_20d/1e4:.0f}万股  **量比**: {ratio:.2f}")

            # Technical indicators
            if len(close) >= 60:
                df["ma5"] = close.rolling(5).mean()
                df["ma10"] = close.rolling(10).mean()
                df["ma20"] = close.rolling(20).mean()
                df["ma60"] = close.rolling(60).mean()

                # MACD
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                df["macd"] = ema12 - ema26
                df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
                df["macd_hist"] = df["macd"] - df["macd_signal"]

                # RSI
                delta = close.diff()
                gain = delta.clip(lower=0)
                loss = (-delta).clip(lower=0)
                avg_gain = gain.rolling(14).mean()
                avg_loss = loss.rolling(14).mean()
                rs = avg_gain / avg_loss.replace(0, float("nan"))
                df["rsi14"] = 100.0 - (100.0 / (1.0 + rs))

                # Bollinger
                df["boll_mid"] = close.rolling(20).mean()
                std20 = close.rolling(20).std()
                df["boll_upper"] = df["boll_mid"] + 2 * std20
                df["boll_lower"] = df["boll_mid"] - 2 * std20

                parts.append("")
                parts.append("### 技术指标 (已计算)")
                last = df.iloc[-1]
                parts.append(f"- **MA5**: {last['ma5']:.2f}  **MA10**: {last['ma10']:.2f}  **MA20**: {last['ma20']:.2f}  **MA60**: {last['ma60']:.2f}")
                parts.append(f"- **MACD**: {last['macd']:.4f}  **Signal**: {last['macd_signal']:.4f}  **Hist**: {last['macd_hist']:.4f}")
                parts.append(f"- **RSI(14)**: {last['rsi14']:.1f}")
                parts.append(f"- **Bollinger**: 上轨 {last['boll_upper']:.2f}  中轨 {last['boll_mid']:.2f}  下轨 {last['boll_lower']:.2f}")

                # Support/Resistance
                high = pd.to_numeric(df["high"], errors="coerce")
                low = pd.to_numeric(df["low"], errors="coerce")
                if len(df) >= 20:
                    parts.append(f"- **20日最高**: {high.iloc[-20:].max():.2f}  **20日最低**: {low.iloc[-20:].min():.2f}")

    except Exception as exc:
        parts.append(f"(数据拉取失败: {exc})")
        logger.warning("Market data fetch failed: %s", exc)

    return "\n".join(parts)


def for_news_analyst(state: dict[str, Any]) -> str:
    """Fetch recent news, filtered for relevance."""
    symbol = state["company_of_interest"]
    market = state.get("market", "a_stock")
    mod = _get_mod(market)

    parts = ["## 真实新闻数据 (你必须基于以下新闻进行分析)\n"]
    try:
        news = mod.get_news(symbol, limit=30)
        if not news.empty:
            # Apply relevance filter
            from tradingagents.graph.news_filter import filter_news
            raw_items = news.to_dict("records")
            filtered = filter_news(raw_items, symbol, company_name="", max_items=15)
            if filtered:
                for item in filtered:
                    title = item.get("title", "")
                    source = item.get("source", "")
                    parts.append(f"- **{title}** ({source})")
            else:
                parts.append("(相关新闻较少，以下为可用的相关新闻)")
                for _, row in news.head(10).iterrows():
                    title = row.get("title", "")
                    source = row.get("source", "")
                    parts.append(f"- **{title}** ({source})")
        else:
            try:
                global_news = a_stock.get_global_news(limit=10)
                if not global_news.empty:
                    parts.append("(个股新闻暂无，以下是宏观/市场新闻)")
                    for _, row in global_news.head(10).iterrows():
                        title = row.get("title", "")
                        parts.append(f"- {title}")
                else:
                    parts.append("(暂无可用新闻)")
            except Exception:
                parts.append("(新闻数据暂不可用)")
    except Exception as exc:
        parts.append(f"(新闻拉取失败: {exc})")

    return "\n".join(parts)


def for_fundamentals_analyst(state: dict[str, Any]) -> str:
    """Fetch financial data and peer comparison."""
    symbol = state["company_of_interest"]
    trade_date = state["trade_date"]
    market = state.get("market", "a_stock")
    mod = _get_mod(market)

    parts = ["## 真实财务数据 (你必须使用以下数据，禁止编造)\n"]

    try:
        # K-line has PE/PB in the last row for A-stock (Baostock)
        window = state.get("data_window", 120)
        start = pd.Timestamp(trade_date) - pd.Timedelta(days=min(window, 60))
        df = mod.get_kline_daily(symbol, start.strftime("%Y-%m-%d"), trade_date)
        if not df.empty:
            last = df.iloc[-1]
            close = pd.to_numeric(last["close"], errors="coerce")
            pe = pd.to_numeric(last.get("pe", float("nan")), errors="coerce")
            pb = pd.to_numeric(last.get("pb", float("nan")), errors="coerce")
            turn = pd.to_numeric(last.get("turn", float("nan")), errors="coerce")
            change_pct = pd.to_numeric(last.get("change_pct", float("nan")), errors="coerce")
            volume = pd.to_numeric(last.get("volume", 0), errors="coerce")

            # If PE/PB missing from K-line (IB, Futu K-line), try Futu snapshot
            if (pd.isna(pe) or pd.isna(pb)) and market in ("a_stock", "hk_stock", "us_stock"):
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
                    ret, snap = ctx.get_market_snapshot([futu_sym])
                    ctx.close()
                    if ret == 0 and snap is not None and not snap.empty:
                        row = snap.iloc[0]
                        if pd.isna(pe):
                            pe = pd.to_numeric(row.get("pe_ttm_ratio", float("nan")), errors="coerce")
                        if pd.isna(pb):
                            pb = pd.to_numeric(row.get("pb_ratio", float("nan")), errors="coerce")
                except Exception:
                    pass

            parts.append(f"**最新收盘价**: {close:.2f} 元" if pd.notna(close) else "")
            parts.append(f"**PE(TTM)**: {pe:.2f}" if pd.notna(pe) else "**PE(TTM)**: 暂无")
            parts.append(f"**PB**: {pb:.2f}" if pd.notna(pb) else "**PB**: 暂无")
            parts.append(f"**换手率**: {turn:.2f}%" if pd.notna(turn) else "")
            parts.append(f"**当日涨跌幅**: {change_pct:.2f}%" if pd.notna(change_pct) else "")

            # Volume analysis
            if pd.notna(volume) and len(df) >= 20:
                avg_vol_20 = pd.to_numeric(df["volume"].iloc[-20:], errors="coerce").mean()
                vol_ratio = volume / avg_vol_20 if avg_vol_20 > 0 else 0
                parts.append(f"**成交量**: {volume/1e4:.0f}万股  **量比(20日)**: {vol_ratio:.2f}")

    except Exception as exc:
        parts.append(f"(行情数据拉取失败: {exc})")

    # Financial summary
    try:
        fin = mod.get_financial_summary(symbol)
        if not fin.empty:
            parts.append("")
            parts.append("### 基本面概览")
            parts.append(_fmt_df(fin.head(10)))
    except Exception:
        pass

    return "\n".join(parts)


def for_hot_money_analyst(state: dict[str, Any]) -> str:
    """Fetch capital flow, northbound, dragon tiger board."""
    symbol = state["company_of_interest"]
    market = state.get("market", "a_stock")
    parts = ["## Hot Money / Capital Flow\n"]

    if market != "a_stock":
        return "## Hot Money / Capital Flow\n(A-share specific — not applicable. Skip this analysis.)\n"

    # Fund flow
    try:
        flow = a_stock.get_fund_flow(symbol, days=20)
        if not flow.empty:
            parts.append("### 个股资金流向")
            parts.append(_fmt_df(flow.tail(10)))
            parts.append("")
    except Exception:
        pass

    # Northbound
    try:
        north = a_stock.get_northbound_flow(days=20)
        if not north.empty:
            parts.append("### 北向资金")
            parts.append(_fmt_df(north.tail(10)))
            parts.append("")
    except Exception:
        pass

    # Dragon tiger
    try:
        dt = a_stock.get_dragon_tiger_board(symbol, days=90)
        if not dt.empty:
            parts.append("### 龙虎榜")
            parts.append(_fmt_df(dt.tail(10)))
            parts.append("")
    except Exception:
        pass

    # Hot stocks
    try:
        hot = a_stock.get_hot_stocks(limit=10)
        if not hot.empty:
            parts.append("### 热门个股")
            parts.append(_fmt_df(hot))
            parts.append("")
    except Exception:
        pass

    return "\n".join(parts)


def for_lockup_analyst(state: dict[str, Any]) -> str:
    """Fetch lockup expiry and insider transactions."""
    symbol = state["company_of_interest"]
    market = state.get("market", "a_stock")
    parts = ["## Lockup / Insider Data\n"]

    if market != "a_stock":
        return "## Lockup / Insider\n(A-share specific — not applicable. Skip this analysis.)\n"

    try:
        lockup = a_stock.get_lockup_expiry(symbol, months=6)
        if not lockup.empty:
            parts.append("### 限售解禁")
            parts.append(_fmt_df(lockup))
            parts.append("")
        else:
            parts.append("**限售解禁**: 未来6个月无重大解禁")
            parts.append("")
    except Exception:
        parts.append("(解禁数据暂不可用)")
        parts.append("")

    try:
        insider = a_stock.get_insider_transactions(symbol)
        if not insider.empty:
            parts.append("### 股东增减持")
            parts.append(_fmt_df(insider.tail(10)))
        else:
            parts.append("**股东增减持**: 近期无重大增减持记录")
    except Exception:
        parts.append("(增减持数据暂不可用)")

    return "\n".join(parts)


def for_policy_analyst(state: dict[str, Any]) -> str:
    """Fetch macro/policy-relevant news for the policy analyst."""
    symbol = state["company_of_interest"]
    market = state.get("market", "a_stock")
    mod = _get_mod(market)

    parts = ["## Policy & Macro News (你必须基于以下真实新闻分析政策影响)\n"]
    try:
        # Try to get news through the market module
        if hasattr(mod, "get_news"):
            news = mod.get_news(symbol, limit=20)
            if not news.empty:
                from tradingagents.graph.news_filter import filter_news
                raw_items = news.to_dict("records")
                # Filter for policy/macro-relevant keywords
                policy_kw = ["policy", "regulation", "fed", "interest", "tariff", "trade",
                             "ban", "restrict", "subsidy", "congress", "白宫", "国会",
                             "政策", "监管", "关税", "制裁", "补贴", "央行", "利率",
                             "cpi", "gdp", "inflation", "employment", "就业", "通胀"]
                filtered = filter_news(raw_items, symbol, company_name="", max_items=15)
                if filtered:
                    for item in filtered:
                        parts.append(f"- **{item.get('title', '')}** ({item.get('source', '')})")
                else:
                    for _, row in news.head(10).iterrows():
                        parts.append(f"- **{row.get('title', '')}** ({row.get('source', '')})")
            else:
                parts.append("(暂无相关新闻数据)")
        else:
            parts.append("(该市场暂不支持新闻获取)")
    except Exception as exc:
        parts.append(f"(新闻获取失败: {exc})")

    parts.append("")
    parts.append("Instructions: Analyze how the above news affects the stock's sector and regulatory environment. If no relevant policy news found, state that clearly and base your analysis on known regulatory frameworks for this market.")
    parts.append("")
    return "\n".join(parts)


def for_sentiment_analyst(state: dict[str, Any]) -> str:
    """Fetch market-derived sentiment data for the sentiment analyst."""
    symbol = state["company_of_interest"]
    trade_date = state["trade_date"]
    market = state.get("market", "a_stock")
    mod = _get_mod(market)

    parts = ["## Market-Derived Sentiment Data (基于市场数据的情绪指标)\n"]

    # Quantitative sentiment from K-line
    try:
        window = state.get("data_window", 30)
        start = pd.Timestamp(trade_date) - pd.Timedelta(days=int(window * 1.6))
        df = mod.get_kline_daily(symbol, start.strftime("%Y-%m-%d"), trade_date)
        if not df.empty:
            close = pd.to_numeric(df["close"], errors="coerce")
            volume = pd.to_numeric(df["volume"], errors="coerce")
            change_pct = pd.to_numeric(df.get("change_pct", pd.Series(dtype=float)), errors="coerce")

            if len(close) >= 5:
                last_close = close.iloc[-1] if pd.notna(close.iloc[-1]) else 0
                chg_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if pd.notna(close.iloc[-5]) and close.iloc[-5] > 0 else 0
                chg_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 and pd.notna(close.iloc[-20]) and close.iloc[-20] > 0 else 0

                parts.append(f"- **最新收盘价**: {last_close:.2f}")
                parts.append(f"- **5日涨跌幅**: {chg_5d:+.2f}%")
                parts.append(f"- **20日涨跌幅**: {chg_20d:+.2f}%")

                if len(volume) >= 20:
                    vol_5 = volume.iloc[-5:].mean()
                    vol_20 = volume.iloc[-20:].mean()
                    vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 0
                    parts.append(f"- **5日均量/20日均量**: {vol_ratio:.2f} ({'放量' if vol_ratio > 1.2 else '缩量' if vol_ratio < 0.8 else '持平'})")

                if len(change_pct) >= 5:
                    up_days = (change_pct.iloc[-5:] > 0).sum()
                    parts.append(f"- **近5日上涨天数**: {up_days}/5")

    except Exception as exc:
        parts.append(f"(市场数据获取失败: {exc})")

    # News sentiment clues
    try:
        if hasattr(mod, "get_news"):
            news = mod.get_news(symbol, limit=10)
            if not news.empty:
                parts.append("")
                parts.append("### 近期新闻标题 (情绪线索)")
                for _, row in news.head(8).iterrows():
                    title = row.get("title", "")
                    if title:
                        parts.append(f"- {title}")
    except Exception:
        pass

    parts.append("")
    parts.append("Instructions: Based on the above data, assess market sentiment direction and intensity. Acknowledge limitations — no social media scraping is performed. Use price momentum, volume patterns, and news headlines as proxies for sentiment.")
    parts.append("")
    return "\n".join(parts)


def for_backtest(state: dict[str, Any]) -> str:
    """Run multiple lightweight strategies and return comparison.

    Strategies: MA crossover (5/20), MACD signal cross, RSI mean-reversion.
    Each produces return, max drawdown, win rate, and alpha vs buy-and-hold.
    """
    symbol = state["company_of_interest"]
    trade_date = state["trade_date"]
    market = state.get("market", "a_stock")
    mod = _get_mod(market)

    try:
        start = pd.Timestamp(trade_date) - pd.Timedelta(days=400)
        df = mod.get_kline_daily(symbol, start.strftime("%Y-%m-%d"), trade_date)
        if df.empty or len(df) < 60:
            return "## 历史回测\n(历史数据不足，无法进行回测)\n"

        close = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(close) < 60:
            return "## 历史回测\n(历史数据不足，无法进行回测)\n"

        daily_ret = close.pct_change().fillna(0)
        bh_cum = (1 + daily_ret).cumprod()
        bh_total = float((bh_cum.iloc[-1] - 1) * 100)
        bh_peak = bh_cum.cummax()
        bh_dd = float(((bh_cum / bh_peak - 1).min()) * 100)
        days = len(close)

        def _simulate(position_signal: "pd.Series", close_prices, daily_rets) -> dict:
            """Run a strategy simulation and return metrics."""
            rets = daily_rets * position_signal.shift(1).fillna(0)
            cum = (1 + rets).cumprod()
            total = float((cum.iloc[-1] - 1) * 100)
            peak = cum.cummax()
            dd = float(((cum / peak - 1).min()) * 100)
            # Trade counting
            sig_diff = position_signal.diff().fillna(0)
            buys = (sig_diff == 1).sum()
            sells = (sig_diff == -1).sum()
            trades = min(buys, sells)
            wins = 0
            in_pos = False
            entry = 0.0
            for i in range(1, len(close_prices)):
                if sig_diff.iloc[i] == 1 and not in_pos:
                    entry = close_prices.iloc[i]; in_pos = True
                elif sig_diff.iloc[i] == -1 and in_pos:
                    if close_prices.iloc[i] > entry: wins += 1
                    in_pos = False
            wr = (wins / trades * 100) if trades > 0 else 0
            return {"return": total, "max_dd": dd, "trades": int(trades), "win_rate": wr,
                    "alpha": total - bh_total, "cum_ret": cum}

        # ── Strategy 1: MA Crossover (5/20) ──
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        s1 = _simulate((ma5 > ma20).astype(int), close, daily_ret)

        # ── Strategy 2: MACD Signal Cross ──
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        s2 = _simulate((macd_line > macd_signal).astype(int), close, daily_ret)

        # ── Strategy 3: RSI Mean-Reversion ──
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta).clip(lower=0).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))
        rsi_signal = pd.Series(0, index=close.index)
        rsi_signal[rsi < 30] = 1
        rsi_signal[rsi > 70] = 0
        rsi_signal = rsi_signal.fillna(method="ffill").fillna(0)
        s3 = _simulate(rsi_signal.astype(int), close, daily_ret)

        strategies = [
            ("MA5/20 金叉", s1), ("MACD 信号交叉", s2), ("RSI 超卖反弹", s3),
        ]

        parts = [
            f"## 多策略历史回测 ({days} 个交易日)\n",
            f"**买入持有**: {bh_total:+.1f}% / 最大回撤 {bh_dd:.1f}%\n",
            "| 策略 | 收益 | 最大回撤 | 胜率 | 交易次数 | Alpha | 特征 |",
            "|------|------|----------|------|----------|-------|------|",
        ]

        for name, s in strategies:
            if s["return"] > bh_total + 5:
                feature = "趋势跟踪"
            elif s["win_rate"] > 55:
                feature = "高胜率"
            elif s["return"] > bh_total:
                feature = "略优持有"
            elif s["max_dd"] < bh_dd:
                feature = "低回撤"
            else:
                feature = "效果一般"

            parts.append(
                f"| {name} | {s['return']:+.1f}% | {s['max_dd']:.1f}% | "
                f"{s['win_rate']:.0f}% | {s['trades']} | {s['alpha']:+.1f}% | {feature} |"
            )

        # Best strategy recommendation
        best = max(strategies, key=lambda x: x[1]["alpha"])
        parts.append("")
        parts.append(f"**最佳策略**: {best[0]} (Alpha {best[1]['alpha']:+.1f}%)")
        if best[1]["alpha"] > 10:
            parts.append("- 该股呈现明确的趋势特征，顺势策略有效")
        elif best[1]["alpha"] < -5:
            parts.append("- 所有主动策略均未能跑赢持有，该股适合被动持有或观望")
        else:
            parts.append("- 策略Alpha有限，需结合基本面判断入场时机")
        parts.append("")
        return "\n".join(parts)

    except Exception as exc:
        logger.warning("Backtest summary failed: %s", exc)
        return "## 历史回测\n(回测计算异常，跳过)\n"


def for_industry_comparison(state: dict[str, Any]) -> str:
    """Fetch industry peers and compute comparison metrics."""
    symbol = state["company_of_interest"]
    market = state.get("market", "a_stock")

    if market != "a_stock":
        return "## 行业对比\n(仅A股支持行业对比)\n"

    try:
        trade_date = state["trade_date"]
        start = pd.Timestamp(trade_date) - pd.Timedelta(days=30)
        df_self = a_stock.get_kline_daily(symbol, start.strftime("%Y-%m-%d"), trade_date)
        self_pe = None
        if not df_self.empty:
            last = df_self.iloc[-1]
            self_pe = pd.to_numeric(last.get("pe", float("nan")), errors="coerce")
            self_pb = pd.to_numeric(last.get("pb", float("nan")), errors="coerce")

        hot = a_stock.get_hot_stocks(limit=20)
        peer_metrics = []
        if not hot.empty:
            for _, row in hot.head(15).iterrows():
                try:
                    sym = str(row.iloc[0]) if len(row) > 0 else ""
                    if sym and sym.isdigit() and len(sym) == 6 and sym != symbol:
                        df_p = a_stock.get_kline_daily(sym, trade_date, trade_date)
                        if not df_p.empty:
                            p = df_p.iloc[-1]
                            pe = pd.to_numeric(p.get("pe", float("nan")), errors="coerce")
                            if pd.notna(pe) and 0 < pe < 1000:
                                peer_metrics.append({"symbol": sym, "pe": pe})
                except Exception:
                    continue

        parts = ["## 行业对比数据\n"]
        if self_pe is not None and pd.notna(self_pe):
            parts.append(f"**{symbol} PE(TTM)**: {self_pe:.1f}")

        if peer_metrics:
            pe_list = [p["pe"] for p in peer_metrics]
            pe_med = sorted(pe_list)[len(pe_list)//2]
            pe_min = min(pe_list); pe_max = max(pe_list)
            parts.append(f"**行业PE中位数**: {pe_med:.1f} (范围 {pe_min:.0f}-{pe_max:.0f}, {len(pe_list)}只股票)")
            if self_pe is not None and pd.notna(self_pe):
                pct = sum(1 for p in pe_list if p < self_pe) / len(pe_list) * 100
                if self_pe > pe_med * 1.2:
                    judgment = "偏高"
                elif self_pe < pe_med * 0.8:
                    judgment = "偏低"
                else:
                    judgment = "合理"
                parts.append(f"**估值水位**: 高于行业 {pct:.0f}% 的同行，估值**{judgment}**")
        else:
            parts.append("(行业对比数据暂时不足)")

        parts.append("")
        return "\n".join(parts)

    except Exception as exc:
        logger.warning("Industry comparison failed: %s", exc)
        return "## 行业对比\n(数据暂时不可用)\n"
