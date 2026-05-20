"""HTTP-based data source modules.

Each module uses only `requests` + standard library — no third-party
SDK dependencies.  All return DataFrames compatible with the existing
Pydantic schemas in `tradingagents.data.schema`.

Per-domain connectivity auto-detection: probes each target host with both
direct and proxy connections, caches the working profile.  Transparent to
callers — just use `get_http_session(host)`.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import requests

from tradingagents.logging import get_logger

logger = get_logger(__name__)

# ── proxy URL (auto-detected from OS environment on every Refresh) ────
_proxy_url: str = ""


def _detect_proxy_url() -> str:
    """Detect proxy URL from OS environment. Called on import and every Refresh.

    Priority:
      1. PROXY_URL from .env / Settings
      2. HTTPS_PROXY / HTTP_PROXY / https_proxy / http_proxy env vars
      3. Windows registry (HKCU Internet Settings ProxyServer)
      4. macOS System Configuration (networksetup)
      5. Linux environment variables
    """
    proxy = ""
    try:
        from tradingagents.config import get_settings
        proxy = get_settings().proxy_url or ""
    except Exception:
        pass
    if not proxy:
        import os
        proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
                 or os.environ.get("https_proxy") or os.environ.get("http_proxy") or "")
    if not proxy:
        import platform
        system = platform.system()
        if system == "Windows":
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
                if server:
                    proxy = f"http://{server}" if "://" not in server else server
            except Exception:
                pass
        elif system == "Darwin":  # macOS
            try:
                import subprocess
                for proto in ("https", "http"):
                    result = subprocess.run(
                        ["networksetup", "-getwebproxy", "Wi-Fi"],
                        capture_output=True, text=True, timeout=3,
                    )
                    if result.returncode == 0 and "Enabled: Yes" in result.stdout:
                        for line in result.stdout.split("\n"):
                            if "Server:" in line:
                                host = line.split(":", 1)[1].strip()
                            if "Port:" in line:
                                port = line.split(":", 1)[1].strip()
                        if host and port:
                            proxy = f"http://{host}:{port}"
                            break
                if not proxy:
                    # Try SOCKS proxy
                    result = subprocess.run(
                        ["networksetup", "-getsocksfirewallproxy", "Wi-Fi"],
                        capture_output=True, text=True, timeout=3,
                    )
                    if result.returncode == 0 and "Enabled: Yes" in result.stdout:
                        for line in result.stdout.split("\n"):
                            if "Server:" in line:
                                host = line.split(":", 1)[1].strip()
                            if "Port:" in line:
                                port = line.split(":", 1)[1].strip()
                        if host and port:
                            proxy = f"socks5h://{host}:{port}"
            except Exception:
                pass
        else:  # Linux
            # Already handled by HTTP_PROXY/HTTPS_PROXY env vars above
            pass
    return proxy.strip()


def refresh_proxy():
    """Re-detect proxy URL from OS environment. Called on Refresh."""
    global _proxy_url
    _proxy_url = _detect_proxy_url()
    if _proxy_url:
        logger.info("Proxy detected: %s", _proxy_url)
    else:
        logger.debug("No proxy detected — direct mode")


# Initial detection
_proxy_url = _detect_proxy_url()
if _proxy_url:
    logger.info("Proxy detected: %s", _proxy_url)
else:
    logger.debug("No proxy detected — direct mode")


# ── per-domain connectivity profile ────────────────────────────────────
# Maps hostname → True (use proxy), False (direct), or None (unprobed)
_profile: dict[str, bool | None] = {}
_profile_lock = threading.Lock()


def _probe_host(host: str, use_proxy: bool, timeout: float = 3.0) -> bool:
    """Quick connectivity check to a host. Returns True if reachable."""
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0",
    })
    if use_proxy and _proxy_url:
        sess.proxies = {"http": _proxy_url, "https": _proxy_url}
    try:
        resp = sess.get(f"https://{host}/", timeout=timeout)
        # Any response (even 404/403) means the host is reachable
        return True
    except Exception:
        return False


def get_connectivity_profile(host: str) -> bool:
    """Return True if this host should use proxy, False for direct.
    Probes on first call, caches the result.
    """
    global _profile
    if host not in _profile or _profile[host] is None:
        with _profile_lock:
            if host not in _profile or _profile[host] is None:
                if not _proxy_url:
                    _profile[host] = False
                    logger.debug("[%s] no proxy available → direct", host)
                else:
                    # Try direct first (faster, no proxy overhead)
                    direct_ok = _probe_host(host, use_proxy=False)
                    if direct_ok:
                        _profile[host] = False
                        logger.debug("[%s] direct OK", host)
                    else:
                        proxy_ok = _probe_host(host, use_proxy=True)
                        if proxy_ok:
                            _profile[host] = True
                            logger.info("[%s] direct blocked → using proxy", host)
                        else:
                            _profile[host] = False
                            logger.warning("[%s] unreachable both direct and via proxy", host)
    return _profile.get(host, False)


def reset_connectivity_profile():
    """Clear cached connectivity decisions (called on Refresh)."""
    global _profile
    with _profile_lock:
        _profile.clear()
    logger.debug("Connectivity profile reset")


# ── per-host session cache ─────────────────────────────────────────────
_sessions: dict[str, requests.Session] = {}
_sessions_lock = threading.Lock()


def get_http_session(host: str = "") -> requests.Session:
    """Return a requests.Session for the given host, with proxy if needed.
    If host is empty, returns a direct session (no proxy).
    """
    use_proxy = get_connectivity_profile(host) if host else False
    cache_key = f"proxy_{host}" if use_proxy else f"direct_{host or 'default'}"

    if cache_key not in _sessions:
        with _sessions_lock:
            if cache_key not in _sessions:
                sess = requests.Session()
                sess.headers.update({
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "zh-CN,zh;q=0.9",
                })
                if use_proxy and _proxy_url:
                    sess.proxies = {"http": _proxy_url, "https": _proxy_url}
                _sessions[cache_key] = sess
    return _sessions[cache_key]


def clear_http_session(host: str = ""):
    """Reset cached session(s). Call when proxy config changes."""
    global _sessions
    with _sessions_lock:
        if host:
            for k in list(_sessions):
                if host in k:
                    _sessions.pop(k, None)
        else:
            _sessions.clear()
        refresh_proxy()
        reset_connectivity_profile()


class _ResilientSession:
    """Persistent session with per-request proxy fallback on connection error.
    Maintains cookie state across requests (required for Yahoo crumb flow).
    """

    def __init__(self, host: str):
        self._host = host
        self._use_proxy = get_connectivity_profile(host) if host else False
        self._sess = self._make_session()

    def _make_session(self) -> requests.Session:
        sess = requests.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        if self._use_proxy and _proxy_url:
            sess.proxies = {"http": _proxy_url, "https": _proxy_url}
        return sess

    def get(self, url: str, timeout: float = 15, **kwargs) -> requests.Response:
        for attempt in range(2):
            try:
                return self._sess.get(url, timeout=timeout, **kwargs)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 0 and _proxy_url:
                    alt_mode = not self._use_proxy
                    logger.debug("[%s] retrying with proxy=%s", self._host, alt_mode)
                    self._sess = requests.Session()
                    self._sess.headers.update({
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    })
                    if alt_mode:
                        self._sess.proxies = {"http": _proxy_url, "https": _proxy_url}
                    self._use_proxy = alt_mode
                    _profile[self._host] = alt_mode
                    continue
                raise

    @property
    def headers(self):
        return self._sess.headers


def resilient_session(host: str) -> _ResilientSession:
    """Return a session-like object that auto-retries with alternate proxy mode."""
    return _ResilientSession(host)


# Legacy alias for callers that don't pass a host
def get_session_direct() -> requests.Session:
    """Return a direct (no-proxy) session. For sources known to work without proxy."""
    return get_http_session("")


from tradingagents.data.http.tencent import TencentSource
from tradingagents.data.http.eastmoney import EastmoneySource
from tradingagents.data.http.yahoo import YahooSource

__all__ = ["TencentSource", "EastmoneySource", "YahooSource",
           "get_http_session", "clear_http_session",
           "reset_connectivity_profile", "get_connectivity_profile"]
