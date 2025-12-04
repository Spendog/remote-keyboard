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
echo ===================================================
echo      REMOTE KEYBOARD - REPAIR & RESET TOOL
echo ===================================================
echo.
echo 1. Stopping all running instances...
taskkill /F /IM python.exe /T >nul 2>&1
:: taskkill /F /IM cmd.exe /T >nul 2>&1  <-- This was killing the repair script itself!

echo.
echo 2. Refreshing code from GitHub...
git fetch --all
git reset --hard origin/main

echo.
echo 3. Checking critical dependencies...
if not exist "static\socket.io.js" (
    echo [WARNING] socket.io.js missing! Attempting to restore...
    if exist "..\remote-keyboard-broken\static\socket.io.js" (
        copy "..\remote-keyboard-broken\static\socket.io.js" "static\socket.io.js"
        echo [SUCCESS] Restored from backup.
    ) else (
        echo [ERROR] Could not find backup socket.io.js!
        echo Please download it manually or check internet connection.
    )
) else (
    echo [OK] socket.io.js found.
)

echo.
echo 4. Restarting Application...
echo.
start run.bat
echo Done.
pause
exit
