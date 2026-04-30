# Creates "PecunatorCore.lnk" on the user Desktop (engine + UI launcher).
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$launcher = Join-Path $PSScriptRoot 'PecunatorDesktopLauncher.ps1'
if (-not (Test-Path $launcher)) {
    Write-Error "Missing: $launcher"
}
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'PecunatorCore.lnk'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($lnkPath)
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'PecunatorCore: motor HTTP + app escritorio'
$releaseExe = Join-Path $root 'desktop_shell\build\windows\x64\runner\Release\pecunator_desktop.exe'
if (Test-Path $releaseExe) {
    $shortcut.IconLocation = "$releaseExe,0"
}
$shortcut.Save()
Write-Host "Shortcut created: $lnkPath"
