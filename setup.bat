@echo off
echo ========================================================
echo                 Babbles Project Setup
echo ========================================================
echo.

echo [1/4] Creating virtual environment (.venv)...
python -m venv .venv
if %errorlevel% neq 0 (
    echo Failed to create virtual environment. Please ensure Python is installed and added to PATH.
    pause
    exit /b %errorlevel%
)
echo.

echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat
echo.

echo [3/4] Upgrading pip and installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies. Please check the error above.
    pause
    exit /b %errorlevel%
)
echo.

echo [4/4] Setup Complete!
echo.
echo ========================================================
echo NOTE: Babbles requires Administrator privileges to hook 
echo global hotkeys accurately. If hotkeys don't respond, 
echo close the app and run it again as Administrator.
echo ========================================================
echo.
echo Setup is now complete. You can close this window.
echo To run the application, please use: run_babbles.bat
echo.

pause
