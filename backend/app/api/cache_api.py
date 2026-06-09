import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.models.auth import AppUser
from app.models.global_bargain import GlobalBargain
from app.models.cache import CCDPriceCache
from app.config import settings
from app.api.valuate import require_admin_token
from app.services.auth import get_current_user
from app.crawler.xianyu import XianyuItem
from app.services.bargain import filter_target_items
from sqlalchemy import or_, select, func as sql_func

router = APIRouter(prefix="/api", tags=["缓存"])
logger = logging.getLogger(__name__)

CCD_GLOBAL_BARGAIN_BRANDS = [
    "canon", "nikon", "sony", "fujifilm", "fuji", "olympus", "panasonic",
    "casio", "ricoh", "kodak", "samsung", "pentax", "sanyo",
]

CCD_GLOBAL_BARGAIN_TERMS = [
    "ccd", "相机", "数码相机", "卡片机",
    "佳能", "尼康", "索尼", "富士", "奥林巴斯", "松下", "卡西欧", "柯达",
    "canon", "nikon", "sony", "fujifilm", "fuji", "olympus", "panasonic",
    "casio", "kodak", "coolpix", "ixus", "powershot", "cybershot", "finepix",
    "lumix", "exilim", "sanyo", "三洋",
]

GLOBAL_BARGAIN_REJECT_KEYWORDS = [
    "iphone", "苹果", "手机", "华为", "小米", "oppo", "vivo", "pro max",
]

GLOBAL_BARGAIN_REJECT_TITLE_TERMS = [
    "eosmsg", "快门次数", "测试快门", "测试相机快门", "软件",
]


def _global_bargain_display_filter():
    """只展示相机/CCD 相关全局捡漏，避免历史脏数据污染捡漏广场。"""
    filters = [GlobalBargain.brand.in_(CCD_GLOBAL_BARGAIN_BRANDS)]
    for term in CCD_GLOBAL_BARGAIN_TERMS:
        pattern = f"%{term}%"
        filters.append(GlobalBargain.keyword.ilike(pattern))
        filters.append(GlobalBargain.title.ilike(pattern))
    return or_(*filters)


def _global_bargain_to_xianyu_item(item: GlobalBargain) -> XianyuItem:
    """把历史全局捡漏记录转成估价过滤器可识别的样本形状。"""
    return XianyuItem(
        item_id=item.item_id,
        title=item.title or "",
        price=float(item.current_price or 0),
        condition=item.condition or "",
        description=item.title or "",
        url=item.url or "",
        sold=False,
        sold_at=None,
        quality_score=float(item.quality_score or 50.0),
        images=[item.image_url] if item.image_url else [],
        query_keyword=item.keyword or "",
    )


def _is_global_bargain_displayable(item: GlobalBargain) -> bool:
    keyword = (item.keyword or "").strip()
    if not keyword:
        return False
    keyword_low = keyword.lower()
    if any(term in keyword_low for term in GLOBAL_BARGAIN_REJECT_KEYWORDS):
        return False
    title_low = (item.title or "").lower()
    if any(term in title_low for term in GLOBAL_BARGAIN_REJECT_TITLE_TERMS):
        return False
    return bool(filter_target_items([_global_bargain_to_xianyu_item(item)], keyword))


async def _fetch_displayable_global_bargains(
    db: AsyncSession,
    brand: Optional[str] = None,
    xd_card: Optional[bool] = None,
) -> list[GlobalBargain]:
    display_filter = _global_bargain_display_filter()
    query = select(GlobalBargain).where(display_filter).order_by(GlobalBargain.profit_estimate.desc())
    if brand:
        query = query.where(GlobalBargain.brand == brand)
    if xd_card is True:
        query = query.where(GlobalBargain.is_xd_card == True)
    elif xd_card is False:
        query = query.where(GlobalBargain.is_xd_card == False)

    result = await db.execute(query)
    return [item for item in result.scalars().all() if _is_global_bargain_displayable(item)]


def _cache_lookup_keys(keyword: str) -> list[str]:
    """返回兼容旧关键词与分层 canonical model 的缓存查询 key。"""
    from app.api.valuate import _canonicalize_keyword
    from app.services.keyword_tier import get_canonical_keyword

    candidates: list[str] = []

    def add(value: str):
        value = (value or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    normalized = _canonicalize_keyword(keyword)
    for value in (keyword, normalized):
        add(value)
        add(get_canonical_keyword(value))
        add(value.lower())

    return candidates


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
    _current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    缓存优先估价接口：
    1. 查 L1（Redis）< 1ms
    2. 查 L2（PostgreSQL）5-20ms
    3. 均未命中返回 404，触发旧逻辑（SSE）
    """
    lookup_keys = _cache_lookup_keys(keyword)
    canonical = lookup_keys[0]

    # L1
    for key in lookup_keys:
        cached = await get_cache_l1(key)
        if cached:
            history = await get_cache_l3(cached.get("keyword", key), db)
            return CachedValuationResponse(
                from_cache=True,
                cache_level="L1",
                keyword=cached.get("keyword", key),
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
    for key in lookup_keys:
        cached2 = await get_cache_l2(key, db)
        if cached2:
            history = await get_cache_l3(cached2.get("keyword", key), db)
            return CachedValuationResponse(
                from_cache=True,
                cache_level="L2",
                keyword=cached2.get("keyword", key),
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
async def cache_status(
    _current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回缓存系统整体状态。"""
    return await get_cache_status(db)


@router.get("/bargains/global", response_model=list[GlobalBargainItem])
async def get_global_bargains(
    brand: str = Query(None),
    xd_card: bool = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    全局捡漏列表（捡漏广场用）：按利润从高到低排序。
    支持按品牌、XD 卡筛选，分页返回。
    """
    displayable_items = await _fetch_displayable_global_bargains(db, brand=brand, xd_card=xd_card)
    offset = (page - 1) * limit
    items = displayable_items[offset:offset + limit]

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
    _current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全局捡漏总数。"""
    displayable_items = await _fetch_displayable_global_bargains(db, brand=brand, xd_card=xd_card)
    total = len(displayable_items)

    brand_counts = {}
    if brand is None and xd_card is None:
        for item in displayable_items:
            brand_key = item.brand or "其他"
            brand_counts[brand_key] = brand_counts.get(brand_key, 0) + 1

    return {"total": total, "brand_counts": brand_counts}


# ============================================================
# 爬虫健康/状态接口
# ============================================================

class CrawlerStatusResponse(BaseModel):
    has_storage_state: bool = False
    login_valid: Optional[bool] = None
    canary_ok: Optional[bool] = None
    canary_message: str = ""
    last_debug_summary: dict = {}
    tier_counts: dict = {}
    current_concurrency: int = 1


@router.get("/crawler/status", response_model=CrawlerStatusResponse)
async def crawler_status(
    run_canary: bool = Query(False),
    _admin=Depends(require_admin_token),
):
    """
    爬虫健康状态检查：登录态、金丝雀预检结果、分层关键词数。
    前端可轮询此接口判断是否需要提示用户重新登录。
    """
    from app.crawler.xianyu import get_crawler
    from app.services.keyword_tier import get_tier_counts

    crawler = get_crawler()
    has_state = crawler.has_storage_state()
    last_debug = crawler.get_last_debug_summary()

    tier_counts = get_tier_counts()

    canary_ok = None
    canary_msg = ""
    if has_state and run_canary:
        try:
            from app.services.crawl_worker import crawl_canary
            ok, reason, _ = await crawl_canary()
            canary_ok = ok
            canary_msg = reason
        except Exception as e:
            canary_msg = f"canary 检测异常: {e}"

    return CrawlerStatusResponse(
        has_storage_state=has_state,
        login_valid=None if canary_ok is None else canary_ok,
        canary_ok=canary_ok,
        canary_message=canary_msg,
        last_debug_summary=last_debug,
        tier_counts=tier_counts,
        current_concurrency=settings.crawl_concurrency,
    )


@router.get("/crawler/tiers")
async def crawler_tiers(_admin=Depends(require_admin_token)):
    """返回各层级关键词统计信息。"""
    from app.services.keyword_tier import (
        get_tier_counts,
        get_t0_model_ids,
        KeywordTier,
        get_keywords_by_tier,
    )
    return {
        "tier_counts": get_tier_counts(),
        "t0_models": get_t0_model_ids(),
        "t0_keyword_count": len(get_keywords_by_tier(KeywordTier.T0_HOT)),
        "t1_keyword_count": len(get_keywords_by_tier(KeywordTier.T1_WARM)),
        "config": {
            "scheduler_mode": settings.crawl_scheduler_mode,
            "t0_enabled": settings.crawl_t0_enabled,
            "t1_enabled": settings.crawl_t1_enabled,
            "t2_enabled": settings.crawl_t2_enabled,
            "t0_interval_s": settings.crawl_interval_seconds,
            "t1_interval_s": settings.crawl_interval_t1_seconds,
            "t2_interval_s": settings.crawl_interval_t2_seconds,
            "canary_enabled": settings.crawl_canary_enabled,
            "dynamic_concurrency": settings.crawl_dynamic_concurrency,
        },
    }


@router.get("/crawler/login-check")
async def crawler_login_check(_admin=Depends(require_admin_token)):
    """轻量登录态检查：不爬取，只检查 storage state 是否存在。"""
    from app.crawler.xianyu import get_crawler, STORAGE_STATE_FILE
    crawler = get_crawler()
    has_state = crawler.has_storage_state()
    return {
        "has_storage_state": has_state,
        "needs_login": not has_state,
    }


class TriggerCrawlRequest(BaseModel):
    tier: str = "t0"           # t0 / t1 / t2
    limit: int = 0             # 限制关键词数量，0=全部
    max_items_per_kw: int = 40
    concurrency: int = 2
    skip_canary: bool = False


@router.post("/crawler/trigger")
async def trigger_crawl(req: TriggerCrawlRequest, _admin=Depends(require_admin_token)):
    """手动触发分层爬取+入库全流程。"""
    if settings.crawl_scheduler_mode.strip().lower() == "external":
        raise HTTPException(
            status_code=409,
            detail="生产爬虫使用独立 worker，请通过 systemd 启动 guessr-crawl@<tier>.service",
        )

    from app.scheduler import _run_tier_crawl
    from app.models.database import AsyncSessionLocal
    from app.services.keyword_tier import KeywordTier

    tier_map = {"t0": KeywordTier.T0_HOT, "t1": KeywordTier.T1_WARM, "t2": KeywordTier.T2_COLD}
    tier = tier_map.get(req.tier, KeywordTier.T0_HOT)

    import asyncio
    asyncio.create_task(_run_tier_crawl(
        tier=tier,
        db_session_factory=AsyncSessionLocal,
        skip_lock=False,
        max_items_per_kw=req.max_items_per_kw or 40,
        skip_canary=req.skip_canary,
        concurrency=req.concurrency or settings.crawl_concurrency,
        keyword_limit=req.limit or 0,
    ))

    return {"status": "started", "tier": req.tier, "message": f"已触发 {req.tier} 爬取任务"}


@router.get("/bargains/by-keyword")
async def get_bargains_by_keyword(
    keyword: str = Query(..., min_length=1),
    current_user: AppUser = Depends(get_current_user),
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
        .where(
            BargainAlert.keyword == canonical,
            BargainAlert.user_id == current_user.id,
        )
        .order_by(BargainAlert.profit_estimate.desc())
        .limit(5)
    )
    alerts = result.scalars().all()
    if not alerts:
        result2 = await db.execute(
            select(BargainAlert)
            .where(
                BargainAlert.keyword.like(f"%{canonical}%"),
                BargainAlert.user_id == current_user.id,
            )
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
