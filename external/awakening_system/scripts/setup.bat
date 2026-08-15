@echo off
chcp 65001 >nul
setlocal
title One-Click Setup - Awakening System
cd /d "%~dp0"

echo =========================================
echo   Awakening System - One-Click Setup
echo =========================================
echo.

REM --- 1. Locate Python ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    echo Remember to tick "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Using Python: %PY%
%PY% --version
echo.

REM --- 2. Create venv if missing ---
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [STEP] Creating virtual environment .venv ...
    %PY% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
) else (
    echo [OK] venv already exists.
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

REM --- 3. Upgrade pip and install deps ---
echo [STEP] Upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check -q

echo [STEP] Installing requirements ...
"%VENV_PY%" -m pip install -r "%~dp0requirements.txt" --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   [DONE] Setup complete.
echo   You can now double-click:
echo     - run_gold_analysis.bat
echo     - run_wave_analysis.bat
echo =========================================
pause
endlocal
