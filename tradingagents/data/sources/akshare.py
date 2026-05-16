"""akshare data source — A-stock special data + US stock fallback.

Provides:
- Dragon Tiger Board (龙虎榜), Lockup Expiry, Insider Transactions (A-stock only)
- US stock K-line via eastmoney (works in China, no VPN needed)
"""

from __future__ import annotations

import pandas as pd

from tradingagents.data.sources.base import DataSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)


class AkshareSource(DataSource):
    """akshare adapter — special A-stock data only."""

    name = "akshare"

    # ---- K-line (not used as primary for K-line, fallback only) ----

    def kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        try:
            import akshare as ak
            adj = {"qfq": "qfq", "hfq": "hfq", "none": ""}.get(adjust, "qfq")
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=adj,
            )
            if df is None or df.empty:
                return pd.DataFrame()
            col_map = {
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
                "成交额": "amount", "涨跌幅": "change_pct", "换手率": "turn",
            }
            df = df.rename(columns=col_map)
            df["symbol"] = symbol
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            for col in ("open", "high", "low", "close", "volume", "amount", "change_pct", "turn"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Dragon Tiger Board (龙虎榜) ----

    def dragon_tiger_board(self, symbol: str, days: int = 30) -> pd.DataFrame:
        try:
            import akshare as ak
            today = pd.Timestamp.now()
            start = (today - pd.Timedelta(days=days)).strftime("%Y%m%d")
            end = today.strftime("%Y%m%d")
            df = ak.stock_lhb_detail_em(start_date=start, end_date=end)
            if df is None or df.empty:
                return pd.DataFrame()
            if "代码" in df.columns:
                df = df[df["代码"] == symbol]
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Lockup Expiry (限售解禁) ----

    def lockup_expiry(self, symbol: str, months: int = 6) -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_restricted_release_queue_em(symbol=symbol)
            if df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Insider Transactions ----

    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_share_hold_change_em(symbol=symbol)
            if df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Hot Stocks ----

    def hot_stocks(self, limit: int = 20) -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_hot_rank_em()
            if df is None or df.empty:
                return pd.DataFrame()
            return df.head(limit)
        except Exception:
            return pd.DataFrame()

    # ---- Fund Flow ----

    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_individual_fund_flow(stock=symbol, market="sh")
            if df is None or df.empty:
                df = ak.stock_individual_fund_flow(stock=symbol, market="sz")
            if df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df.head(days)
        except Exception:
            return pd.DataFrame()

    # ---- Northbound Flow ----

    def northbound_flow(self, days: int = 30) -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_hsgt_north_net_flow_in_em()
            if df is None or df.empty:
                return pd.DataFrame()
            return df.head(days)
        except Exception:
            return pd.DataFrame()

    # ---- Industry Comparison ----

    def industry_comparison(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    # ---- Profit Forecast ----

    def profit_forecast(self, symbol: str) -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_profit_forecast_em(symbol=symbol)
            if df is None or df.empty:
                return pd.DataFrame()
            df["symbol"] = symbol
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Remaining methods return empty (not supported) ----

    # ---- HK Stock K-line ----
    def hk_kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """Fetch HK stock K-line via akshare eastmoney."""
        try:
            import akshare as ak
            adj = {"qfq": "qfq", "hfq": "hfq", "none": ""}.get(adjust, "qfq")
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            df = ak.stock_hk_hist(symbol=symbol.strip(), period="daily", start_date=sd, end_date=ed, adjust=adj)
            if df is None or df.empty:
                return pd.DataFrame()
            col_map = {
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
                "成交额": "amount", "涨跌幅": "change_pct", "换手率": "turn",
            }
            df = df.rename(columns=col_map)
            df["symbol"] = symbol
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            for col in ("open","high","low","close","volume","amount","change_pct","turn"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()

    # ---- US Stock K-line ----
    def us_kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """Fetch US stock K-line via akshare eastmoney (works in China)."""
        try:
            import akshare as ak
            adj = {"qfq": "qfq", "hfq": "hfq", "none": ""}.get(adjust, "qfq")
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            # Try NASDAQ (105) first, then NYSE (106)
            for ex in ("105", "106"):
                try:
                    df = ak.stock_us_hist(
                        symbol=f"{ex}.{symbol.strip().upper()}",
                        period="daily", start_date=sd, end_date=ed, adjust=adj,
                    )
                    if df is not None and not df.empty:
                        col_map = {
                            "日期": "date", "开盘": "open", "收盘": "close",
                            "最高": "high", "最低": "low", "成交量": "volume",
                            "成交额": "amount", "涨跌幅": "change_pct", "换手率": "turn",
                        }
                        df = df.rename(columns=col_map)
                        df["symbol"] = symbol
                        if "date" in df.columns:
                            df["date"] = pd.to_datetime(df["date"]).dt.date
                        for col in ("open","high","low","close","volume","amount","change_pct","turn"):
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors="coerce")
                        return df
                except Exception:
                    continue
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def kline_weekly(self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        return pd.DataFrame()

    def kline_monthly(self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        return pd.DataFrame()

    def quote(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def balance_sheet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def income_statement(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def cash_flow(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()

    def eastmoney_news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        """A-stock announcements via eastmoney public API (JSON, no auth)."""
        try:
            import requests
            url = (
                f"https://np-anotice-stock.eastmoney.com/api/security/ann"
                f"?page_size={min(limit, 20)}&page_index=1&stock_list={symbol}"
            )
            r = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.eastmoney.com",
            }, timeout=5)
            if r.status_code != 200:
                return pd.DataFrame()
            data = r.json()
            items = data.get("data", {}).get("list", [])
            if not items:
                return pd.DataFrame()

            rows = []
            for item in items:
                # Build title from available fields
                cols = item.get("columns", {}) if isinstance(item.get("columns"), dict) else {}
                title = (
                    cols.get("SECURITY_NAME_ABBR", "")
                    or item.get("notice_name", "")
                    or item.get("title", "")
                    or f"{item.get('art_code', '')} {item.get('notice_date', '')}"
                )
                if title:
                    rows.append({
                        "title": str(title).strip(),
                        "source": "eastmoney",
                        "url": "",
                        "publish_time": str(item.get("notice_date", "")),
                        "summary": str(item.get("art_code", "")),
                    })
            return pd.DataFrame(rows)
        except Exception:
            return pd.DataFrame()

    def sina_news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        """A-stock news via Sina Finance HTML page (public, no auth).
        Parses the stock news listing page for headlines.
        """
        try:
            import re
            import requests
            prefix = "sh" if symbol.startswith("6") else "sz"
            url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{prefix}{symbol}.phtml"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            r.encoding = "gbk"  # Sina uses GBK encoding
            if r.status_code != 200:
                return pd.DataFrame()
            # Parse datelist div: date + link pattern with <br> separators
            rows = []
            datelist_m = re.search(r'<div class="datelist">(.*?)</div>', r.text, re.DOTALL)
            html = datelist_m.group(1) if datelist_m else r.text
            # Pattern: 2026-05-16 20:09  <a target='_blank' href='URL'>TITLE</a>
            pattern = re.compile(r"(\d{4}-\d{2}-\d{2}).*?<a[^>]*>([^<]{5,100})</a>")
            matches = pattern.findall(html)
            for date_str, title in matches[:limit]:
                title = title.strip()
                if title and len(title) > 5 and "首页" not in title and "财经" not in title:
                    rows.append({"title": title, "source": "sina", "url": "",
                                 "publish_time": date_str, "summary": ""})
            logger.info("[akshare] sina news returned %d articles for %s", len(rows), symbol)
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    # Backward-compat alias
    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        """Try eastmoney first, then sina."""
        df = self.eastmoney_news(symbol, limit)
        if not df.empty:
            return df
        return self.sina_news(symbol, limit)

    def concept_blocks(self) -> pd.DataFrame:
        return pd.DataFrame()
