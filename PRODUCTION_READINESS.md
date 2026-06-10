# 估二手生产上线手册

## 当前上线门槛

以下项目全部完成后，才可以对公网开放：

- [x] 已轮换服务器数据库密码、添加 ADMIN_TOKEN。⚠️ DeepSeek/通义 API Key 需手动去平台重新生成（曾出现在 Git 历史中）。
- [ ] 域名已启用 HTTPS（certbot 已安装，Nginx HTTPS 模板已就绪，等待 DuckDNS 域名 `secondhandestimate.duckdns.org` 解析到 119.91.117.232）。
- [x] PostgreSQL 备份恢复演练通过（16MB dump → restore → 验证 → 清理）。
- [x] 前端构建通过（`vite build --mode production`，96 modules），已部署到 `/var/www/guessr/`。
- [x] Nginx 配置语法检查通过（`nginx -t`），前端正常加载。
- [x] 后端测试：159 passed，0 failed（`pytest -q`）。
- [ ] Docker Compose 未安装（服务器用 systemd 管理服务，替代方案已验证可行）。
- [ ] 真实估价金丝雀：缓存端点 HTTP 200（当前缓存为空，等待调度器填充）。已修复 `import os` bug（调度器之前静默失败）。
- [ ] 独立爬虫稳定轮转成功：生产 Web 进程不再运行 Playwright，`guessr-crawl@sweep.service` 单型号任务成功完成并写入数据库。
- [x] 监控告警：服务器 cron 已配置（每 5 分钟检查磁盘/内存/服务/爬虫登录态），watchdog 模式（静默=正常）。
- [ ] 闲鱼登录态：当前会话已触发风控；保持静默冷却，冷却结束后由单型号 sweep 请求验证，禁止额外真实金丝雀。
- [ ] 服务器连通性：2026-06-09 公网健康检查返回空响应，SSH 在密钥交换前被关闭；需先从腾讯云控制台恢复实例/SSH。

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

## 独立爬虫 Worker

生产环境必须设置：

```bash
CRAWL_ENABLED=true
CRAWL_SCHEDULER_MODE=external
CRAWL_CANARY_ENABLED=false
CRAWL_STOP_ON_RISK=true
CRAWL_CONCURRENCY=1
CRAWL_CONCURRENCY_MAX=1
CRAWL_STABILITY_MODE=true
CRAWL_KEYWORDS_PER_RUN=1
CRAWL_MIN_INTERVAL_SECONDS=180
CRAWL_COVERAGE_TARGET_SECONDS=172800
CRAWL_RISK_COOLDOWN_SECONDS=604800
MAX_ITEMS_PER_QUERY_T0=20
MAX_PAGES_PER_QUERY=1
```

安装 systemd service 和 timer：

```bash
cd /opt/guessr
bash deploy/install-crawl-timers.sh
systemctl list-timers 'guessr-crawl-*'
journalctl -u 'guessr-crawl@sweep.service' -n 100 --no-pager
```

不要使用高频完整爬虫或并行 tier timer。稳定模式把 673 个去重型号拆成独立短命进程，
每次只访问一个型号。`guessr-crawl-sweep.timer` 在上一个 worker 退出后再调度，
Redis 全局门禁强制至少间隔 180 秒，全局分布式锁防止任何层级重叠。
单型号 worker 硬超时为 3 分钟；无失败冷却时，加上下一次调度等待，一轮尝试上限约 45 小时。
普通网络或内部故障会先冷却 30 分钟，再重试同一型号；空结果会保留旧缓存并继续轮转。

稳定模式不运行额外 canary，因为 canary 会让每轮请求量翻倍；当前单型号请求本身就是探针。
登录失效、`RGV587` 或其他风控信号会立刻熔断并进入至少 7 天冷却。此时安全优先，
48 小时更新目标会暂停，不能通过继续重试来强行满足。

验证数据库确实更新：

```bash
sudo -u postgres psql -d ccd_db -c \
  "SELECT batch_id,status,success_count,fail_count,total_items,finished_at,error_message FROM crawl_status ORDER BY started_at DESC LIMIT 5;"
sudo -u postgres psql -d ccd_db -c \
  "SELECT count(*) AS total,max(crawled_at) AS latest FROM crawled_items;"
sudo -u postgres psql -d ccd_db -c \
  "SELECT count(*) AS total,max(crawled_at) AS latest FROM ccd_price_cache;"
sudo -u postgres psql -d ccd_db -c \
  "SELECT count(*) AS stale_over_48h FROM ccd_price_cache WHERE crawled_at < now() - interval '48 hours';"
```

网页系统状态面板还会显示 673 个标准型号中，48 小时内成功更新和过期/未覆盖的数量。
上游没有挂牌数据、登录失效或风控期间无法保证成功写入，但失败批次不会覆盖旧缓存。

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
