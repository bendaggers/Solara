@echo off
title Solara - OHLCV Sync
cd /d "C:\Users\BENMIC~1\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\SolaraAIQuantDashboard\BE"

echo [SYNC] Activating virtual environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [SYNC] No venv found - using system Python
)

echo [SYNC] Running backfill (fills gaps only)...
python manage.py backfill_ohlcv

echo [SYNC] Starting continuous sync loop...
python manage.py sync_ohlcv

echo.
echo [SYNC] Sync stopped.
pause
