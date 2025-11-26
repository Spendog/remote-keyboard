@echo off
echo Updating Remote Keyboard...

git pull origin main

echo Updating dependencies...
if exist "venv" (
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call setup.bat
)

echo Update Complete!
pause
