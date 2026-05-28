"""
爬取进度 + 系统统计 API。
用于前端实时展示后台爬取进度和数据库概览。
"""
import json
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func

from app.models.database import get_db
from app.models.redis_client import get_redis, CRAWL_PROGRESS_KEY
from app.models.cache import CCDPriceCache
from app.models.global_bargain import GlobalBargain
from app.models.crawl_status import CrawlStatus
from app.models.price_history import PriceHistory
from app.models.item import CrawledItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["系统"])


class CrawlProgress(BaseModel):
    """爬取进度"""
    batch_id: str
    stage: str
    done: int
    total: int
    current_keyword: str
    success_count: int
    fail_count: int
    total_items: int
    bargains_found: int
    started_at: str
    finished_at: str


class StageInfo(BaseModel):
    """阶段信息"""
    name: str
    count: int


class SystemStats(BaseModel):
    """系统统计概览"""
    # 缓存覆盖
    cached_models: int
    latest_crawl: str | None
    # 商品数据
    total_items: int
    # 捡漏数据
    total_bargains: int
    bargains_by_brand: dict
    # 历史记录
    price_history_count: int
    # 最近爬取批次
    recent_batches: list
    # 品牌覆盖
    brands: dict


_STAGE_LABELS = {
    "idle":       "空闲",
    "starting":   "启动中",
    "crawling":   "爬取中",
    "pricing":    "计算估价",
    "detecting_bargains": "检测捡漏",
    "saving":     "写入数据",
    "completed":  "已完成",
    "failed":     "失败",
}


@router.get("/crawl/progress", response_model=CrawlProgress | None)
async def get_crawl_progress():
    """
    返回当前爬取任务的实时进度。
    若无正在进行的任务，返回 None（前端据此判断"空闲"状态）。
    进度数据来自 Redis，每 5 秒轮询即可。
    """
    r = await get_redis()
    if not r:
        return None
    try:
        raw = await r.get(CRAWL_PROGRESS_KEY)
        if not raw:
            return None
        data = json.loads(raw)
        return CrawlProgress(
            batch_id=data.get("batch_id", ""),
            stage=_STAGE_LABELS.get(data.get("stage", ""), data.get("stage", "")),
            done=data.get("done", 0),
            total=data.get("total", 0),
            current_keyword=data.get("current_keyword", ""),
            success_count=data.get("success_count", 0),
            fail_count=data.get("fail_count", 0),
            total_items=data.get("total_items", 0),
            bargains_found=data.get("bargains_found", 0),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
        )
    except Exception as e:
        logger.warning(f"读取爬取进度失败: {e}")
        return None


@router.get("/stats/overview", response_model=SystemStats)
async def get_stats_overview(db: AsyncSession = Depends(get_db)):
    """
    返回系统统计概览：
    - 缓存覆盖的型号数
    - 最新爬取时间
    - 总商品数
    - 捡漏总数及按品牌分布
    - 价格历史记录数
    - 最近 5 个爬取批次摘要
    - 各品牌型号覆盖数
    """
    # L2 缓存：覆盖型号数 + 最新爬取时间
    l2_result = await db.execute(
        select(
            sql_func.count(CCDPriceCache.id),
            sql_func.max(CCDPriceCache.crawled_at),
        )
    )
    l2_row = l2_result.first()
    cached_models = l2_row[0] or 0 if l2_row else 0
    latest_crawl = l2_row[1].isoformat() if l2_row and l2_row[1] else None

    # 总商品数
    total_items_result = await db.execute(
        select(sql_func.count(CrawledItem.id))
    )
    total_items = total_items_result.scalar() or 0

    # 全局捡漏展示口径：复用捡漏广场过滤，避免历史脏数据污染统计卡片。
    from app.api.cache_api import _fetch_displayable_global_bargains

    displayable_bargains = await _fetch_displayable_global_bargains(db)
    total_bargains = len(displayable_bargains)
    bargains_by_brand = {}
    for item in displayable_bargains:
        brand = item.brand or "其他"
        bargains_by_brand[brand] = bargains_by_brand.get(brand, 0) + 1

    # 价格历史记录数
    history_count_result = await db.execute(
        select(sql_func.count(PriceHistory.id))
    )
    price_history_count = history_count_result.scalar() or 0

    # 最近 5 个爬取批次
    batches_result = await db.execute(
        select(CrawlStatus)
        .order_by(CrawlStatus.started_at.desc())
        .limit(5)
    )
    recent_batches = [
        {
            "batch_id": r.batch_id,
            "status": r.status,
            "total_keywords": r.total_keywords,
            "success_count": r.success_count,
            "fail_count": r.fail_count,
            "total_items": r.total_items,
            "bargains_found": r.bargains_found,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "error_message": r.error_message,
        }
        for r in batches_result.scalars().all()
    ]

    # 各品牌型号覆盖数
    brand_result = await db.execute(
        select(CCDPriceCache.brand, sql_func.count(CCDPriceCache.id))
        .group_by(CCDPriceCache.brand)
    )
    brands = {
        (row[0] or "其他"): row[1]
        for row in brand_result.fetchall()
    }

    return SystemStats(
        cached_models=cached_models,
        latest_crawl=latest_crawl,
        total_items=total_items,
        total_bargains=total_bargains,
        bargains_by_brand=bargains_by_brand,
        price_history_count=price_history_count,
        recent_batches=recent_batches,
        brands=brands,
    )
