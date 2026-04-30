# Start Pecunator HTTP API on :8765.
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root

$venvPy = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    & $venvPy main.py
}
else {
    Write-Warning ".venv not found at $venvPy ; using system python."
    python main.py
}
