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
    """Fetch recent news for the stock."""
    symbol = state["company_of_interest"]
    market = state.get("market", "a_stock")
    mod = _get_mod(market)

    parts = ["## 真实新闻数据 (你必须基于以下新闻进行分析)\n"]
    try:
        news = mod.get_news(symbol, limit=15)
        if not news.empty:
            for _, row in news.head(15).iterrows():
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
    parts = ["## 真实资金流向数据 (你必须使用以下数据)\n"]

    if market != "a_stock":
        parts.append("(A股市场专属数据，当前标的不适用)")
        return "\n".join(parts)

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
    parts = ["## 真实解禁/增减持数据 (你必须使用以下数据)\n"]

    if market != "a_stock":
        parts.append("(A股市场专属数据，当前标的不适用)")
        return "\n".join(parts)

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
