@echo off
echo ========================================================
echo   MT5 Trader Workbench - Hardened Build Script
echo ========================================================
echo.
echo Starting hardened packaging process...
echo Pipeline: Frontend Build ==^> Pyarmor Backend ==^> Verify ==^> Windows Installer (.exe)
echo Please wait, this may take a few minutes.
echo.

call npm run package:win:hardened

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Packaging failed! Please check the logs above.
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Hardened packaging completed successfully!
echo The final installer (.exe) is located in the "dist" directory.
echo.
pause
