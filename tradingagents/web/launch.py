"""Launch script for tradingagents-web — starts Streamlit, handles Ctrl+C."""

import subprocess
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app.py"
    args = [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    print(f"Starting Streamlit server... (Ctrl+C to stop)")
    print(f"Open http://localhost:8501 in your browser")
    try:
        subprocess.run(args)
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
