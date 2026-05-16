"""Interactive Brokers data source.

All IB API calls run on a single dedicated thread with its own event loop,
avoiding ib_insync's multi-thread incompatibility on Python 3.13.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from datetime import date
from typing import Any

import pandas as pd

from tradingagents.data.sources.base import DataSource
from tradingagents.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 4002
_CLIENT_ID = 99

# Dedicated thread resources
_ib_thread = None
_ib_instance = None
_ib_ready = threading.Event()
_ib_lock = threading.Lock()
_task_queue: queue.Queue[tuple[Any, threading.Event]] = queue.Queue()


def _ib_worker(host: str, port: int):
    """Worker thread: owns the IB connection and event loop. Processes tasks from queue."""
    global _ib_instance
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        from ib_insync import IB
        ib = IB()
        ib.connect(host, port, clientId=_CLIENT_ID, timeout=8)
        _ib_instance = ib
        _ib_ready.set()
        logger.info("IB worker thread started (clientId=%d)", _CLIENT_ID)

        while True:
            task, done_event = _task_queue.get()
            if task is None:  # Shutdown signal
                break
            try:
                result = task(ib)
                done_event.result = result
            except Exception as exc:
                done_event.result = exc
            finally:
                done_event.set()
    except Exception as exc:
        _ib_ready.set()
        _ib_instance = None
        logger.debug("IB worker failed to start: %s", exc)
    finally:
        try:
            if _ib_instance and _ib_instance.isConnected():
                _ib_instance.disconnect()
        except Exception:
            pass
        _ib_instance = None
        loop.close()


def _ensure_worker():
    """Start the IB worker thread if not already running."""
    global _ib_thread, _ib_ready
    if _ib_thread is not None and _ib_thread.is_alive():
        return
    with _ib_lock:
        if _ib_thread is not None and _ib_thread.is_alive():
            return
        _ib_ready.clear()
        _ib_thread = threading.Thread(target=_ib_worker, args=(_DEFAULT_HOST, _DEFAULT_PORT), daemon=True, name="ib-worker")
        _ib_thread.start()
        _ib_ready.wait(timeout=10)


def _run_in_ib_thread(task_fn) -> Any:
    """Execute a function on the IB worker thread and return its result."""
    _ensure_worker()
    done = threading.Event()
    done.result = None
    _task_queue.put((task_fn, done))
    done.wait(timeout=30)
    result = done.result
    if isinstance(result, Exception):
        raise result
    if result is None and _ib_instance is None:
        raise ConnectionError("IB not connected")
    return result


# Contract builder — runs on caller thread (no IB needed)
def _ib_contract(symbol: str, market: str):
    s = symbol.strip().upper()
    if market == "a_stock":
        if s.startswith("6"):
            return ("Stock", s, "SEHKNTL", "CNY")
        return ("Stock", s, "SEHKNT", "CNY")
    elif market == "hk_stock":
        code = s.lstrip("0") or "0"
        return ("Stock", code, "SEHK", "HKD")
    elif market == "us_stock":
        return ("Stock", s, "SMART", "USD")
    return None


_BAR_SIZE = {"daily": "1 day", "weekly": "1 week", "monthly": "1 month"}


class IBSource(DataSource):
    """Interactive Brokers data adapter — single-threaded, queue-based."""

    name = "ib"

    def __init__(self, market: str = "a_stock"):
        self.market = market

    # ---- K-line ----

    def kline_daily(self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "daily")

    def kline_weekly(self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "weekly")

    def kline_monthly(self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        return self._fetch_kline(symbol, start_date, end_date, "monthly")

    def _fetch_kline(self, symbol: str, start_date: str, end_date: str, freq: str) -> pd.DataFrame:
        contract_info = _ib_contract(symbol, self.market)
        if contract_info is None:
            return pd.DataFrame()

        def _task(ib) -> pd.DataFrame:
            from ib_insync import Stock
            ctype, sym, exch, curr = contract_info
            contract = Stock(sym, exch, curr)
            bars = ib.reqHistoricalData(
                contract, endDateTime="", durationStr="2 Y",
                barSizeSetting=_BAR_SIZE.get(freq, "1 day"),
                whatToShow="TRADES", useRTH=True, formatDate=1, keepUpToDate=False,
            )
            if not bars:
                return pd.DataFrame()
            df = pd.DataFrame([{
                "date": b.date.date() if hasattr(b.date, "date") else pd.to_datetime(str(b.date)).date(),
                "open": float(b.open), "high": float(b.high),
                "low": float(b.low), "close": float(b.close),
                "volume": int(b.volume), "amount": float(b.close) * float(b.volume),
            } for b in bars])
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                start_dt = pd.Timestamp(start_date); end_dt = pd.Timestamp(end_date)
                df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
                df["date"] = df["date"].dt.date
            df["symbol"] = symbol
            logger.info("[ib] %s returned %d rows (market=%s)", symbol, len(df), self.market)
            return df

        try:
            return _run_in_ib_thread(_task)
        except Exception as exc:
            logger.debug("IB K-line failed for %s: %s", symbol, exc)
            return pd.DataFrame()

    # ---- Quote / Snapshot ----

    def quote(self, symbol: str) -> pd.DataFrame:
        contract_info = _ib_contract(symbol, self.market)
        if contract_info is None:
            return pd.DataFrame()

        def _task(ib):
            from ib_insync import Stock
            ctype, sym, exch, curr = contract_info
            contract = Stock(sym, exch, curr)
            ib.reqMktData(contract, snapshot=True)
            ib.sleep(1)
            ticker = ib.ticker(contract)
            if not ticker or ticker.close is None:
                return pd.DataFrame()
            return pd.DataFrame([{"symbol": symbol, "close": float(ticker.close)}])

        try:
            return _run_in_ib_thread(_task)
        except Exception:
            return pd.DataFrame()

    def financial_summary(self, symbol: str) -> pd.DataFrame:
        contract_info = _ib_contract(symbol, self.market)
        if contract_info is None:
            return pd.DataFrame()

        def _task(ib):
            from ib_insync import Stock
            ctype, sym, exch, curr = contract_info
            contract = Stock(sym, exch, curr)
            ib.reqMktData(contract, snapshot=True)
            ib.sleep(1)
            ticker = ib.ticker(contract)
            if ticker and ticker.close:
                row = {"symbol": symbol, "close": float(ticker.close)}
                for attr in ["peRatio", "pbRatio", "marketCap", "dividendYield"]:
                    v = getattr(ticker, attr, None)
                    if v and v != v:  # NaN check
                        v = None
                    if v:
                        row[attr] = float(v)
                return pd.DataFrame([row]) if len(row) > 2 else pd.DataFrame()
            return pd.DataFrame()

        try:
            return _run_in_ib_thread(_task)
        except Exception:
            return pd.DataFrame()

    # ---- News ----

    def news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        contract_info = _ib_contract(symbol, self.market)
        if contract_info is None:
            return pd.DataFrame()

        def _task(ib):
            from ib_insync import Stock
            from datetime import datetime, timedelta
            import re
            ctype, sym, exch, curr = contract_info
            contract = Stock(sym, exch, curr)
            ib.qualifyContracts(contract)
            providers = "DJ-N+BRFG+BRFUPDN"
            now = datetime.now()
            start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            end = now.strftime("%Y-%m-%d %H:%M:%S")
            articles = ib.reqHistoricalNews(contract.conId, providers, start, end, limit)
            if not articles:
                return pd.DataFrame()
            rows = []
            for a in articles:
                headline = re.sub(r"\{[^}]+\}", "", (a.headline or "")).strip()
                if headline:
                    rows.append({"title": headline, "source": a.providerCode or "IB",
                                 "publish_time": str(a.time) if hasattr(a, "time") else "",
                                 "summary": (a.text or "")[:300] if hasattr(a, "text") else ""})
            logger.info("[ib] news returned %d articles for %s", len(rows), symbol)
            return pd.DataFrame(rows)

        try:
            return _run_in_ib_thread(_task)
        except Exception as exc:
            logger.debug("IB news failed for %s: %s", symbol, exc)
            return pd.DataFrame()

    # ---- Unsupported endpoints ----

    def balance_sheet(self, symbol: str) -> pd.DataFrame: return pd.DataFrame()
    def income_statement(self, symbol: str) -> pd.DataFrame: return pd.DataFrame()
    def cash_flow(self, symbol: str) -> pd.DataFrame: return pd.DataFrame()
    def technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame: return pd.DataFrame()
    def fund_flow(self, symbol: str, days: int = 30) -> pd.DataFrame: return pd.DataFrame()
    def northbound_flow(self, days: int = 30) -> pd.DataFrame: return pd.DataFrame()
    def dragon_tiger_board(self, symbol: str, days: int = 30) -> pd.DataFrame: return pd.DataFrame()
    def lockup_expiry(self, symbol: str, months: int = 6) -> pd.DataFrame: return pd.DataFrame()
    def profit_forecast(self, symbol: str) -> pd.DataFrame: return pd.DataFrame()
    def hot_stocks(self, limit: int = 20) -> pd.DataFrame: return pd.DataFrame()
    def concept_blocks(self) -> pd.DataFrame: return pd.DataFrame()
    def industry_comparison(self, symbol: str) -> pd.DataFrame: return pd.DataFrame()
    def insider_transactions(self, symbol: str) -> pd.DataFrame: return pd.DataFrame()
