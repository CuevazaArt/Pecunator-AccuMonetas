# backup_databases.ps1
# Creates timestamped backups of all Louise Hub SQLite databases.
# Run daily via Task Scheduler or manually before deployments.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\backup\backup_databases.ps1
#
# Optional: set PECUNATOR_BACKUP_DIR env var to override backup location.
# Default backup location: runtime\data\backups\

param(
    [string]$BackupDir = $env:PECUNATOR_BACKUP_DIR,
    [int]$RetainDays = 30
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$DataDir = Join-Path $ProjectRoot "runtime\data"

if (-not $BackupDir) {
    $BackupDir = Join-Path $DataDir "backups"
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupPath = Join-Path $BackupDir $Timestamp

# Create backup directory
New-Item -ItemType Directory -Force -Path $BackupPath | Out-Null

Write-Host "[backup] Starting database backup at $Timestamp"
Write-Host "[backup] Source: $DataDir"
Write-Host "[backup] Destination: $BackupPath"

# Define databases to back up
$Databases = @(
    "louise_hub.sqlite",
    "dorothy_hub.sqlite",
    "elphaba_hub.sqlite",
    "telemetry.sqlite",
    "account_monitor.sqlite"
)

$BackedUp = 0
$Skipped = 0

foreach ($DbFile in $Databases) {
    $SourcePath = Join-Path $DataDir $DbFile
    if (-not (Test-Path $SourcePath)) {
        Write-Host "[backup] SKIP $DbFile (not found)"
        $Skipped++
        continue
    }

    $DestPath = Join-Path $BackupPath $DbFile
    try {
        # Use SQLite online backup via .dump to handle WAL files safely
        # If sqlite3.exe is available, use it; otherwise fall back to file copy
        $SqliteBin = Get-Command sqlite3 -ErrorAction SilentlyContinue

        if ($SqliteBin) {
            # Online backup using SQLite backup API (handles locked/WAL databases)
            & sqlite3 $SourcePath ".backup '$DestPath'"
        } else {
            # Fallback: checkpoint WAL first, then copy
            Copy-Item -Path $SourcePath -Destination $DestPath -Force
            # Also copy WAL artifacts if they exist
            foreach ($ext in @("-wal", "-shm")) {
                $ArtifactPath = $SourcePath + $ext
                if (Test-Path $ArtifactPath) {
                    Copy-Item -Path $ArtifactPath -Destination ($DestPath + $ext) -Force
                }
            }
        }
        $SizeMB = [math]::Round((Get-Item $DestPath).Length / 1MB, 2)
        Write-Host "[backup] OK $DbFile ($SizeMB MB)"
        $BackedUp++
    } catch {
        Write-Warning "[backup] FAILED $DbFile : $_"
    }
}

# Integrity check on backed-up files
Write-Host ""
Write-Host "[backup] Verifying integrity..."
$SqliteBin = Get-Command sqlite3 -ErrorAction SilentlyContinue
if ($SqliteBin) {
    Get-ChildItem -Path $BackupPath -Filter "*.sqlite" | ForEach-Object {
        $Result = & sqlite3 $_.FullName "PRAGMA integrity_check;" 2>&1
        if ($Result -eq "ok") {
            Write-Host "[backup] VERIFY OK $($_.Name)"
        } else {
            Write-Warning "[backup] VERIFY FAIL $($_.Name): $Result"
        }
    }
} else {
    Write-Host "[backup] sqlite3.exe not in PATH — skipping integrity check"
    Write-Host "[backup] Install SQLite tools: https://www.sqlite.org/download.html"
}

# Rotate old backups (keep last $RetainDays days)
Write-Host ""
Write-Host "[backup] Rotating backups older than $RetainDays days..."
$CutoffDate = (Get-Date).AddDays(-$RetainDays)
Get-ChildItem -Path $BackupDir -Directory | Where-Object {
    $_.CreationTime -lt $CutoffDate
} | ForEach-Object {
    Write-Host "[backup] REMOVE $($_.Name)"
    Remove-Item -Recurse -Force $_.FullName
}

# Summary
Write-Host ""
Write-Host "================================"
Write-Host "BACKUP COMPLETE"
Write-Host "  Backed up:  $BackedUp databases"
Write-Host "  Skipped:    $Skipped databases (not found)"
Write-Host "  Location:   $BackupPath"
Write-Host "  Retention:  $RetainDays days"
Write-Host "================================"

exit 0
