# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

估二手 is a second-hand CCD camera price estimation platform. Users input a keyword, the system scrapes real Xianyu (闲鱼) listings, then applies statistical filtering + multi-model AI analysis to produce a price range, condition distribution, and bargain recommendations.

## Tech Stack

- **Frontend**: Vue 3 + TypeScript + Vite + Axios + Vue Router
- **Backend**: FastAPI + SQLAlchemy 2.0 async + PostgreSQL (production) / SQLite (dev fallback) + Redis
- **AI Models**: DeepSeek, Qwen (通义千问), Doubao (豆包) — concurrent calls
- **Scraper**: Playwright (requires Xianyu login cookie)
- **Scheduler**: APScheduler (full crawl every 1.5 hours)

## Common Commands

### Frontend
```bash
cd frontend
npm install
npm run dev          # Dev server on http://localhost:5173, proxies /api to localhost:8000
npm run build        # Production build to frontend/dist/
npm run type-check   # vue-tsc --noEmit
```

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env     # Fill in API keys
python main.py           # Runs on port 8000 (or BACKEND_PORT in .env)
```

## High-Level Architecture

### Three-Tier Caching
All valuation queries go through a cache-first pipeline:

1. **L1 Redis** (< 1ms): hot model snapshots, TTL 1.5h, shared across Uvicorn workers
2. **L2 PostgreSQL** (5–20ms): `ccd_price_cache` table stores complete data for ~852 CCD models
3. **L3 Historical trends** (20–50ms): `price_history` for price trend reference

If L1/L2 miss, the system falls back to real-time scraping + AI valuation (45–90s).

### Two Distinct Bargain Mechanisms

| | Conditional Bargain | Global Bargain (捡漏广场) |
|---|---|---|
| Trigger | User searches a specific model | Background scheduler every 1.5h |
| Data source | Current search's crawled results | All ~852 CCD models' crawled results |
| Display | Bottom of valuation result page (HomeView) | Independent "Bargain Plaza" page (BargainView) |
| Data table | `bargain_alerts` | `global_bargains` |
| Sorting | By profit desc | By profit desc, cross-brand |

`global_bargains` is fully replaced (TRUNCATE + INSERT) after each scheduled crawl, not incrementally updated.

### Backend Entry Flow

`main.py` → `lifespan`:
1. `init_db()` creates tables + runs SQLite→PG migration helpers
2. `setup_scheduler()` starts APScheduler
3. On first boot, if `ccd_price_cache` is empty, immediately triggers a full crawl (`skip_lock=True`) so the Bargain Plaza has data without waiting 1.5h

### Scraper Dependency

The crawler (`backend/app/crawler/xianyu.py`) requires an active Xianyu login. Cookie state is persisted in `backend/xianyu_storage_state.json`. Without valid cookies, searches return 401/429 errors.

### Database Dual-Mode

`backend/app/models/database.py` supports both PostgreSQL and SQLite via the connection string:
- `postgresql+asyncpg://...` → PostgreSQL mode with full DDL
- `sqlite+aiosqlite://...` → SQLite mode with column migration helpers

`backend/app/config.py` sets the default to SQLite for local dev; production overrides via `.env`.

## Key Files for Navigation

| File | Responsibility |
|---|---|
| `backend/app/config.py` | Pydantic settings, all env vars |
| `backend/app/scheduler.py` | APScheduler job definition, full crawl orchestration |
| `backend/app/services/cache.py` | L1/L2/L3 cache read/write + invalidation |
| `backend/app/services/crawl_worker.py` | Batch crawling with concurrency control |
| `backend/app/services/bargain_detector.py` | Global bargain detection across all models |
| `backend/app/services/cache_updater.py` | Batch upsert cache + L1 warm-up |
| `backend/app/models/database.py` | Async engine, session factory, init/migration |
| `backend/app/api/valuate.py` | `/api/valuate` (real-time) and `/api/valuate/stream` (SSE) |
| `backend/app/api/cache_api.py` | `/api/valuate/cached`, `/api/bargains/*`, `/api/cache/status` |
| `frontend/vite.config.js` | Dev proxy: `/api` → `http://localhost:8000` |
| `frontend/src/api/index.ts` | All API client functions |

## Cursor / Agent Rules

- `.cursor/rules/agents-md-sync.mdc` requires that **any code change must be reflected in `AGENTS.md`** (located at repo root). Do not modify code without updating `AGENTS.md` for new APIs, tables, or architecture changes.
- `.cursor/rules/model.md` requires using the latest Claude model as default.

## Environment Variables (backend/.env)

Minimum required:
```
DEEPSEEK_API_KEY=...
QWEN_API_KEY=...
DOUBAO_API_KEY=...
DATABASE_URL=postgresql+asyncpg://...   # or sqlite+aiosqlite:///./guessr.db
REDIS_URL=redis://localhost:6379/0
ADMIN_TOKEN=...                          # For /sync-cookie and /open-xianyu-login
```

See `backend/app/config.py` for all available settings.
