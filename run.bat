@echo off
title Discord Nuke Bot
color 0C

echo =======================================
echo      Discord Nuke Bot - Starting
echo =======================================
echo.

REM Check if config.json exists
if not exist "config.json" (
    echo [INFO] config.json not found! Creating template...
    echo.
    (
        echo {
        echo   "token": "YOUR_BOT_TOKEN",
        echo   "prefix": ".!",
        echo   "owner_id": "YOUR_USER_ID_HERE",
        echo   "whitelist": [],
        echo   "language": "en"
        echo }
    ) > config.json
    echo [SUCCESS] Created config.json template!
    echo.
    echo =======================================
    echo  IMPORTANT: Configure your bot now!
    echo =======================================
    echo 1. Open config.json in a text editor
    echo 2. Replace YOUR_BOT_TOKEN with your actual Discord bot token
    echo 3. Replace YOUR_USER_ID_HERE with your Discord user ID
    echo 4. Save the file and run this script again
    echo.
    echo Get your bot token: https://discord.com/developers/applications
    echo Get your user ID: Enable Developer Mode in Discord, right-click your name, Copy ID
    echo =======================================
    echo.
    start notepad config.json
    pause
    exit /b 0
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed!
    echo Please run install.bat first
    pause
    exit /b 1
)

echo Starting bot...
echo.
python main.py

REM If bot crashes, pause so user can see error
if errorlevel 1 (
    echo.
    echo =======================================
    echo Bot stopped with an error!
    echo =======================================
    pause
)
