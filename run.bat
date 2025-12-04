@echo off
:: Check for Admin rights
NET SESSION >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Running as Administrator.
) else (
    echo [INFO] Requesting Administrator privileges...
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"

echo Starting Remote Keyboard...

if not exist "venv" (
    echo Virtual environment not found. Running setup...
    call setup.bat
)

call venv\Scripts\activate

echo Checking for existing instances...
powershell -Command "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*gui_app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Starting GUI App...
python gui_app.py

if %errorlevel% neq 0 (
    echo Application crashed or closed with error.
    pause
)
