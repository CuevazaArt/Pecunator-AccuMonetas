@echo off
echo Iniciando monitor de tasas de prestamo (stablecoins)...
echo Presiona Ctrl+C para detener.
echo.
cd /d "%~dp0"
.venv\Scripts\python.exe loan_rate_monitor.py
pause
