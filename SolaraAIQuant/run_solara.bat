@echo off
title Solara AI Quant
cd /d "%~dp0"

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
