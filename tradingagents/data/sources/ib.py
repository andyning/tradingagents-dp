"""Interactive Brokers data source — institutional-grade market data.

Requires IB Gateway or TWS running locally with API enabled.
Paper trading port: 4002 (Gateway) / 7497 (TWS).
Live trading port: 4001 (Gateway) / 7496 (TWS).

Uses a SINGLE persistent connection per session — does NOT open/close
per request. Connection is lazily initialized on first use.
"""

from __future__ import annotations

import threading
import time
from datetime import date

import pandas as pd

from tradingagents.data.sources.base import DataSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

# Default paper trading port for IB Gateway
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 4002
_CLIENT_ID = 99  # Fixed client ID — single stable connection

# Shared persistent connection
_shared_ib = None
_shared_lock = threading.Lock()
_shared_refcount = 0


def _get_shared_ib(host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT):
    """Get or create a SINGLE persistent IB connection. Thread-safe.
    Auto-reconnects if the connection was dropped."""
    global _shared_ib, _shared_refcount
    with _shared_lock:
        # Check if existing connection is still alive
        if _shared_ib is not None:
            try:
                if _shared_ib.isConnected():
                    _shared_refcount += 1
                    return _shared_ib
            except Exception:
                pass  # Connection dead — reconnect below
            # Clean up dead connection
            try:
                _shared_ib.disconnect()
            except Exception:
                pass
            _shared_ib = None

        # Create fresh connection — ib_insync needs an event loop per thread
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from ib_insync import IB
            _shared_ib = IB()
            _shared_ib.connect(host, port, clientId=_CLIENT_ID, timeout=8)
            logger.info("IB persistent connection established (clientId=%d)", _CLIENT_ID)
            _shared_refcount += 1
            return _shared_ib
        except Exception as exc:
            logger.debug("IB connection failed: %s", exc)
            _shared_ib = None
            return None


def _release_shared_ib():
    """Release reference. Disconnect only on app shutdown."""
    global _shared_ib, _shared_refcount
    with _shared_lock:
        _shared_refcount = max(0, _shared_refcount - 1)

# Contract mapping per market
def _ib_contract(symbol: str, market: str):
    """Build an IB contract for the given symbol and market."""
    try:
        from ib_insync import Stock
    except ImportError:
        return None

    s = symbol.strip().upper()
    if market == "a_stock":
        # A-shares via Shanghai/Shenzhen Stock Connect
        if s.startswith("6"):
            return Stock(s, "SEHKNTL", "CNY")  # Shanghai-HK Northbound
        return Stock(s, "SEHKNT", "CNY")        # Shenzhen-HK Northbound
    elif market == "hk_stock":
        # IB uses unpadded codes for HK: "700" not "00700"
        code = s.lstrip("0") or "0"
        return Stock(code, "SEHK", "HKD")
    elif market == "us_stock":
        return Stock(s, "SMART", "USD")
    return None

# Bar size mapping
_BAR_SIZE = {"daily": "1 day", "weekly": "1 week", "monthly": "1 month"}


class IBSource(DataSource):
    """Interactive Brokers data adapter — uses persistent shared connection.

    Gracefully returns empty DataFrames when IB Gateway is not running,
    allowing the fallback chain to proceed to the next source.
    """

    name = "ib"

    def __init__(self, market: str = "a_stock", host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT):
        self.market = market
        self.host = host
        self.port = port

    def _get_ib(self):
        """Get the shared persistent IB connection."""
        return _get_shared_ib(self.host, self.port)

    # ---- K-line ----

    def kline_daily(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "daily")

    def kline_weekly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "weekly")

    def kline_monthly(
        self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "monthly")

    def _fetch_kline(
        self, symbol: str, start_date: str, end_date: str, freq: str
    ) -> pd.DataFrame:
        contract = _ib_contract(symbol, self.market)
        if contract is None:
            return pd.DataFrame()

        ib = self._get_ib()
        if ib is None:
            return pd.DataFrame()

        try:
            bar_size = _BAR_SIZE.get(freq, "1 day")
            # IB duration format: "N D" or "N W" or "N M" or "N Y"
            duration = "2 Y"
            # IB requires empty string for "now" or full datetime string
            # Use empty string to get data up to the most recent available
            bars = ib.reqHistoricalData(
                contract, endDateTime="", durationStr=duration,
                barSizeSetting=bar_size, whatToShow="TRADES",
                useRTH=True, formatDate=1, keepUpToDate=False,
            )
            if not bars:
                return pd.DataFrame()

            df = pd.DataFrame([{
                "date": b.date.date() if hasattr(b.date, "date") else pd.to_datetime(str(b.date)).date(),
                "open": float(b.open), "high": float(b.high),
                "low": float(b.low), "close": float(b.close),
                "volume": int(b.volume), "amount": float(b.close) * float(b.volume),
            } for b in bars])

            # Filter to requested date range
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                start_dt = pd.Timestamp(start_date)
                end_dt = pd.Timestamp(end_date)
                df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
                df["date"] = df["date"].dt.date

            df["symbol"] = symbol
            logger.info("[ib] %s returned %d rows (market=%s)", symbol, len(df), self.market)
            return df
        except Exception as exc:
            logger.debug("IB K-line failed for %s: %s", symbol, exc)
            return pd.DataFrame()
        # Connection stays open — shared across all IBSource instances

    # ---- Quote ----

    def quote(self, symbol: str) -> pd.DataFrame:
        contract = _ib_contract(symbol, self.market)
        if contract is None:
            return pd.DataFrame()

        ib = self._get_ib()
        if ib is None:
            return pd.DataFrame()

        try:
            # Use snapshot market data
            ib.reqMktData(contract, snapshot=True)
            ib.sleep(1)  # wait for snapshot to arrive

            ticker = ib.ticker(contract)
            if not ticker or ticker.close is None:
                return pd.DataFrame()

            df = pd.DataFrame([{
                "symbol": symbol,
                "close": float(ticker.close) if ticker.close else None,
                "open": float(ticker.open) if ticker.open else None,
                "high": float(ticker.high) if ticker.high else None,
                "low": float(ticker.low) if ticker.low else None,
                "volume": int(ticker.volume) if ticker.volume else 0,
                "bid": float(ticker.bid) if ticker.bid else None,
                "ask": float(ticker.ask) if ticker.ask else None,
            }])
            return df
        except Exception:
            return pd.DataFrame()
        # Connection stays open — shared across all IBSource instances

    # ---- Financial Summary ----

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        """Get fundamental data snapshot from IB."""
        contract = _ib_contract(symbol, self.market)
        if contract is None:
            return pd.DataFrame()

        ib = self._get_ib()
        if ib is None:
            return pd.DataFrame()

        try:
            # Request fundamental data
            ib.reqFundamentalData(contract, "ReportsFinSummary", snapshot=True)
            ib.sleep(1)
            # This returns XML — basic metrics extraction
            # For simplicity, use market snapshot which includes PE, PB for some markets
            ib.reqMktData(contract, snapshot=True)
            ib.sleep(1)
            ticker = ib.ticker(contract)
            if ticker:
                row = {
                    "symbol": symbol,
                    "close": float(ticker.close) if ticker.close else None,
                    "pe": float(getattr(ticker, 'peRatio', 0) or 0) or None,
                    "pb": float(getattr(ticker, 'pbRatio', 0) or 0) or None,
                    "market_cap": float(getattr(ticker, 'marketCap', 0) or 0) or None,
                    "dividend_yield": float(getattr(ticker, 'dividendYield', 0) or 0) or None,
                }
                row = {k: v for k, v in row.items() if v}
                return pd.DataFrame([row])
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()
        # Connection stays open — shared across all IBSource instances

    # ---- Unsupported by IB free tier / not needed ----

    def balance_sheet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def income_statement(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def cash_flow(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        """Fetch recent news headlines via IB (Dow Jones, Briefing.com)."""
        contract = _ib_contract(symbol, self.market)
        if contract is None:
            return pd.DataFrame()

        ib = self._get_ib()
        if ib is None:
            return pd.DataFrame()

        try:
            from datetime import datetime, timedelta
            # Qualify contract to get conId
            ib.qualifyContracts(contract)
            conId = contract.conId

            # Use available news providers: DJ-N (Dow Jones) + BRFG (Briefing.com)
            providers = "DJ-N+BRFG+BRFUPDN"

            now = datetime.now()
            start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            end = now.strftime("%Y-%m-%d %H:%M:%S")

            articles = ib.reqHistoricalNews(conId, providers, start, end, limit)
            if not articles:
                return pd.DataFrame()

            rows = []
            for a in articles:
                headline = (a.headline or "").strip()
                # Clean up IB news codes like {A:800015:L:en}
                import re
                headline = re.sub(r"\{[^}]+\}", "", headline).strip()
                if headline:
                    rows.append({
                        "title": headline,
                        "source": a.providerCode or "IB",
                        "publish_time": str(a.time) if hasattr(a, "time") else "",
                        "summary": (a.text or "")[:300] if hasattr(a, "text") else "",
                    })
            logger.info("[ib] news returned %d articles for %s", len(rows), symbol)
            return pd.DataFrame(rows)
        except Exception as exc:
            logger.debug("IB news failed for %s: %s", symbol, exc)
            return pd.DataFrame()
        # Connection stays open — shared across all IBSource instances

    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def northbound_flow(self, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def dragon_tiger_board(self, symbol: str, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def lockup_expiry(self, symbol: str, months: int = 6) -> pd.DataFrame:
        return pd.DataFrame()

    def profit_forecast(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def hot_stocks(self, limit: int = 20) -> pd.DataFrame:
        return pd.DataFrame()

    def concept_blocks(self) -> pd.DataFrame:
        return pd.DataFrame()

    def industry_comparison(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def insider_transactions(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()
