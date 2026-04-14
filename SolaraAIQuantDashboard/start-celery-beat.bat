@echo off
title Solara - Celery Beat
set "BE=C:\Users\BENMIC~1\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\SolaraAIQuantDashboard\BE"
cd /d "%BE%"
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
echo [BEAT] Starting Celery beat scheduler...
python -m celery -A core beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
echo.
echo [BEAT] Stopped.
pause