"""HTTP-based data source modules.

Each module uses only `requests` + standard library — no third-party
SDK dependencies.  All return DataFrames compatible with the existing
Pydantic schemas in `tradingagents.data.schema`.

Proxy support: set `PROXY_URL` in .env (e.g. socks5h://127.0.0.1:10808).
All HTTP sources route through the proxy when configured.
"""

from __future__ import annotations

from typing import Optional

import requests

from tradingagents.logging import get_logger

logger = get_logger(__name__)

# ── shared proxy-aware session ─────────────────────────────────────────
_shared_session: Optional[requests.Session] = None


def get_http_session() -> requests.Session:
    """Return a shared requests.Session with proxy and browser-grade headers."""
    global _shared_session
    if _shared_session is None:
        _shared_session = requests.Session()
        _shared_session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

        # Proxy resolution order:
        #   1. PROXY_URL in .env / Settings
        #   2. Windows system proxy (if ProxyEnable=1)
        #   3. Windows ProxyServer (even if ProxyEnable=0, the proxy app may be running)
        #   4. HTTP_PROXY / HTTPS_PROXY env vars
        proxy = ""
        try:
            from tradingagents.config import get_settings
            proxy = get_settings().proxy_url or ""
        except Exception:
            pass

        if not proxy:
            import os
            proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("https_proxy") or os.environ.get("http_proxy") or ""

        if not proxy:
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
                try:
                    enabled = int(winreg.QueryValueEx(key, "ProxyEnable")[0])
                    server = winreg.QueryValueEx(key, "ProxyServer")[0] or ""
                except Exception:
                    enabled, server = 0, ""
                winreg.CloseKey(key)
                # ProxyServer may contain "http=...;https=..." or just "host:port"
                if server:
                    if enabled:
                        proxy = f"http://{server}" if "://" not in server else server
                    else:
                        # ProxyEnable=0 but proxy app may still be running — use it
                        proxy = f"http://{server}" if "://" not in server else server
                        logger.debug("ProxyEnable=0, but using ProxyServer: %s", proxy)
            except Exception:
                pass

        if proxy.strip():
            _shared_session.proxies = {"http": proxy, "https": proxy}
            logger.info("HTTP session using proxy: %s", proxy)
        else:
            logger.debug("HTTP session — no proxy configured")

    return _shared_session


def clear_http_session():
    """Reset the shared session (useful when proxy config changes)."""
    global _shared_session
    if _shared_session:
        _shared_session.close()
    _shared_session = None


from tradingagents.data.http.tencent import TencentSource
from tradingagents.data.http.eastmoney import EastmoneySource
from tradingagents.data.http.yahoo import YahooSource

__all__ = ["TencentSource", "EastmoneySource", "YahooSource",
           "get_http_session", "clear_http_session"]
