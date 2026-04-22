@echo off
title Solara - Vite Frontend
set "FE=C:\Users\BENMIC~1\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\SolaraAIQuantDashboard\FE"
echo [FE] Navigating to %FE%
cd /d "%FE%"
echo [FE] Starting Vite on http://localhost:5173
npm run dev
echo.
echo [FE] Server stopped.
pause