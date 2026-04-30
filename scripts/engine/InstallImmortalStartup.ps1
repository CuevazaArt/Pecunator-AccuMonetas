# Install startup shortcut so Pecunator launcher runs after Windows logon.
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$launcher = Join-Path $root 'scripts\ui\PecunatorDesktopLauncher.ps1'
if (-not (Test-Path $launcher)) {
    throw "Missing launcher script: $launcher"
}

$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'PecunatorCore Immortal.lnk'

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($lnkPath)
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Auto-start PecunatorCore (engine supervisor + desktop UI)'
$shortcut.Save()

Write-Host "Startup shortcut created: $lnkPath"
