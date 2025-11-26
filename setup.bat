@echo off
echo Setting up Remote Keyboard Environment...

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing via Winget...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo Failed to install Python. Please install manually.
        pause
        exit /b 1
    )
    echo Python installed. Please restart this script to pick up the new PATH.
    pause
    exit /b 0
)

REM Create Virtual Environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Install Dependencies
echo Installing dependencies...
call venv\Scripts\activate
pip install -r requirements.txt

echo Setup Complete!
pause
