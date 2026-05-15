"""Launch script for tradingagents-web — invokes streamlit run."""

import subprocess
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app.py"
    args = [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    subprocess.run(args)


if __name__ == "__main__":
    main()
