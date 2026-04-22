@echo off
chcp 65001 >nul 2>&1
title Deploy Frontend

setlocal enabledelayedexpansion

REM Read envId from cloudbaserc.json
set "ENV_ID="
if exist "%~dp0frontend\cloudbaserc.json" (
    for /f "tokens=2 delims=:" %%a in ('findstr /C:"envId" "%~dp0frontend\cloudbaserc.json"') do (
        set "RAW=%%a"
        set "RAW=!RAW:,=!"
        set "RAW=!RAW: =!"
        set "RAW=!RAW:"=!"
        if not "!RAW!"=="{{envId}}" (
            set "ENV_ID=!RAW!"
        )
    )
)

if "%ENV_ID%"=="" (
    echo Tencent Cloud env ID not found in cloudbaserc.json
    echo Get it from: https://console.cloud.tencent.com/tcb
    set /p ENV_ID="Enter env ID: "
    if "!ENV_ID!"=="" exit /b 1
)

set /p BACKEND_URL="Backend URL (https://xxxx.vip.cpolar.cn): "
if "%BACKEND_URL%"=="" exit /b 1
if "%BACKEND_URL:~-1%"=="/" set "BACKEND_URL=%BACKEND_URL:~0,-1%"

echo Updating cloudbaserc.json envId...
powershell -Command "(Get-Content '%~dp0frontend\cloudbaserc.json') -replace '\"envId\": \"{{envId}}\"', ('\"envId\": \"' + '%ENV_ID%' + '\"') | Set-Content '%~dp0frontend\cloudbaserc.json'"

echo Updating .env.production...
(echo VITE_API_BASE_URL=%BACKEND_URL%) > "%~dp0frontend\.env.production"

echo Building frontend...
cd /d "%~dp0frontend"
call npm run build
if %errorlevel% neq 0 goto :error

echo Deploying to Tencent CloudBase...
tcb hosting deploy "%~dp0frontend\dist" -e %ENV_ID%
if %errorlevel% neq 0 goto :error

echo.
echo Done! Backend: %BACKEND_URL%
echo Do NOT close cpolar window!
pause
exit /b 0

:error
echo.
echo Deploy failed!
pause
