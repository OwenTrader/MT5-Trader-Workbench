@echo off
echo ========================================================
echo   MT5 Trader Workbench - Standard Build Script
echo ========================================================
echo.
echo Starting standard packaging process...
echo Pipeline: Frontend Build ==^> PyInstaller Backend ==^> Verify ==^> Windows Installer (.exe)
echo Please wait, this may take a few minutes.
echo.

call npm run package:win

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Packaging failed! Please check the logs above.
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Standard packaging completed successfully!
echo The final installer (.exe) is located in the "dist" directory.
echo.
pause
