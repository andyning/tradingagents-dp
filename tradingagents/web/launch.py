"""Launch script for tradingagents-web — handles Ctrl+C cleanly on Windows.
In PyInstaller frozen mode, routes to the in-process launcher.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path


def main():
    # In PyInstaller frozen mode, use in-process launcher (no subprocess)
    if getattr(sys, "frozen", False):
        from main_entry import main as bundled_main
        bundled_main()
        return

    # Dev mode: spawn Streamlit via subprocess
    app_path = Path(__file__).parent / "app.py"
    args = [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    print("Starting Streamlit server... (Ctrl+C to stop)")
    print("Open http://localhost:8501 in your browser")

    # Use Popen so we can terminate the child on Ctrl+C
    proc = subprocess.Popen(args)

    def _cleanup(signum=None, frame=None):
        """Kill child process and exit cleanly."""
        try:
            # On Windows, terminate() sends CTRL_BREAK_EVENT which Streamlit ignores
            # when background threads (Futu/IB) are still running.  Use kill()
            # directly for instant shutdown, then clean up after.
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        except Exception:
            pass
        # Help the OS clean up orphaned child threads
        print("\nStopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    # Wait for child to exit (blocking)
    try:
        proc.wait()
    except KeyboardInterrupt:
        _cleanup()


if __name__ == "__main__":
    main()
