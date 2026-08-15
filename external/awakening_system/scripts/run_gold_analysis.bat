@echo off
title XAU USD Indicator Analysis
echo =========================================
echo   XAU/USD Gold - Indicator Analysis
echo   Tech indicators + intraday strategies
echo =========================================
echo.

"F:\python-manager-26.0 (1)\python.exe" "%~dp0gold_analysis.py"
if %errorlevel% neq 0 (
    echo.
    echo Trying system python...
    python "%~dp0gold_analysis.py"
)

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script failed. See messages above.
) else (
    echo [OK] Report generated. Opening browser...
)
pause
