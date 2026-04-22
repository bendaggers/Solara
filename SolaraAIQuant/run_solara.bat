@echo off
:: Solara AI Quant — Double-click launcher
:: Calls run_solara.ps1 via PowerShell, bypassing the default execution policy
:: that blocks .ps1 files from running when double-clicked.
::
:: To pass args:  run_solara.bat --production
::                run_solara.bat --production --dry-run
::                run_solara.bat --status

pushd "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_solara.ps1" %*
popd
