@echo off
title XAU USD Elliott Wave Analysis
echo =========================================
echo   XAU/USD Gold - Elliott Wave Analysis
echo   ZigZag + 5-wave / ABC pattern
echo =========================================
echo.

"F:\python-manager-26.0 (1)\python.exe" "%~dp0wave_analysis.py"
if %errorlevel% neq 0 (
    echo.
    echo Trying system python...
    python "%~dp0wave_analysis.py"
)

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script failed. See messages above.
) else (
    echo [OK] Report generated. Opening browser...
)
pause
