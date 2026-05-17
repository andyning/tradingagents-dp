# TradingAgents — One-click installer for Windows
# Usage: .\install.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TradingAgents — Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Check Python ──────────────────────────────────────────────────
$pythonCmd = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $v = & $cmd --version 2>&1
        if ($v -match "(\d+)\.(\d+)") {
            $major = [int]$matches[1]; $minor = [int]$matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                $pythonCmd = $cmd; break
            }
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "ERROR: Python 3.10+ not found." -ForegroundColor Red
    Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}
Write-Host "Python: $(& $pythonCmd --version)" -ForegroundColor Green

# ── Create venv ───────────────────────────────────────────────────
$venvDir = Join-Path $PSScriptRoot "venv"
if (-not (Test-Path $venvDir)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & $pythonCmd -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create venv." -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}

# ── Activate venv ─────────────────────────────────────────────────
$activateScript = Join-Path $venvDir "Scripts" "Activate.ps1"
. $activateScript

Write-Host "Installing TradingAgents (this may take a few minutes on first run)..." -ForegroundColor Yellow
pip install -e "$PSScriptRoot"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed." -ForegroundColor Red
    exit 1
}
Write-Host "Package installed." -ForegroundColor Green

# ── Setup .env ────────────────────────────────────────────────────
$envFile = Join-Path $PSScriptRoot ".env"
$envExample = Join-Path $PSScriptRoot ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host ".env created from .env.example" -ForegroundColor Yellow
    } else {
        @"
# DeepSeek API key (required)
DEEPSEEK_API_KEY=sk-your-key-here

# Optional overrides
# TA_LLM_BASE_URL=https://api.deepseek.com
# TA_ANALYSIS_DEPTH=medium
# TA_OUTPUT_LANGUAGE=Chinese
"@ | Out-File -FilePath $envFile -Encoding utf8
        Write-Host ".env created with defaults" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host ">>> IMPORTANT: Edit .env and add your DeepSeek API key <<<" -ForegroundColor Cyan
    Write-Host "    notepad $envFile" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host ".env already exists." -ForegroundColor Green
}

# ── Verify ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Verifying installation..." -ForegroundColor Yellow
$check = & python -c "from tradingagents.graph import TradingAgentsGraph; from tradingagents.llm import DeepSeekClient; print('OK')" 2>&1
if ($check -match "OK") {
    Write-Host ""
    Write-Host "Installation successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Commands available:" -ForegroundColor Cyan
    Write-Host "  tradingagents -s <SYMBOL> -d <DATE>   # CLI"
    Write-Host "  tradingagents-web                       # Web dashboard"
    Write-Host "  tradingagents-api                       # REST API"
    Write-Host ""
    Write-Host "To start: activate the venv, then run a command:" -ForegroundColor White
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "  tradingagents-web" -ForegroundColor Yellow
} else {
    Write-Host "WARNING: Import verification returned unexpected output:" -ForegroundColor Red
    Write-Host $check
}
