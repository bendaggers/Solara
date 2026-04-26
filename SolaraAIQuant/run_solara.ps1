# ==============================================================================
# Solara AI Quant - Launcher
# ==============================================================================
# DO NOT double-click this file - Windows opens .ps1 in Notepad by default.
# Double-click run_solara.bat instead.
#
# Optional args forwarded to main.py:
#   --production              live MT5 orders
#   --production --dry-run    MT5 connected but no real orders
#   --status                  show config and model summary
# ==============================================================================

$ErrorActionPreference = "Continue"

# Always run from the directory this script lives in
Set-Location -Path $PSScriptRoot

$VenvDir    = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Activate   = Join-Path $VenvDir "Scripts\Activate.ps1"
$Reqs       = Join-Path $PSScriptRoot "requirements.txt"

function Pause-And-Exit($code) {
    Write-Host ""
    Write-Host "  Press any key to close..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit $code
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Solara AI Quant" -ForegroundColor Cyan
Write-Host "  $PSScriptRoot" -ForegroundColor DarkGray
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Find Python 3.11 - required for ML package compatibility
# Try py launcher first (Windows Python Launcher lets you pick version)
$PythonExe = $null
$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PyLauncher) {
    $py311 = & py -3.11 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $PythonExe = "py"
        $PythonArgs = @("-3.11")
        Write-Host "[INFO]  Python: $py311 (via py -3.11)" -ForegroundColor DarkGray
    }
}

# Fall back to checking the default 'python' command
if (-not $PythonExe) {
    $PyExe = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PyExe) {
        Write-Host "[ERROR] Python not found in PATH." -ForegroundColor Red
        Write-Host "        Install Python 3.11.7 from python.org and tick 'Add to PATH'." -ForegroundColor Red
        Pause-And-Exit 1
    }
    $PyVersion = & python --version 2>&1
    $PythonExe = "python"
    $PythonArgs = @()
    Write-Host "[INFO]  Python: $PyVersion" -ForegroundColor DarkGray

    # Warn if not 3.11 - ML packages (catboost, lightgbm) may fail on other versions
    if ($PyVersion -notmatch "3\.11") {
        Write-Host ""
        Write-Host "[WARN]  Python 3.11 is required. You have: $PyVersion" -ForegroundColor Yellow
        Write-Host "        Download Python 3.11.7 from:" -ForegroundColor Yellow
        Write-Host "        https://www.python.org/downloads/release/python-3117/" -ForegroundColor Yellow
        Write-Host "        After install, re-run this script." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "        Continue anyway? (y to proceed, any other key to exit)" -ForegroundColor Yellow
        $key = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        if ($key.Character -ne 'y') {
            Pause-And-Exit 1
        }
        Write-Host ""
    }
}

# 2. Create .venv if it does not exist
if (-not (Test-Path $VenvPython)) {
    Write-Host "[SETUP] .venv not found - creating virtual environment..." -ForegroundColor Yellow
    & $PythonExe @PythonArgs -m venv "$VenvDir"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        Write-Host "[ERROR] Failed to create .venv." -ForegroundColor Red
        Pause-And-Exit 1
    }
    Write-Host "[SETUP] .venv created." -ForegroundColor Green
}

# 3. Activate .venv
& $Activate
Write-Host "[INFO]  .venv activated." -ForegroundColor DarkGray

# 4. Install / sync dependencies
$StampFile   = Join-Path $VenvDir ".reqs_installed"
$ReqsChanged = $true
if ((Test-Path $StampFile) -and (Test-Path $Reqs)) {
    if ((Get-Item $StampFile).LastWriteTime -ge (Get-Item $Reqs).LastWriteTime) {
        $ReqsChanged = $false
    }
}

if ($ReqsChanged) {
    Write-Host "[SETUP] Installing dependencies (first run - may take a few minutes)..." -ForegroundColor Yellow
    # Use 'python -m pip' instead of pip.exe directly.
    # Windows may block newly-created pip.exe in restricted folders (MQL5, AppData, etc.)
    # python.exe is already trusted; running pip as a module bypasses the block.
    & $VenvPython -m pip install -r "$Reqs" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] pip install failed. Check requirements.txt or your internet connection." -ForegroundColor Red
        Pause-And-Exit 1
    }
    New-Item -ItemType File -Path $StampFile -Force | Out-Null
    Write-Host "[SETUP] Dependencies ready." -ForegroundColor Green
} else {
    Write-Host "[INFO]  Dependencies up to date." -ForegroundColor DarkGray
}

# 5. Run main.py
Write-Host ""
if ($args.Count -gt 0) {
    Write-Host "[START] python main.py $args" -ForegroundColor Green
} else {
    Write-Host "[START] python main.py  (development mode)" -ForegroundColor Green
}
Write-Host ""

& $VenvPython main.py @args
$ExitCode = $LASTEXITCODE

# 6. Done
Write-Host ""
if ($ExitCode -ne 0) {
    Write-Host "[EXIT]  main.py stopped with code $ExitCode" -ForegroundColor Red
} else {
    Write-Host "[EXIT]  main.py finished cleanly." -ForegroundColor Green
}
Pause-And-Exit $ExitCode
