@echo off
chcp 65001 >nul
echo ========================================
echo   SOLARA SIMPLE WATCHER
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11.7 from python.org
    pause
    exit /b 1
)

echo Checking Python version...
python -c "import sys; print('Python {0}.{1}.{2}'.format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro))"

echo.
echo ========================================
echo Starting watcher...
echo ========================================
echo.

REM Run the watchdog script
cd /d "%~dp0"
python watchdog.py

pause