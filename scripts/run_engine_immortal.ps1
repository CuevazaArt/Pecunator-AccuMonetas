# Supervise Pecunator engine forever: restarts after crashes.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

while ($true) {
    $occupied = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($occupied) {
        Start-Sleep -Seconds 5
        continue
    }
    try {
        & (Join-Path $root '.venv\Scripts\Activate.ps1')
        python (Join-Path $root 'scripts\run_engine_with_examplejv.py')
    } catch {
        Write-Warning "Engine supervisor caught exception: $_"
    }
    Write-Host "Engine exited; restarting in 3 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}
