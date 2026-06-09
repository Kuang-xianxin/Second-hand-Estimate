# 估二手

闲鱼二手 CCD 相机估价与捡漏平台。用户输入型号后，系统优先读取价格缓存；缓存未命中时执行实时采集、样本清洗、统计估价和多模型 AI 分析。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Axios、Vue Router、SSE
- 后端：FastAPI、SQLAlchemy async、PostgreSQL、Redis、Playwright
- 后台任务：开发环境 APScheduler；生产环境 systemd 独立 worker + Redis 分布式锁
- 部署：Docker Compose、Nginx、GitHub Actions

## 本地开发

```powershell
# 后端
cd backend
python -m pip install -r requirements-dev.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# 前端
cd ..\frontend
npm ci
npm run dev
```

打开 `http://127.0.0.1:5173`。

## 验证

```powershell
cd backend
python -m pytest -q

cd ..\frontend
npm run build
npm audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
```

## 生产部署

生产上线前必须阅读 [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)。生产配置会强制检查 PostgreSQL、Redis、管理员令牌、站内鉴权、CORS 和可信 Host；配置不安全时后端拒绝启动。

生产爬虫使用独立短命进程，不在 Uvicorn Web 进程内运行 Playwright：

```bash
cd /opt/guessr
bash deploy/install-crawl-timers.sh
systemctl list-timers 'guessr-crawl-*'
journalctl -u 'guessr-crawl@t0.service' -n 100 --no-pager
```

安装脚本会先运行一个关键词的真实金丝雀。只有金丝雀成功写入
`crawl_status` 后，才会启用完整 T0 定时任务。

```bash
cp .env.cloud.example .env.cloud
docker compose --env-file .env.cloud -f docker-compose.cloud.yml config
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d --build
```

- `/health`：进程存活检查
- `/ready`：PostgreSQL 与 Redis 就绪检查
- `nginx.conf`：HTTP 或上游 TLS 终止场景
- `nginx.https.conf.example`：直接由 Nginx 提供 HTTPS 的示例

## 安全说明

不要提交 `.env`、闲鱼登录态、服务器地址、密码或 API 密钥。仓库曾包含旧部署凭据，正式上线前必须轮换相关服务器密码和第三方 API 密钥，并清理 Git 历史中的秘密。
