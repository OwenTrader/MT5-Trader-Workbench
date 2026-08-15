@echo off
title XAU USD PA x Elliott Fusion Analysis
echo ===============================================
echo   XAU/USD Gold - PA x Elliott Wave Fusion
echo   Price Action + Elliott Wave (Institutional)
echo   (MT5 -^> MT4 -^> Yahoo data fallback)
echo ===============================================
echo.

"F:\python-manager-26.0 (1)\python.exe" "%~dp0pa_wave_fusion_mt5.py"
if %errorlevel% neq 0 (
    echo.
    echo Trying system python...
    python "%~dp0pa_wave_fusion_mt5.py"
)

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script failed. See messages above.
) else (
    echo [OK] Fusion report generated. Opening browser...
)
pause
