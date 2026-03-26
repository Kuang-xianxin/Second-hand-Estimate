# 估二手（Second-hand Estimate）

一个面向真实二手交易场景的智能估价项目：
- 输入关键词，抓取闲鱼相关商品数据
- 使用统计规则 + 多模型分析给出估价区间
- 自动识别潜在“捡漏”商品并生成列表

> 这是一个持续迭代中的工程化练习项目，当前版本可本地跑通核心估价链路。

---

## 项目亮点（求职版）

- **端到端闭环**：前端（Vue3）→ 后端 API（FastAPI）→ 爬虫采集 → 估价算法 → 数据落库 → 历史与捡漏展示
- **多模型并发估价**：集成 DeepSeek / 通义千问 / OpenAI，统一输出建议价、区间、置信度与理由
- **业务化数据处理**：对爬取价格做异常值处理与区间估算，降低极端价格干扰
- **可运营能力**：支持估价历史查询、捡漏提醒读取状态更新
- **工程配套**：`.env.example` 配置模板、前后端分离、浏览器扩展同步 Cookie

---

## 技术栈

### Frontend
- Vue 3
- Vite
- Vue Router
- Axios

### Backend
- FastAPI
- SQLAlchemy (async)
- SQLite
- DrissionPage / requests / BeautifulSoup
- OpenAI SDK（兼容多厂商接口）

---

## 目录结构

```text
.
├─ frontend/                 # Vue 前端
├─ backend/                  # FastAPI 后端
│  ├─ app/
│  │  ├─ api/                # /api 路由
│  │  ├─ crawler/            # 闲鱼采集
│  │  ├─ models/             # 数据模型与数据库
│  │  └─ services/           # 估价、多模型、捡漏逻辑
│  ├─ .env.example
│  └─ main.py
├─ browser-extension/        # Cookie 同步扩展
└─ 二手产品估价网站完整实现方案.md
```

---

## 当前已实现功能

- 关键词估价：`POST /api/valuate`
- 估价历史：`GET /api/history`
- 捡漏列表：`GET /api/bargains`
- 捡漏已读：`PATCH /api/bargains/{id}/read`
- Cookie 同步：`POST /api/sync-cookie`
- 健康检查：`GET /health`

---

## 本地运行

### 1) 启动后端

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows PowerShell 可用: Copy-Item .env.example .env
python main.py
```

后端默认运行在 `http://localhost:8000`。

### 2) 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，并通过 Vite 代理 `/api -> http://localhost:8000`。

---

## 环境变量说明（backend/.env）

最少需要根据你使用的模型填写 API Key：
- `DEEPSEEK_API_KEY`
- `QWEN_API_KEY`
- `OPENAI_API_KEY`

可按需选择模型：
- `DEEPSEEK_MODEL`
- `QWEN_MODEL`
- `QWEN_MODEL_SECONDARY`
- `OPENAI_MODEL`

其余配置可参考 `backend/.env.example`。

---

## 路线图（持续迭代）

- [ ] 优化估价结果可解释性（更细粒度理由）
- [ ] 增加关键词/类目级别统计看板
- [ ] 完善异常场景提示（数据不足、接口限流等）
- [ ] 增加基础测试与接口回归脚本
- [ ] 部署在线演示环境

---

## 声明

本项目仅用于学习与工程实践展示。涉及第三方平台数据时，请遵守目标平台服务条款与相关法律法规。
