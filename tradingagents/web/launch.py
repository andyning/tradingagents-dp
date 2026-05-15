"""Launch script for tradingagents-web — replaces current process with streamlit."""

import os
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app.py"
    os.execv(sys.executable, [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]])


if __name__ == "__main__":
    main()
