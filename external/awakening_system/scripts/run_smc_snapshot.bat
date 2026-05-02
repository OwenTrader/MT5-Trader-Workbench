@echo off
title XAU USD Market Depth Snapshot (SMC)
echo ===============================================
echo   XAU/USD Gold - Market Depth Snapshot
echo   SMC: Order Block + FVG + Liquidity + IF-THEN
echo   (MT5 -^> MT4 -^> Yahoo data fallback)
echo ===============================================
echo.

"F:\python-manager-26.0 (1)\python.exe" "%~dp0smc_snapshot_mt5.py"
if %errorlevel% neq 0 (
    echo.
    echo Trying system python...
    python "%~dp0smc_snapshot_mt5.py"
)

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Script failed. See messages above.
) else (
    echo [OK] Snapshot report generated. Opening browser...
)
pause
