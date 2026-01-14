@echo off
chcp 65001 >nul

REM Run the watchdog script
cd /d "%~dp0"
python watchdog.py

pause