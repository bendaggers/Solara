$host.UI.RawUI.WindowTitle = "SAQ - Cycle Digest"
Set-Location $PSScriptRoot

Write-Host "Waiting for cycle_digest.log..." -ForegroundColor DarkGray
while (-not (Test-Path ".\logs\cycle_digest.log")) { Start-Sleep 2 }

Get-Content ".\logs\cycle_digest.log" -Wait -Tail 800 -Encoding UTF8
