# Starts the Python engine (minimized window), then the Flutter desktop app or dev runner.
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$enginePs1 = Join-Path $root 'scripts\engine\run_engine_immortal.ps1'
Start-Process powershell.exe -WindowStyle Minimized -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $enginePs1
) | Out-Null
Start-Sleep -Seconds 4
$releaseExe = Join-Path $root 'desktop_shell\build\windows\x64\runner\Release\pecunator_desktop.exe'
if (Test-Path $releaseExe) {
    Start-Process -FilePath $releaseExe
    exit 0
}
$debugExe = Join-Path $root 'desktop_shell\build\windows\x64\runner\Debug\pecunator_desktop.exe'
if (Test-Path $debugExe) {
    Start-Process -FilePath $debugExe
    exit 0
}
Start-Process powershell.exe -ArgumentList @(
    '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', (Join-Path $root 'scripts\ui\run_dashboard.ps1')
)
