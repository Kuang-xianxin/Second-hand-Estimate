#!/bin/bash
# ==============================================
# 估二手 - 腾讯云开发一键部署脚本（Linux/macOS）
# ==============================================

set -e

echo "====================================="
echo "  估二手 - 腾讯云部署脚本"
echo "====================================="

# ---- 检查依赖 ----
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    echo "   请访问 https://docs.docker.com/get-docker/ 安装"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ 错误: 未安装 Node.js/npm"
    echo "   请访问 https://nodejs.org/ 安装"
    exit 1
fi

# ---- 配置区（请根据实际情况修改） ----
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_URL=${FRONTEND_URL:-*}
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-""}
QWEN_API_KEY=${QWEN_API_KEY:-""}
DOUBAO_API_KEY=${DOUBAO_API_KEY:-""}
ADMIN_TOKEN=${ADMIN_TOKEN:-$(openssl rand -hex 32)}
BACKEND_HOST=${BACKEND_HOST:-"127.0.0.1"}

# ---- 构建前端 ----
echo ""
echo "📦 [1/4] 构建前端..."
cd "$(dirname "$0")/frontend"
npm ci
npm run build
echo "✅ 前端构建完成"

# ---- 构建后端 Docker 镜像 ----
echo ""
echo "🐳 [2/4] 构建后端 Docker 镜像..."
cd "$(dirname "$0")"
docker build -f backend/Dockerfile.cloud -t guessr-backend:latest ./backend
echo "✅ 后端镜像构建完成"

# ---- 启动后端容器 ----
echo ""
echo "🚀 [3/4] 启动后端服务..."
docker stop guessr-backend 2>/dev/null || true
docker rm guessr-backend 2>/dev/null || true

docker run -d \
  --name guessr-backend \
  --restart unless-stopped \
  -p ${BACKEND_PORT}:8000 \
  -e DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY}" \
  -e QWEN_API_KEY="${QWEN_API_KEY}" \
  -e DOUBAO_API_KEY="${DOUBAO_API_KEY}" \
  -e ADMIN_TOKEN="${ADMIN_TOKEN}" \
  -e BACKEND_PORT=8000 \
  -e FRONTEND_URL="${FRONTEND_URL}" \
  -v "$(pwd)/backend/guessr.db:/app/guessr.db" \
  guessr-backend:latest

echo "✅ 后端服务已启动 (端口 ${BACKEND_PORT})"

# ---- 验证服务 ----
echo ""
echo "🔍 [4/4] 验证服务状态..."
sleep 5
if curl -sf http://localhost:${BACKEND_PORT}/health > /dev/null; then
    echo "✅ 后端健康检查通过"
    echo ""
    echo "====================================="
    echo "  🎉 部署完成！"
    echo "====================================="
    echo "后端地址: http://${BACKEND_HOST}:${BACKEND_PORT}"
    echo "前端部署: 请将 frontend/dist 目录上传至腾讯云开发静态托管"
    echo ""
    echo "首次部署建议:"
    echo "1. 登录腾讯云开发控制台"
    echo "2. 创建静态网站托管"
    echo "3. 上传 dist 目录内容"
    echo "4. 在环境变量中配置 BACKEND_URL 为后端地址"
    echo ""
    echo "后端管理令牌: ${ADMIN_TOKEN}"
    echo "（请妥善保存，修改 .env 后重启容器生效）"
else
    echo "❌ 后端健康检查失败，请检查日志:"
    docker logs guessr-backend
    exit 1
fi
