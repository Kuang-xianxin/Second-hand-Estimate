@echo off
REM 启动内网穿透脚本
REM 需要先在 https://ngrok.com 免费注册并获取 authtoken

set NGROK_PATH=C:\Users\QQ276\AppData\Local\Temp\ngrok\ngrok.exe
set FRONTEND_PORT=5173
set BACKEND_PORT=8000

REM 检查 ngrok 是否存在
if not exist "%NGROK_PATH%" (
    echo ngrok not found, downloading...
    powershell -Command "Invoke-WebRequest -Uri 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip' -OutFile '$env:TEMP\ngrok.zip' -UseBasicParsing"
    powershell -Command "Expand-Archive -Path '$env:TEMP\ngrok.zip' -DestinationPath '$env:TEMP\ngrok' -Force"
)

REM 启动前端穿透 (5173)
start "ngrok-frontend" cmd /k "cd /d C:\Users\QQ276\AppData\Local\Temp\ngrok && ngrok http %FRONTEND_PORT% --log=stdout"

REM 等待 ngrok 启动
timeout /t 5 /nobreak > nul

REM 获取前端公网地址
for /f "tokens=*" %%i in ('curl -s http://localhost:4040/api/tunnels 2^>nul ^| findstr /i "public_url" ^| head -1') do set FRONTEND_URL=%%i
echo Frontend URL: %FRONTEND_URL%

REM 启动后端穿透 (8000)
start "ngrok-backend" cmd /k "cd /d C:\Users\QQ276\AppData\Local\Temp\ngrok && ngrok http %BACKEND_PORT% --log=stdout"

timeout /t 5 /nobreak > nul

REM 获取后端公网地址
for /f "tokens=*" %%i in ('curl -s http://localhost:4040/api/tunnels 2^>nul ^| findstr /i "public_url" ^| head -1') do set BACKEND_URL=%%i
echo Backend URL: %BACKEND_URL%

echo.
echo ========================================
echo 内网穿透完成！
echo 前端地址: %FRONTEND_URL%
echo 后端地址: %BACKEND_URL%
echo ========================================
echo 按任意键关闭此窗口...
pause > nul
