@echo off
title XAU USD Scenario Playbook
echo ===============================================
echo   XAU/USD Gold - Scenario Playbook (Decision Tree)
echo   Pure Price Action + Branched Scenario Guidance
echo   (MT5 -^> MT4 -^> Yahoo data fallback)
echo ===============================================
echo.

"F:\python-manager-26.0 (1)\python.exe" "%~dp0scenario_playbook_mt5.py"
if %errorlevel% neq 0 (
    echo.
    echo Trying system python...
    python "%~dp0scenario_playbook_mt5.py"
)

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script failed. See messages above.
) else (
    echo [OK] Playbook generated. Opening browser...
)
pause
