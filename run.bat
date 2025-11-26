@echo off
echo Starting Remote Keyboard...

if not exist "venv" (
    echo Virtual environment not found. Running setup...
    call setup.bat
)

call venv\Scripts\activate
python gui_app.py

if %errorlevel% neq 0 (
    echo Application crashed or closed with error.
    pause
)
