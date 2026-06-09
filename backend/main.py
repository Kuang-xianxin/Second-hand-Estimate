import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text

from app.models.database import init_db, AsyncSessionLocal, engine
from app.models.redis_client import close_redis, get_redis
from app.api.valuate import router as valuate_router
from app.api.cache_api import router as cache_router
from app.api.stats_api import router as stats_router
from app.api.auth import router as auth_router
from app.config import settings

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_production()
    await init_db()
    setup_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
        await close_redis()
        await engine.dispose()


def setup_scheduler():
    from app.scheduler import setup_scheduler as _setup, run_full_crawl_task
    import asyncio

    if settings.crawl_enabled:
        _setup(AsyncSessionLocal)
    else:
        logger.info("定时爬取已禁用（crawl_enabled=False），跳过调度器初始化")

    # 初始全量爬取需要同时启用 crawl_enabled 和 initial_crawl_enabled
    if not settings.crawl_enabled:
        logger.info("定时爬取已禁用，跳过首次全量爬取")
        return
    if not settings.initial_crawl_enabled:
        logger.info("首次启动爬取已禁用（initial_crawl_enabled=False），跳过")
        return

    async def trigger_initial_crawl():
        try:
            from sqlalchemy import select, func as sql_func
            from app.models.cache import CCDPriceCache
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(sql_func.count(CCDPriceCache.id)))
                count = result.scalar() or 0
            if count == 0:
                logger.info("缓存表为空，触发首次全量爬取...")
                await run_full_crawl_task(AsyncSessionLocal, skip_lock=True)
            else:
                logger.info(f"缓存表已有 {count} 条记录，跳过首次全量爬取")
        except Exception:
            logger.exception("首次全量爬取异常")

    asyncio.create_task(trigger_initial_crawl())


def shutdown_scheduler():
    from app.scheduler import shutdown_scheduler as _shutdown
    _shutdown()


app = FastAPI(
    title="估二手 API",
    description="二手商品智能估价平台后端",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_host_list or ["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
)

app.include_router(valuate_router)
app.include_router(cache_router)
app.include_router(stats_router)
app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "估二手"}


@app.get("/ready")
async def ready():
    checks = {"database": False, "redis": False}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        logger.exception("Readiness database check failed")

    try:
        redis_client = await get_redis()
        checks["redis"] = bool(redis_client and await redis_client.ping())
    except Exception:
        logger.exception("Readiness Redis check failed")

    status_code = 200 if all(checks.values()) else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if status_code == 200 else "not_ready", "checks": checks},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.backend_port)
