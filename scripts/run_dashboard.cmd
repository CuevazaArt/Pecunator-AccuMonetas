@echo off
REM Doble clic o desde cmd: ejecuta el dashboard sin bloqueo por ExecutionPolicy.
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_dashboard.ps1"
if errorlevel 1 pause
