# 估二手 - AI 助手项目概览

## 项目是什么

闲鱼 CCD 相机（及其他二手商品）估价工具。输入关键词 → 自动抓取闲鱼真实挂牌数据 → 统计 + 多模型 AI 分析 → 给出估价区间、成色分布、捡漏推荐。

## 技术栈

- **前端**: Vue 3 + TypeScript + Vite + Axios + Vue Router，SSE 流式输出
- **后端**: FastAPI + SQLAlchemy 2.0 async + **PostgreSQL** + Redis + Playwright（闲鱼爬虫）
- **缓存**: Redis（L1 热点缓存）+ PostgreSQL（L2 主力数据库）
- **AI 估价**: 兼容 DeepSeek / 通义千问 / 豆包，多模型并发
- **调度**: APScheduler，每 1.5 小时后台全量爬取 + 缓存更新
- **部署**: Docker 容器化，Nginx 反向代理，腾讯云服务器

## 目录结构

```
frontend/                   # Vue 3 前端
  src/views/HomeView.vue   # 估价主页面（SSE 流式 + 条件捡漏）
  src/views/HistoryView.vue # 估价历史
  src/views/BargainView.vue # 捡漏广场（全局捡漏）
  src/api/index.ts         # API 调用封装
  src/types/index.ts       # TypeScript 类型定义
  vite.config.js           # 开发代理（/api -> localhost:8000）

backend/
  app/
    api/
      valuate.py           # /api/valuate（SSE）、/api/history
      cache_api.py         # /api/valuate/cached、/api/cache/status、/api/bargains/*
      stats_api.py         # /api/crawl/progress、/api/stats/overview
      crawler/xianyu.py      # 闲鱼数据采集（DrissionPage）
    models/
      database.py          # SQLAlchemy async 连接（PostgreSQL + SQLite 降级）
      redis_client.py      # Redis 异步客户端
      cache.py             # CCDPriceCache 模型
      global_bargain.py     # GlobalBargain 模型
      price_history.py      # PriceHistory 模型
      crawl_status.py       # CrawlStatus 模型
      item.py              # CrawledItem、ValuationRecord、BargainAlert
    services/
      pricing.py           # 基准价计算、IQR 去极值
      llm.py              # 多模型 AI 并发调用
      bargain.py           # 条件捡漏识别逻辑
      cache.py            # 三级缓存读写（L1 Redis / L2 PG / L3 历史）
      redis_lock.py       # 分布式锁（定时任务防重）
      crawl_worker.py      # 批量爬取逻辑（并发控制）
      bargain_detector.py  # 全局捡漏检测算法
      cache_updater.py     # 缓存批量更新 + L1 预热
      ccd_keywords.py      # 全量 CCD 型号关键词列表（~2003 个，覆盖 676 型号）
      xd_card_models.py    # XD 卡相机型号数据库
    scheduler.py           # APScheduler 定时任务（每 1.5 小时全量爬取）
  main.py                  # FastAPI 入口
```

## 三级缓存架构

```
用户请求 ──▶ L1 Redis（< 1ms）──▶ L2 PostgreSQL（5-20ms）──▶ L3 历史趋势（20-50ms）
```

- **L1 Redis**: 热点数据缓存，TTL 1.5 小时，跨 Worker 共享，进程重启不丢
- **L2 PostgreSQL**: 主力数据库，ccd_price_cache 表存储 ~852 个型号的完整估价数据
- **L3**: 价格历史趋势（price_history 表），给用户提供趋势参考

## 两种捡漏机制


|      | 条件捡漏           | 全局捡漏（捡漏广场）       |
| ---- | -------------- | ---------------- |
| 触发   | 用户搜索具体型号       | 后台定时任务（每 1.5 小时） |
| 数据来源 | 当前搜索型号的爬取结果    | 全部 CCD 型号的爬取结果   |
| 显示位置 | 估价结果页底部        | 独立的「捡漏广场」Tab     |
| 显示规则 | **该型号有捡漏才显示**  | 始终显示，按利润降序       |
| 数据表  | bargain_alerts | global_bargains  |


## API 速查


| 方法    | 路径                           | 说明                  |
| ----- | ---------------------------- | ------------------- |
| POST  | `/api/valuate/stream`        | SSE 流式估价（实时爬取）      |
| GET   | `/api/valuate/cached`        | 缓存优先估价（L1/L2 毫秒级返回） |
| GET   | `/api/crawl/progress`        | 当前爬取实时进度（Redis）      |
| GET   | `/api/stats/overview`         | 系统统计概览              |
| GET   | `/api/cache/status`          | 缓存系统状态              |
| GET   | `/api/history`               | 估价历史列表              |
| GET   | `/api/history/{id}`          | 单条估价详情              |
| GET   | `/api/bargains`              | 条件捡漏提醒列表            |
| GET   | `/api/bargains/by-keyword`   | 按型号查询条件捡漏           |
| GET   | `/api/bargains/global`       | 全局捡漏列表（捡漏广场）        |
| GET   | `/api/bargains/global/count` | 全局捡漏总数              |
| PATCH | `/api/bargains/{id}/read`    | 标记已读                |


## 关键工作流程

1. **估价流程（缓存命中）**: 用户输入 → 查 L1/L2 缓存 → < 500ms 返回，无 LLM 调用
2. **估价流程（缓存未命中）**: 用户输入 → 实时爬取 → 数据清洗 → 多模型 AI 估价 → SSE 返回（45-90 秒）
3. **后台定时任务**: 每 1.5 小时全量爬取（需 `crawl_enabled=True`，开发默认关闭）→ 算法估价 → 全局捡漏检测 → 缓存更新 → L1 预热
3a. **初次部署**: 启动时仅在 `crawl_enabled=True` 且 `initial_crawl_enabled=True` 时，检测 `ccd_price_cache` 表是否为空，为空则触发全量爬取。两项开关开发环境默认均为 `False`，避免本地启动误触发全量爬取。
4. **捡漏识别**: 价格低于基准价 30%+ 且绝对利润 ≥ 80 元自动标记
5. **XD 卡专项**: 富士/奥林巴斯 xD 卡机型捆绑价值单独计算，MASD-1 卡套兼容提示

## 开发注意事项

- 前端开发服务器端口 `5173`，后端 `8000`，Vite 代理 `/api` 到后端
- 后端 `.env` 需要配置：AI 模型 API Key、数据库连接字符串、Redis 连接字符串
- 数据库：PostgreSQL（生产）+ SQLite 降级（开发），连接字符串在 `config.py`
- `qwen_result` 列实际存储了 qwen+doubao 两个模型结果（doubao 嵌套在 qwen_result JSON 内部）
- `valuation_records.openai_result` 为历史遗留字段，新代码不写入
- 调度间隔由 `config.crawl_interval_seconds` 控制（默认 5400 秒 = 1.5 小时），scheduler.py 使用此配置
- 爬虫依赖 Playwright + 闲鱼登录 Cookie，无 Cookie 时爬虫返回 401/429，`crawl_worker.CrawlResult` 会标记 `login_required=True` / `risk_detected=True`，`BatchCrawlReport` 汇总 `login_required_count` / `risk_detected_count`
- `XianyuCrawler.get_last_debug_summary()` 可获取最近一次爬取的调试摘要（含 `login_page_hint`、`risk_page_hint` 等字段）
- `crawl_worker.crawl_single_keyword()` 的并发控制：`asyncio.Semaphore` 包裹了 `sleep + crawler.search()`，确保并发数内任务全程串行化，不会所有任务同时 sleep 后同时发起请求
- 前端修改后执行 `npm run build` 构建产物到 `frontend/dist/`
- `XianyuItem` 数据类包含 `query_keyword` 字段，用于将商品回溯到搜索关键词（scheduler.py / cache_updater.py / bargain_detector.py 依赖此字段）
- `trigger_crawl.py` 支持金丝雀测试参数：`--brand`、`--keyword`、`--max-keywords`、`--limit`、`--max-pages`、`--concurrency`、`--dry-run`
- `cache_updater.write_crawled_items()` 将爬取的商品批量写入 `crawled_items` 表（按 `item_id` upsert），scheduler.py 和 trigger_crawl.py 在爬取完成后自动调用

## 配置项速查

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `crawl_interval_seconds` | 5400 | 定时爬取间隔（秒） |
| `crawl_enabled` | false | 是否启用定时爬取（开发默认关闭，生产 .env 设为 true） |
| `initial_crawl_enabled` | false | 首次启动是否触发全量爬取（需同时开启 crawl_enabled） |
| `max_items_per_query` | 200 | 每关键词最大商品数 |
| `max_pages_per_query` | 2 | 每关键词最大翻页数（开发默认 2 页防封） |
| `crawl_concurrency` | 1 | 并发爬取数（开发默认单并发防封） |
| `crawl_batch_size` | 50 | 每批关键词数 |
| `crawl_dev_keyword_limit` | 0 | 开发模式关键词上限（0=不限制，生产 .env 设 0 全量） |
| `bargain_threshold` | 120.0 | 捡漏最低利润阈值（元） |

## 数据库表


| 表名                | 用途                |
| ----------------- | ----------------- |
| crawled_items     | 爬取的原始商品数据         |
| valuation_records | 估价记录              |
| bargain_alerts    | 条件捡漏提醒            |
| ccd_price_cache   | CCD 型号价格缓存（L2 缓存） |
| global_bargains   | 全局捡漏（捡漏广场）        |
| price_history     | 价格历史趋势（L3 缓存）     |
| crawl_status      | 爬取任务状态            |


## 环境

- 开发环境: Windows (PowerShell)
- 服务器: 腾讯云 Linux（PostgreSQL + Redis + PgBouncer）
- Git 分支: main
