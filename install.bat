@echo off
title Discord Nuke Bot - Installation
color 0A

echo =======================================
echo    Discord Nuke Bot - Installation
echo =======================================
echo.

echo [1/3] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

REM Check Python version (must be 3.10+)
for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Extract major and minor version
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

REM Check if version is at least 3.10
if %PYTHON_MAJOR% LSS 3 (
    echo [ERROR] Python 3.10+ is required! Current version: %PYTHON_VERSION%
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)
if %PYTHON_MAJOR% EQU 3 if %PYTHON_MINOR% LSS 10 (
    echo [ERROR] Python 3.10+ is required! Current version: %PYTHON_VERSION%
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)
echo [OK] Python version is compatible
echo.

echo [2/3] Installing required packages...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements!
    pause
    exit /b 1
)
echo.

echo [3/3] Installation complete!
echo.
echo =======================================
echo  Setup Instructions:
echo =======================================
echo 1. Edit config.json with your bot token
echo 2. Add your Discord user ID to owner_id
echo 3. Run run.bat to start the bot
echo =======================================
echo.
pause
