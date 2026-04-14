@echo off
title Solara - Django Backend
set "BE=C:\Users\BENMIC~1\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\SolaraAIQuantDashboard\BE"
echo [BE] Navigating to %BE%
cd /d "%BE%"
echo [BE] Activating virtual environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [BE] No venv found - using system Python
)
echo.
echo [BE] Checking for OHLCV gaps...
python manage.py check_gaps
echo.
echo [BE] Starting Django on http://localhost:8000
python manage.py runserver
echo.
echo [BE] Server stopped.
pause
