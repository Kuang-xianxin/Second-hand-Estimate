import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.models.database import get_db
from app.services.cache import (
    get_cache_l1,
    get_cache_l2,
    get_cache_l3,
    get_cache_status,
)
from app.models.item import BargainAlert, CrawledItem
from app.models.global_bargain import GlobalBargain
from app.models.cache import CCDPriceCache
from sqlalchemy import select, func as sql_func

router = APIRouter(prefix="/api", tags=["缓存"])
logger = logging.getLogger(__name__)


class CachedValuationResponse(BaseModel):
    from_cache: bool
    cache_level: str  # "L1" / "L2"
    keyword: str
    display_name: Optional[str] = None
    brand: Optional[str] = None
    base_price: float
    price_min: float
    price_max: float
    median_price: Optional[float] = None
    sample_count: int
    is_xd_card: bool = False
    xd_card_bundle_count: int = 0
    crawled_at: Optional[str] = None
    history: list = []


class GlobalBargainItem(BaseModel):
    id: int
    item_id: str
    keyword: Optional[str] = None
    brand: Optional[str] = None
    title: Optional[str] = None
    current_price: float
    base_price: float
    profit_estimate: float
    discount_rate: float
    condition: Optional[str] = None
    quality_score: Optional[float] = None
    is_xd_card: bool = False
    xd_card_size: str = ""
    xd_card_value: float = 0.0
    url: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/valuate/cached", response_model=CachedValuationResponse)
async def valuate_cached(
    keyword: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """
    缓存优先估价接口：
    1. 查 L1（Redis）< 1ms
    2. 查 L2（PostgreSQL）5-20ms
    3. 均未命中返回 404，触发旧逻辑（SSE）
    """
    import re
    from app.api.valuate import _canonicalize_keyword
    canonical = _canonicalize_keyword(keyword)

    # L1
    cached = await get_cache_l1(canonical)
    if cached:
        history = await get_cache_l3(canonical, db)
        return CachedValuationResponse(
            from_cache=True,
            cache_level="L1",
            keyword=cached.get("keyword", canonical),
            display_name=cached.get("display_name"),
            brand=cached.get("brand"),
            base_price=cached.get("base_price", 0),
            price_min=cached.get("price_min", 0),
            price_max=cached.get("price_max", 0),
            median_price=cached.get("median_price"),
            sample_count=cached.get("sample_count", 0),
            is_xd_card=cached.get("is_xd_card", False),
            xd_card_bundle_count=cached.get("xd_card_bundle_count", 0),
            crawled_at=cached.get("crawled_at"),
            history=history,
        )

    # L2
    cached2 = await get_cache_l2(canonical, db)
    if cached2:
        history = await get_cache_l3(canonical, db)
        return CachedValuationResponse(
            from_cache=True,
            cache_level="L2",
            keyword=cached2.get("keyword", canonical),
            display_name=cached2.get("display_name"),
            brand=cached2.get("brand"),
            base_price=cached2.get("base_price", 0),
            price_min=cached2.get("price_min", 0),
            price_max=cached2.get("price_max", 0),
            median_price=cached2.get("median_price"),
            sample_count=cached2.get("sample_count", 0),
            is_xd_card=cached2.get("is_xd_card", False),
            xd_card_bundle_count=cached2.get("xd_card_bundle_count", 0),
            crawled_at=cached2.get("crawled_at"),
            history=history,
        )

    # 缓存未命中
    from fastapi import HTTPException
    raise HTTPException(
        status_code=404,
        detail={
            "message": "缓存未命中，请使用 /api/valuate/stream 触发实时爬取",
            "keyword": canonical,
        },
    )


@router.get("/cache/status")
async def cache_status(db: AsyncSession = Depends(get_db)):
    """返回缓存系统整体状态。"""
    return await get_cache_status(db)


@router.get("/bargains/global", response_model=list[GlobalBargainItem])
async def get_global_bargains(
    brand: str = Query(None),
    xd_card: bool = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    全局捡漏列表（捡漏广场用）：按利润从高到低排序。
    支持按品牌、XD 卡筛选，分页返回。
    """
    query = select(GlobalBargain).order_by(GlobalBargain.profit_estimate.desc())
    count_query = select(sql_func.count(GlobalBargain.id))

    if brand:
        query = query.where(GlobalBargain.brand == brand)
        count_query = count_query.where(GlobalBargain.brand == brand)
    if xd_card is True:
        query = query.where(GlobalBargain.is_xd_card == True)
        count_query = count_query.where(GlobalBargain.is_xd_card == True)
    elif xd_card is False:
        query = query.where(GlobalBargain.is_xd_card == False)
        count_query = count_query.where(GlobalBargain.is_xd_card == False)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return [
        GlobalBargainItem(
            id=item.id,
            item_id=item.item_id,
            keyword=item.keyword,
            brand=item.brand,
            title=item.title,
            current_price=item.current_price,
            base_price=item.base_price,
            profit_estimate=item.profit_estimate,
            discount_rate=item.discount_rate,
            condition=item.condition,
            quality_score=item.quality_score,
            is_xd_card=item.is_xd_card,
            xd_card_size=item.xd_card_size or "",
            xd_card_value=item.xd_card_value or 0.0,
            url=item.url,
            image_url=item.image_url,
            created_at=item.created_at.isoformat() if item.created_at else None,
        )
        for item in items
    ]


@router.get("/bargains/global/count")
async def get_global_bargains_count(
    brand: str = Query(None),
    xd_card: bool = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """全局捡漏总数。"""
    query = select(sql_func.count(GlobalBargain.id))
    if brand:
        query = query.where(GlobalBargain.brand == brand)
    if xd_card is True:
        query = query.where(GlobalBargain.is_xd_card == True)
    elif xd_card is False:
        query = query.where(GlobalBargain.is_xd_card == False)
    result = await db.execute(query)
    total = result.scalar() or 0

    brand_counts = {}
    if brand is None and xd_card is None:
        brand_result = await db.execute(
            select(GlobalBargain.brand, sql_func.count(GlobalBargain.id))
            .group_by(GlobalBargain.brand)
        )
        brand_counts = {row[0] or "其他": row[1] for row in brand_result.fetchall()}

    return {"total": total, "brand_counts": brand_counts}


@router.get("/bargains/by-keyword")
async def get_bargains_by_keyword(
    keyword: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """
    按型号查询条件捡漏（有捡漏才返回，无捡漏返回空列表）。
    来自 bargain_alerts 表。
    """
    import re
    from app.api.valuate import _canonicalize_keyword
    canonical = _canonicalize_keyword(keyword)

    result = await db.execute(
        select(BargainAlert)
        .where(BargainAlert.keyword == canonical)
        .order_by(BargainAlert.profit_estimate.desc())
        .limit(5)
    )
    alerts = result.scalars().all()
    if not alerts:
        result2 = await db.execute(
            select(BargainAlert)
            .where(BargainAlert.keyword.like(f"%{canonical}%"))
            .order_by(BargainAlert.profit_estimate.desc())
            .limit(5)
        )
        alerts = result2.scalars().all()

    return [
        {
            "id": a.id,
            "item_id": a.item_id,
            "keyword": a.keyword,
            "title": a.title,
            "price": a.price,
            "current_price": a.current_price or a.price,
            "base_price": a.base_price,
            "profit_estimate": a.profit_estimate,
            "discount_rate": a.discount_rate,
            "condition": a.condition,
            "quality_score": a.quality_score,
            "is_xd_card": a.is_xd_card,
            "xd_card_size": a.xd_card_size or "",
            "xd_card_value": a.xd_card_value or 0.0,
            "url": a.url,
            "image_url": a.image_url,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]
