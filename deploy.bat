@echo off
rem 部署脚本 - Windows
echo === 1. 构建前端 ===
cd frontend
call npm install
call npm run build
cd ..

echo === 2. 启动 Docker 服务 ===
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo === 部署完成 ===
echo 前端: http://localhost
echo 后端API: http://localhost:8000
echo API文档: http://localhost:8000/docs
pause
