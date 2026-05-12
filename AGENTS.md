# 估二手 - AI 助手项目概览

## 项目是什么

闲鱼 CCD 相机（及其他二手商品）估价工具。输入关键词 → 自动抓取闲鱼真实挂牌数据 → 统计 + 多模型 AI 分析 → 给出估价区间、成色分布、捡漏推荐。

## 技术栈

- **前端**: Vue 3 + TypeScript + Vite + Axios + Vue Router，SSR 流式输出（SSE）
- **后端**: FastAPI + SQLAlchemy (async) + SQLite + Playwright（闲鱼爬虫）

- **AI 估价**: 兼容 DeepSeek / 通义千问 / OpenAI，多模型并发
- **调度**: APScheduler，后台定时爬取 + 价格缓存
- **部署**: Docker 容器化，Nginx 反向代理，腾讯云服务器

## 目录结构

```
frontend/                   # Vue 3 前端
  src/views/HomeView.vue   # 估价主页面（SSE 流式展示）
  src/views/HistoryView.vue # 估价历史
  src/views/BargainView.vue # 捡漏商品
  src/api/index.ts         # API 调用封装
  src/types/index.ts       # TypeScript 类型定义
  vite.config.js           # 开发代理（/api -> localhost:8000）

backend/
  app/
    api/valuate.py         # /api/valuate（SSE）、/api/history、/api/bargains
    crawler/xianyu.py      # 闲鱼数据采集（DrissionPage）
    models/                # SQLAlchemy 模型
    services/
      pricing.py           # 基准价计算、异常值过滤
      llm.py               # 多模型 AI 并发调用
      bargain.py           # 捡漏识别逻辑
      xd_card_models.py    # XD 卡相机型号数据库
  main.py                  # FastAPI 入口
```

## 关键工作流程

1. **估价流程**: 用户输入关键词 → 后端爬取闲鱼数据 → 数据清洗 → 多模型 AI 并发估价 → SSE 流式返回结果
2. **估价流程（新版，后台缓存）**: 用户输入关键词 → 从价格缓存库直接查询 → 毫秒级返回结果，同时后台静默更新缓存
3. **后台定时同步**: 每 1.5 小时自动爬取全部 CCD 型号闲鱼数据 → 更新价格缓存 → 自动识别捡漏商品
4. **捡漏识别**: 价格低于基准价 30%+ 且质量评分高的商品自动标记
5. **XD 卡专项**: 富士 XD 卡相机型号关联卡价值评估（参考 CCD相机内存卡专家技能）

## API 速查

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/valuate` | SSE 流式估价 |
| GET | `/api/history` | 估价历史列表 |
| GET | `/api/history/{id}` | 单条估价详情 |
| GET | `/api/bargains` | 捡漏列表 |
| PATCH | `/api/bargains/{id}/read` | 标记已读 |

## 开发注意事项

- 前端开发服务器端口 `5173`，后端 `8000`，Vite 代理 `/api` 到后端
- 后端 `.env` 需要配置至少一个 AI 模型的 API Key（DeepSeek / 通义千问 / OpenAI）
- 数据库为 SQLite（`backend/app/models/database.py`）
- 爬虫依赖 DrissionPage，需要闲鱼登录 Cookie 才能稳定抓取
- 前端修改后执行 `npm run build` 构建产物到 `frontend/dist/`

## CCD 相机专项

处理 CCD 相机相关任务时（XD 卡估价、相机型号识别、记忆棒等），可调用以下技能：
- `ccd-memory-card`：XD 卡估价、相机型号识别、记忆棒等专业知识
- `ccd-model-database`：全品牌 CCD 型号数据库（覆盖 **16 个品牌、约 852 个型号**），用于爬取关键词生成和估价系统型号覆盖

CCD 型号数据库包含：佳能 IXUS/PowerShot A/SX (154)、索尼 T/W/H/P/M/S/N (159)、尼康 Coolpix S/L (108)、松下 Lumix FX (26)、卡西欧 Exilim (70)、三星 NV/ST/MV/WB (60)、富士 FinePix xD (104)、奥林巴斯 μ/Stylus/FE/SP xD (128)、宾得 Optio (25)、柯达 EasyShare (38)。

## 环境

- 开发环境: Windows (PowerShell)
- 服务器: 腾讯云 Linux
- Git 分支: main
