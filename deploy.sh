#!/bin/bash
# 部署脚本 - 在服务器上执行
set -e

echo "=== 1. 构建前端 ==="
cd frontend
npm install
npm run build
cd ..

echo "=== 2. 启动 Docker 服务 ==="
docker-compose down 2>/dev/null || true
docker-compose build --no-cache
docker-compose up -d

echo "=== 3. 等待后端启动 ==="
sleep 5

echo "=== 部署完成 ==="
echo "前端: http://你的服务器IP"
echo "后端API: http://你的服务器IP:8000"
echo "API文档: http://你的服务器IP:8000/docs"
