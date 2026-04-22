# =============================================================================
# Solara AI Quant — Launcher
# =============================================================================
# Usage:
#   Right-click → Run with PowerShell
#   Or double-click run_solara.bat (which calls this script)
#
# Optional args are forwarded to main.py:
#   .\run_solara.ps1 --production
#   .\run_solara.ps1 --production --dry-run
#   .\run_solara.ps1 --status
# =============================================================================

# Always run from the directory this script lives in, regardless of where
# it was launched from (e.g. desktop shortcut, task scheduler, etc.)
Set-Location -Path $PSScriptRoot

$VenvDir    = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir "Scripts\pip.exe"
$Activate   = Join-Path $VenvDir "Scripts\Activate.ps1"
$Reqs       = Join-Path $PSScriptRoot "requirements.txt"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Solara AI Quant" -ForegroundColor Cyan
Write-Host "  Dir: $PSScriptRoot" -ForegroundColor DarkGray
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Create .venv if it doesn't exist ───────────────────────────────────────
if (-not (Test-Path $VenvPython)) {
    Write-Host "[SETUP] .venv not found — creating virtual environment..." -ForegroundColor Yellow

    $PyVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Python not found in PATH. Install Python 3.11.7 first." -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "[SETUP] Using: $PyVersion" -ForegroundColor DarkGray

    python -m venv "$VenvDir"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create .venv." -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "[SETUP] .venv created." -ForegroundColor Green
}

# ── 2. Activate .venv ─────────────────────────────────────────────────────────
Write-Host "[INFO]  Activating .venv..." -ForegroundColor DarkGray
& $Activate

# ── 3. Install / sync dependencies ────────────────────────────────────────────
# Runs on first launch or when requirements.txt has changed.
$StampFile   = Join-Path $VenvDir ".reqs_installed"
$ReqsChanged = $true
if (Test-Path $StampFile) {
    $stampTime = (Get-Item $StampFile).LastWriteTime
    $reqsTime  = (Get-Item $Reqs).LastWriteTime
    if ($stampTime -ge $reqsTime) {
        $ReqsChanged = $false
    }
}

if ($ReqsChanged) {
    Write-Host "[SETUP] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $VenvPip install -r "$Reqs" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] pip install failed. Check requirements.txt." -ForegroundColor Red
        pause
        exit 1
    }
    New-Item -ItemType File -Path $StampFile -Force | Out-Null
    Write-Host "[SETUP] Dependencies installed." -ForegroundColor Green
} else {
    Write-Host "[INFO]  Dependencies up to date." -ForegroundColor DarkGray
}

# ── 4. Run main.py ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[START] python main.py $args" -ForegroundColor Green
Write-Host ""

& $VenvPython main.py @args
$ExitCode = $LASTEXITCODE

# ── 5. Keep window open on error ─────────────────────────────────────────────
Write-Host ""
if ($ExitCode -ne 0) {
    Write-Host "[EXIT]  main.py exited with code $ExitCode" -ForegroundColor Red
    Write-Host "        Press any key to close..." -ForegroundColor DarkGray
    pause
} else {
    Write-Host "[EXIT]  main.py finished cleanly." -ForegroundColor Green
    Write-Host "        Press any key to close..." -ForegroundColor DarkGray
    pause
}
