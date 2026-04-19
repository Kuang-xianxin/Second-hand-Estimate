@echo off
REM =============================================
REM  估二手 - 腾讯云开发一键部署脚本 (Windows)
REM =============================================
setlocal enabledelayedexpansion

echo ======================================
echo   估二手 - 腾讯云部署脚本
echo ======================================

REM ---- 检查依赖 ----
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未安装 Docker，请访问 https://docs.docker.com/get-docker/
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未安装 Node.js，请访问 https://nodejs.org/
    exit /b 1
)

REM ---- 配置区 ----
set BACKEND_PORT=8000
set BACKEND_HOST=127.0.0.1

REM ---- 构建前端 ----
echo.
echo [1/4] 构建前端...
cd /d "%~dp0frontend"
call npm ci
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] 前端构建失败
    exit /b 1
)
echo [OK] 前端构建完成

REM ---- 构建后端 Docker 镜像 ----
echo.
echo [2/4] 构建后端 Docker 镜像...
cd /d "%~dp0"
docker build -f backend\Dockerfile.cloud -t guessr-backend:latest .\backend
if %errorlevel% neq 0 (
    echo [ERROR] Docker 镜像构建失败
    exit /b 1
)
echo [OK] 后端镜像构建完成

REM ---- 启动后端容器 ----
echo.
echo [3/4] 启动后端服务...
docker stop guessr-backend >nul 2>nul
docker rm guessr-backend >nul 2>nul

docker run -d ^
  --name guessr-backend ^
  --restart unless-stopped ^
  -p %BACKEND_PORT%:8000 ^
  -e BACKEND_PORT=8000 ^
  -e FRONTEND_URL=* ^
  -e DEEPSEEK_API_KEY=%DEEPSEEK_API_KEY% ^
  -e QWEN_API_KEY=%QWEN_API_KEY% ^
  -e DOUBAO_API_KEY=%DOUBAO_API_KEY% ^
  -e ADMIN_TOKEN=%ADMIN_TOKEN% ^
  -v "%~dp0backend\guessr.db:/app/guessr.db" ^
  guessr-backend:latest
echo [OK] 后端服务已启动 (端口 %BACKEND_PORT%)

REM ---- 验证服务 ----
echo.
echo [4/4] 验证服务状态...
timeout /t 5 /nobreak >nul
curl -sf http://localhost:%BACKEND_PORT%/health >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] 后端健康检查通过
    echo.
    echo ======================================
    echo   部署完成！
    echo ======================================
    echo 后端地址: http://%BACKEND_HOST%:%BACKEND_PORT%
    echo 前端部署: 请将 frontend\dist 目录上传至腾讯云开发静态托管
    echo.
    echo 首次部署建议:
    echo 1. 登录腾讯云开发控制台
    echo 2. 创建静态网站托管
    echo 3. 上传 dist 目录内容
    echo.
) else (
    echo [ERROR] 后端健康检查失败，请检查日志:
    docker logs guessr-backend
    exit /b 1
)
