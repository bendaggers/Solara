@echo off
title Solara AI Quant — Main
cd /d "%~dp0"

:: ── Log monitor windows ───────────────────────────────────────────────────────
start "SAQ - Cycle Digest" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0log_cycle_digest.ps1"
start "SAQ - Survivor Log" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0log_survivor.ps1"

:: ── Main SAQ process ──────────────────────────────────────────────────────────
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_solara.ps1" --production %*

:: Fallback pause — catches the rare case where PowerShell itself fails to start.
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PowerShell failed to launch the script.
    echo         Error code: %ERRORLEVEL%
    echo.
    pause
)
