$host.UI.RawUI.WindowTitle = "SAQ - Survivor Log"
Set-Location $PSScriptRoot

Write-Host "Waiting for saq.log..." -ForegroundColor DarkGray
while (-not (Test-Path ".\logs\saq.log")) { Start-Sleep 2 }

Get-Content ".\logs\saq.log" -Wait -Tail 50 -Encoding UTF8 | Select-String "Survivor|survivor|ERROR"
