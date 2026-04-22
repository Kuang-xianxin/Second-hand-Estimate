@echo off
chcp 65001 >nul 2>&1
title Stop Service

taskkill /f /im cpolar.exe >nul 2>&1
echo cpolar stopped

taskkill /f /fi "WINDOWTITLE eq Backend" >nul 2>&1
echo Backend stopped

echo.
echo All services stopped.
pause
