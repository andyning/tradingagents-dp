"""Single entry point for PyInstaller bundles — launches Streamlit in-process.

In dev mode: use `tradingagents-web` (calls launch.py subprocess).
In PyInstaller: this file is the Analysis entry point in tradingagents.spec.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_meipass_paths() -> None:
    """Add _MEIPASS directory to sys.path so 'import tradingagents' works."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and meipass not in sys.path:
        sys.path.insert(0, meipass)


def _setup_env() -> None:
    """Load .env from the .exe directory early (before config.py Settings init).

    In frozen mode, creates a template .env if none exists, then loads it
    via python-dotenv so DEEPSEEK_API_KEY is in os.environ before
    pydantic-settings reads it.
    """
    if not getattr(sys, "frozen", False):
        return

    exe_dir = Path(sys.executable).parent
    env_path = exe_dir / ".env"
    env_template = exe_dir / ".env.example"

    # Create template .env if missing (so user has a starting point)
    if not env_path.exists() and env_template.exists():
        env_path.write_text(env_template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[TradingAgents] Created .env template at {env_path}")
        print("[TradingAgents] Edit it to set your DEEPSEEK_API_KEY")

    # Load .env into os.environ before pydantic-settings reads it
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            print(f"[TradingAgents] Loaded config from {env_path}")
        except ImportError:
            pass  # python-dotenv not installed


def main() -> None:
    """Start Streamlit in-process (no subprocess)."""
    _ensure_meipass_paths()
    _setup_env()

    # Resolve app.py path
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        app_path = os.path.join(meipass, "tradingagents", "web", "app.py")
    else:
        app_path = str(Path(__file__).parent / "tradingagents" / "web" / "app.py")

    print("[TradingAgents] Starting Streamlit server...")
    print("[TradingAgents] Open http://localhost:8501 in your browser")
    print("[TradingAgents] Press Ctrl+C to stop")

    from streamlit.web.bootstrap import run

    run(
        str(app_path),
        is_hello=False,
        args=[],
        flag_options={
            "server.headless": True,
            "server.port": 8501,
            "server.enableCORS": False,
            "server.enableXsrfProtection": False,
            "browser.serverPort": 8501,
            "browser.gatherUsageStats": False,
            "global.developmentMode": False,
            "server.fileWatcherType": "none",
        },
    )


if __name__ == "__main__":
    main()
