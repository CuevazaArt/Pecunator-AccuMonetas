# Start Pecunator HTTP API on :8765; loads api_key/api_secret from exampleJV/config.py when present (same as manual env).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& (Join-Path $root '.venv\Scripts\Activate.ps1')
python (Join-Path $root 'scripts\run_engine_with_examplejv.py')
