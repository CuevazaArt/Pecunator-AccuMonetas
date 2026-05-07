@echo off
echo Iniciando monitor de tasas Earn (stablecoins)...
echo Presiona Ctrl+C para detener.
echo.
cd /d "%~dp0"
.venv\Scripts\python.exe earn_rate_monitor.py
pause
