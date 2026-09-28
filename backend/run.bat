@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -3.11 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 exit /b 1

    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 exit /b 1

    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" "scripts\run_backend.py"
