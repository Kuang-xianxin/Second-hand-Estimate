@echo off
chcp 65001 >nul 2>&1
title Backend

echo Starting backend...
cd /d "%~dp0backend"
start "Backend" cmd /k "python main.py"

echo Starting cpolar tunnel...
cd /d "%~dp0"
start "Tunnel" cmd /k "cpolar.exe http 8000"
