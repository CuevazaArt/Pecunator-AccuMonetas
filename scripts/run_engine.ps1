# Start Pecunator HTTP API on :8765 (direct engine startup).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& (Join-Path $root '.venv\Scripts\Activate.ps1')
python (Join-Path $root 'main.py')
