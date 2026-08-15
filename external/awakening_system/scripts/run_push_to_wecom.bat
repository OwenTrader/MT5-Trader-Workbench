@echo off
title Push Report to WeCom
echo ===============================================
echo   Push Latest Report to WeCom Group Bot
echo   (Markdown summary + HTML file attachment)
echo ===============================================
echo.

"F:\python-manager-26.0 (1)\python.exe" "%~dp0push_to_wecom.py" %*
if %errorlevel% neq 0 (
    echo.
    echo Trying system python...
    python "%~dp0push_to_wecom.py" %*
)

echo.
pause
