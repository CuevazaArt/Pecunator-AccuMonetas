# Keep Pecunator HTTP API alive by relaunching on crash/exit.
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$runner = Join-Path $PSScriptRoot 'run_engine.ps1'
if (-not (Test-Path $runner)) {
    throw "Missing engine runner: $runner"
}

while ($true) {
    $occupied = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($occupied) {
        Start-Sleep -Seconds 5
        continue
    }
    Write-Host "[engine-immortal] starting engine..." -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runner
    $code = $LASTEXITCODE
    Write-Warning "[engine-immortal] engine exited with code $code. Restarting in 3s..."
    Start-Sleep -Seconds 3
}
