#!/usr/bin/env bash
# TradingAgents — One-click installer for macOS & Linux
# Usage: bash install.sh

set -e

echo ""
echo "========================================"
echo "  TradingAgents — Installer"
echo "========================================"
echo ""

# ── Check Python ──────────────────────────────────────────────────
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        major=$(echo $ver | cut -d. -f1)
        minor=$(echo $ver | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.10+ not found."
    echo "macOS: brew install python@3.10"
    echo "Ubuntu: sudo apt install python3.10 python3.10-venv"
    exit 1
fi
echo "[OK] Python: $($PYTHON_CMD --version)"

# ── Create venv ───────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "[OK] Virtual environment created."
else
    echo "[OK] Virtual environment already exists."
fi

# Activate
source "$VENV_DIR/bin/activate"

# ── Install package ───────────────────────────────────────────────
echo "Installing TradingAgents (this may take a few minutes on first run)..."
pip install -e "$SCRIPT_DIR"
echo "[OK] Package installed."

# ── Setup .env ────────────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "[OK] .env created from .env.example"
    else
        cat > "$ENV_FILE" << 'EOF'
# DeepSeek API key (required)
DEEPSEEK_API_KEY=sk-your-key-here

# Optional overrides
# TA_LLM_BASE_URL=https://api.deepseek.com
# TA_ANALYSIS_DEPTH=medium
# TA_OUTPUT_LANGUAGE=Chinese
EOF
        echo "[OK] .env created with defaults"
    fi
    echo ""
    echo ">>> IMPORTANT: Edit .env and add your DeepSeek API key <<<"
    echo "    nano $ENV_FILE"
    echo ""
else
    echo "[OK] .env already exists."
fi

# ── Linux: check for CJK fonts ────────────────────────────────────
if [ "$(uname -s)" = "Linux" ]; then
    if ! fc-list :lang=zh 2>/dev/null | grep -q .; then
        echo "[NOTE] No Chinese fonts detected. Install for PDF export:"
        echo "       sudo apt install fonts-noto-cjk    # Debian/Ubuntu"
        echo "       sudo yum install google-noto-cjk-fonts  # RHEL/Fedora"
    fi
fi

# ── Verify ───────────────────────────────────────────────────────
echo ""
echo "Verifying installation..."
CHECK=$($PYTHON_CMD -c "from tradingagents.graph import TradingAgentsGraph; from tradingagents.llm import DeepSeekClient; print('OK')" 2>&1) || true
if echo "$CHECK" | grep -q "OK"; then
    echo ""
    echo "========================================"
    echo "  Installation successful!"
    echo "========================================"
    echo ""
    echo "Commands available:"
    echo "  tradingagents -s <SYMBOL> -d <DATE>   # CLI"
    echo "  tradingagents-web                       # Web dashboard"
    echo "  tradingagents-api                       # REST API"
    echo ""
    echo "To start:"
    echo "  source venv/bin/activate"
    echo "  tradingagents-web"
    echo ""
else
    echo "WARNING: Import verification returned unexpected output:"
    echo "$CHECK"
fi
