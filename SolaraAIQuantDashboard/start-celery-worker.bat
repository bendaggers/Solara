@echo off
title Solara - Celery Worker
set "BE=C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\SolaraAIQuantDashboard\BE"

cd /d "%BE%"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo [WORKER] Running startup catch-up backfill...
echo [WORKER] This fills any candles missed while the system was off.
python manage.py backfill_ohlcv
echo [WORKER] Backfill complete.
echo.

echo [WORKER] Starting Celery worker...
python -m celery -A core worker --loglevel=info --pool=solo

echo.
echo [WORKER] Stopped.
pause
