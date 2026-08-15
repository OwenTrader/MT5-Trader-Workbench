@echo off
title XAU USD Elliott Wave Theory Analysis
echo ===========================================
echo   XAU/USD Gold - Elliott Wave Theory
echo   5-wave impulse + ABC + Fib projections
echo   (MT5 -^> MT4 -^> Yahoo data fallback)
echo ===========================================
echo.

"F:\python-manager-26.0 (1)\python.exe" "%~dp0elliott_wave_mt5.py"
if %errorlevel% neq 0 (
    echo.
    echo Trying system python...
    python "%~dp0elliott_wave_mt5.py"
)

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script failed. See messages above.
) else (
    echo [OK] Elliott Wave report generated. Opening browser...
)
pause
