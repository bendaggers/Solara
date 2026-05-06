@echo off
title Solara AI Quant — Main
cd /d "%~dp0"

:: ── Log monitor windows ───────────────────────────────────────────────────────
:: Each window waits for its log file to appear (created on first SAQ run),
:: then tails it live. Close these windows manually when done.

start "SAQ - Cycle Digest" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Set-Location '%~dp0'; $host.UI.RawUI.WindowTitle = 'SAQ - Cycle Digest'; ^
   Write-Host 'Waiting for cycle_digest.log...' -ForegroundColor DarkGray; ^
   while (-not (Test-Path '.\logs\cycle_digest.log')) { Start-Sleep 2 }; ^
   Get-Content '.\logs\cycle_digest.log' -Wait -Tail 800 -Encoding UTF8"

start "SAQ - Survivor Log" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Set-Location '%~dp0'; $host.UI.RawUI.WindowTitle = 'SAQ - Survivor Log'; ^
   Write-Host 'Waiting for saq.log...' -ForegroundColor DarkGray; ^
   while (-not (Test-Path '.\logs\saq.log')) { Start-Sleep 2 }; ^
   Get-Content '.\logs\saq.log' -Wait -Tail 50 -Encoding UTF8 | Select-String 'Survivor|ERROR'"

:: ── Main SAQ process ──────────────────────────────────────────────────────────
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_solara.ps1" --production %*

:: Fallback pause — catches the rare case where PowerShell itself fails to start.
:: Normally Pause-And-Exit inside the .ps1 handles keeping the window open.
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PowerShell failed to launch the script.
    echo         Error code: %ERRORLEVEL%
    echo.
    pause
)
