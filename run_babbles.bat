@echo off
title Babbles Speech App Launcher
cls

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ===================================================
    echo             BABBLES SPEECH-TO-TEXT APP             
    echo ===================================================
    echo [*] Running with Administrator privileges.
    echo [*] Launching application in virtual environment...
    echo.
    
    cd /d "%~dp0"
    .venv\Scripts\python.exe main.py
    pause
) else (
    echo [*] Babbles requires Administrator privileges to monitor global hotkeys.
    echo [*] Requesting elevation...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)
