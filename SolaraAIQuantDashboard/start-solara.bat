@echo off
title Solara Launcher
set "ROOT=%USERPROFILE%\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\SolaraAIQuantDashboard"
echo.
echo   =========================================
echo    SolaraAIQuantDashboard - Starting up...
echo   =========================================
echo.
echo [1/4] Launching Django backend...
start "Solara - Django" cmd /k ""%ROOT%\start-be.bat""
timeout /t 3 /nobreak >nul
echo [2/4] Launching Celery worker...
start "Solara - Worker" cmd /k ""%ROOT%\start-celery-worker.bat""
timeout /t 2 /nobreak >nul
echo [3/4] Launching Celery beat...
start "Solara - Beat" cmd /k ""%ROOT%\start-celery-beat.bat""
timeout /t 2 /nobreak >nul
echo [4/4] Launching Vite frontend...
start "Solara - Frontend" cmd /k ""%ROOT%\start-fe.bat""
echo.
echo   All servers launched!
echo.
echo   Django API   ->  http://localhost:8000/api/
echo   Django Admin ->  http://localhost:8000/admin/
echo   Frontend     ->  http://localhost:5173
echo.
pause
