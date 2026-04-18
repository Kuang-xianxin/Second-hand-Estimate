# 估二手（Second-hand Estimate）

输入任意二手商品关键词，系统自动抓取闲鱼真实挂牌数据，通过统计规则 + 多模型 AI 分析，给出合理估价区间、成色分布，并智能识别潜在"捡漏"商品。

---

## 核心功能

- **关键词估价**：输入商品名，自动爬取闲鱼样本数据 → 统计清洗 → AI 多模型并发估价
- **成色分析**：对抓取的商品按质量评分，统计高/中/低成色分布
- **捡漏识别**：自动找出价格明显低于合理估值的商品，标注 XD 卡等配件附加价值
- **历史记录**：估价历史永久保存，随时回看之前的估价结果
- **XD 卡相机专项**：针对富士 XD 卡相机型号，自动识别 XD 卡捆绑价值

---

## 技术栈

**前端** — Vue 3 + TypeScript + Vite + Axios + Vue Router（SSR 流式输出，实时展示估价进度）

**后端** — FastAPI + SQLAlchemy (async) + SQLite + DrissionPage

**AI 估价** — 兼容 DeepSeek / 通义千问 / OpenAI，多模型并发输出置信度 + 估价理由

**数据采集** — DrissionPage + BeautifulSoup，浏览器扩展同步闲鱼登录态

---

## 目录结构

```
.
├─ frontend/                   # Vue 3 + TypeScript 前端
│  ├─ src/views/
│  │   ├─ HomeView.vue         # 估价主页面（SSE 流式结果展示）
│  │   └─ HistoryView.vue      # 估价历史页面
│  ├─ src/types/index.ts       # TypeScript 类型定义（与后端数据结构一一对应）
│  └─ vite.config.js            # 开发代理配置（/api -> localhost:8000）
├─ backend/
│  ├─ app/
│  │  ├─ api/valuate.py        # /api/valuate（SSE 流式估价）、/api/history、/api/bargains
│  │  ├─ crawler/xianyu.py     # 闲鱼商品数据采集
│  │  ├─ models/              # SQLAlchemy 模型与数据库
│  │  └─ services/
│  │       ├─ pricing.py       # 基准价计算与异常值过滤
│  │       ├─ llm.py           # 多模型并发调用
│  │       ├─ bargain.py       # 捡漏识别逻辑
│  │       └─ opencli_adapter.py
│  └─ main.py                  # FastAPI 入口
└─ browser-extension/          # 闲鱼 Cookie 同步浏览器扩展
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/valuate` | SSE 流式估价（关键词 → 抓取 → 清洗 → AI 估价） |
| `GET` | `/api/history` | 估价历史列表 |
| `GET` | `/api/history/{id}` | 某次估价的完整详情 |
| `GET` | `/api/bargains` | 捡漏商品列表 |
| `PATCH` | `/api/bargains/{id}/read` | 标记捡漏消息已读 |
| `POST` | `/api/sync-cookie` | 同步闲鱼登录 Cookie |
| `GET` | `/health` | 健康检查 |

---

## 本地运行

### 后端

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 复制并填入 API Key
python main.py
```

后端运行在 `http://localhost:8000`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://localhost:5173`，通过 Vite 代理 `/api` 请求到后端。

前端生产构建：

```bash
npm run build
```

类型检查：

```bash
npm run type-check
```

---

## 环境变量（backend/.env）

最少需要填入以下任一模型的 API Key：

```
DEEPSEEK_API_KEY=
QWEN_API_KEY=
OPENAI_API_KEY=
```

模型名称可按需调整（参考 `.env.example`）。

---

## 免责声明

本项目仅供学习与工程实践研究使用。数据采集和估价结果仅供参考，不构成交易建议。请遵守闲鱼平台服务条款及相关法律法规。
