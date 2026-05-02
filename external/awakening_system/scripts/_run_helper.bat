@echo off
REM Internal helper: resolves a usable python interpreter into %PYEXE%
REM Auto-runs setup.bat if venv is missing.

set "PYEXE="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYEXE=%~dp0.venv\Scripts\python.exe"
    goto :eof
)

echo [INFO] First-time use detected. Running setup ...
call "%~dp0setup.bat"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYEXE=%~dp0.venv\Scripts\python.exe"
    goto :eof
)

REM Fallback to system python
where py >nul 2>nul && set "PYEXE=py -3" && goto :eof
where python >nul 2>nul && set "PYEXE=python" && goto :eof

echo [ERROR] No Python available. Install Python 3.9+ and re-run setup.bat
exit /b 1
