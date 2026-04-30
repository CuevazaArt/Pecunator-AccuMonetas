# Stop whatever process is listening on TCP 8765 (Pecunator HTTP API).
$ErrorActionPreference = 'SilentlyContinue'
$pids = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    Where-Object { $_ -gt 0 } |
    Sort-Object -Unique
if (-not $pids) {
    Write-Host 'Nothing listening on port 8765.'
    exit 0
}
foreach ($procId in $pids) {
    try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
        Write-Host "Stopped process $procId (was using port 8765)."
    } catch {
        Write-Warning "Could not stop PID ${procId}: $_"
    }
}
