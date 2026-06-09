# 估二手生产上线手册

## 当前上线门槛

以下项目全部完成后，才可以对公网开放：

- 已轮换曾出现在 Git 历史中的服务器密码、DeepSeek、通义和豆包密钥。
- 域名已启用 HTTPS，HTTP 自动跳转 HTTPS，TLS 层启用 HSTS。
- PostgreSQL 和 Redis 均为独立持久化服务，已执行一次备份恢复演练。
- 闲鱼登录态使用专用低权限账号，并确认数据采集频率符合平台规则。
- `docker compose`、Nginx、后端测试、前端构建和真实估价金丝雀全部通过。
- 已配置日志采集、磁盘/内存/5xx 告警和爬虫登录失效告警。

## 生产环境变量

在服务器项目根目录执行：

```bash
cp .env.cloud.example .env.cloud
chmod 600 .env.cloud
```

必须修改：

- `ADMIN_TOKEN`：至少 32 位随机值。
- `DATABASE_URL`：生产 PostgreSQL/PgBouncer 地址。
- `REDIS_URL`：生产 Redis 地址。
- `FRONTEND_URL`、`CORS_ORIGINS`、`TRUSTED_HOSTS`：真实 HTTPS 域名。
- AI 模型密钥。

仅在 SMTP 配置并验证可用后，才把 `PASSWORD_RESET_ENABLED` 设为 `true`。

## 构建与验证

```bash
# 后端
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q

# 前端
cd ../frontend
npm ci
npm run build
npm audit --omit=dev --audit-level=high

# 容器
cd ..
docker compose --env-file .env.cloud -f docker-compose.cloud.yml config
docker compose --env-file .env.cloud -f docker-compose.cloud.yml build
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready

# Nginx
sudo nginx -t
sudo systemctl reload nginx
```

`/health` 只表示进程存活；`/ready` 会检查 PostgreSQL 和 Redis，只有两者都正常才返回 200。

## HTTPS

先用 HTTP 配置完成 ACME 校验，再申请证书并切换到 HTTPS 示例：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --webroot -w /var/www/certbot -d secondhandestimate.duckdns.org
sudo cp nginx.https.conf.example /etc/nginx/sites-available/guessr
sudo nginx -t && sudo systemctl reload nginx
sudo certbot renew --dry-run
```

## 数据备份与恢复演练

```bash
pg_dump --format=custom --file=guessr-$(date +%F).dump "$DATABASE_URL"
createdb guessr_restore_test
pg_restore --clean --if-exists --dbname=guessr_restore_test guessr-YYYY-MM-DD.dump
```

备份文件应同步到另一台机器或对象存储，不能只放在应用服务器。

## 发布与回滚

1. 在 CI 中通过秘密扫描、后端测试、前端构建和依赖审计。
2. 先部署到预发布环境，运行缓存查询和一个低频实时估价金丝雀。
3. 生产发布前记录当前镜像标签和数据库备份。
4. `/ready`、首页、登录、缓存估价、实时估价、历史记录、捡漏广场全部通过后再切流量。
5. 发布失败时恢复上一镜像；涉及数据库结构变更时按迁移脚本回滚。

## 尚需完成的结构性工作

- 使用 Alembic 替换启动时自动 `ALTER TABLE`，让数据库迁移可审计、可回滚。
- 增加结构化安全审计日志和异常登录告警；当前已有应用层与 Nginx 两层限流。
- 引入 PostgreSQL 自动备份、监控和告警。
- 增加 API 集成测试和浏览器端到端测试。
- 固定 Python 依赖版本并定期执行依赖漏洞扫描。
