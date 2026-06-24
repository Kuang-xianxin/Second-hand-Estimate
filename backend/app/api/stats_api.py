"""
爬取进度 + 系统统计 API。
用于前端实时展示后台爬取进度和数据库概览。
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func

from app.models.database import get_db
from app.models.redis_client import get_redis, CRAWL_PROGRESS_KEY
from app.models.cache import CCDPriceCache
from app.models.global_bargain import GlobalBargain
from app.models.crawl_status import CrawlStatus
from app.models.price_history import PriceHistory
from app.models.item import CrawledItem
from app.models.auth import AppUser
from app.config import settings
from app.services.auth import get_current_user
from app.services.tier_coverage import count_model_covered_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["系统"])


class CrawlProgress(BaseModel):
    """爬取进度"""
    batch_id: str
    stage: str
    stage_key: str = ""
    done: int
    total: int
    current_keyword: str
    success_count: int
    fail_count: int
    total_items: int
    bargains_found: int
    started_at: str
    finished_at: str
    raw_done: int = 0
    raw_total: int = 0
    keyword_done: int = 0
    keyword_total: int = 0
    progress_percent: int = 0
    progress_text: str = ""
    progress_unit: str = "progress"
    phase_steps: list[dict[str, Any]] = Field(default_factory=list)


class StageInfo(BaseModel):
    """阶段信息"""
    name: str
    count: int


class SystemStats(BaseModel):
    """系统统计概览"""
    # 缓存覆盖
    cached_models: int
    latest_crawl: str | None
    crawl_expected_models: int
    crawl_fresh_models_48h: int
    crawl_stale_models_48h: int
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
    # 统一型号池覆盖
    model_coverage_cached: int
    model_coverage_expected: int


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

_STAGE_KEYS_ZH = {
    "空闲": "idle",
    "启动": "starting",
    "爬取": "crawling",
    "估价": "pricing",
    "计算": "pricing",
    "捡漏": "detecting_bargains",
    "写入": "saving",
    "保存": "saving",
    "完成": "completed",
    "失败": "failed",
    "错误": "failed",
}

_PHASES = [
    ("crawling", "爬取商品", 0, 70),
    ("pricing", "规则清洗/估价", 70, 82),
    ("detecting_bargains", "检测捡漏", 82, 92),
    ("saving", "写入缓存", 92, 98),
    ("completed", "完成", 100, 100),
]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stage_key(raw_stage: str) -> str:
    stage = (raw_stage or "").strip()
    if stage in _STAGE_LABELS:
        return stage
    low = stage.lower()
    if low in _STAGE_LABELS:
        return low
    for needle, key in _STAGE_KEYS_ZH.items():
        if needle in stage:
            return key
    return low or "idle"


def _phase_percent(stage_key: str, item_percent: int) -> int:
    if stage_key == "failed":
        return min(99, max(0, item_percent))
    if stage_key == "completed":
        return 100
    if stage_key == "crawling":
        # WHY: 前端旧进度条直接用 done/total 算百分比；爬取阶段必须显示采样进度，不显示并发 worker 完成度。
        return min(99, max(0, item_percent))
    for key, _, start, _ in _PHASES:
        if key == stage_key:
            return start
    return max(0, min(99, item_percent))


def _build_phase_steps(stage_key: str, progress_percent: int) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    phase_keys = [key for key, _, _, _ in _PHASES]
    current_index = phase_keys.index(stage_key) if stage_key in phase_keys else 0
    for key, label, start, end in _PHASES:
        if stage_key == "failed":
            status = "error" if key == "crawling" else "pending"
        elif stage_key == "completed":
            status = "done"
        elif phase_keys.index(key) < current_index:
            status = "done"
        elif key == stage_key:
            status = "pending"
        else:
            status = "pending"
        steps.append({
            "key": key,
            "label": label,
            "status": status,
            "start_percent": start,
            "end_percent": end,
        })
    return steps


def _normalize_crawl_progress(data: dict[str, Any]) -> dict[str, Any]:
    """Return UI-oriented progress while preserving raw counters for debugging."""
    raw_stage = str(data.get("stage", "") or "")
    stage_key = _stage_key(raw_stage)
    raw_done = _as_int(data.get("done"))
    raw_total = _as_int(data.get("total"))
    success_count = _as_int(data.get("success_count"))
    fail_count = _as_int(data.get("fail_count"))
    total_items = _as_int(data.get("total_items"))

    keyword_total = _as_int(
        data.get("keyword_total")
        or data.get("total_keywords")
        or data.get("model_total")
        or raw_total
    )
    keyword_total = max(keyword_total, 1)
    keyword_done = max(
        success_count + fail_count,
        _as_int(data.get("keyword_done")),
        _as_int(data.get("completed_keywords")),
    )
    if stage_key == "completed":
        keyword_done = max(keyword_done, keyword_total)
    keyword_done = min(keyword_done, keyword_total)

    max_items_per_kw = max(
        1,
        _as_int(
            data.get("max_items_per_kw")
            or data.get("max_items_per_keyword")
            or data.get("max_items")
            or settings.max_items_per_crawl_keyword,
            settings.max_items_per_crawl_keyword,
        ),
    )
    expected_items = max(1, keyword_total * max_items_per_kw)
    item_percent = min(100, round(total_items / expected_items * 100)) if total_items else 0
    keyword_percent = round(keyword_done / keyword_total * 100)

    # WHY: Redis 写入端的 done/total 可能是并发 worker 完成度；UI 需要流水线真实进度。
    progress_percent = _phase_percent(stage_key, max(item_percent, keyword_percent))

    display_total = max(100, keyword_total * 100)
    display_done = min(display_total, round(display_total * progress_percent / 100))
    progress_unit = "progress"
    progress_text = ""
    current_keyword = str(data.get("current_keyword", "") or "")

    if stage_key == "crawling":
        if total_items:
            progress_text = f"爬取样本 {total_items}/{expected_items} 条"
        else:
            progress_text = f"爬取型号 {keyword_done}/{keyword_total} 个"
    elif stage_key == "pricing":
        progress_text = "规则清洗与估价计算"
    elif stage_key == "detecting_bargains":
        progress_text = "检测捡漏机会"
    elif stage_key == "saving":
        progress_text = "写入商品、缓存和捡漏结果"
    elif stage_key == "completed":
        progress_text = "全部完成"
    elif stage_key == "failed":
        progress_text = "任务失败"

    if progress_text and current_keyword and progress_text not in current_keyword:
        current_keyword = f"{progress_text} · {current_keyword}"
    elif progress_text and not current_keyword:
        current_keyword = progress_text

    return {
        "stage_key": stage_key,
        "stage_label": _STAGE_LABELS.get(stage_key, raw_stage or stage_key),
        "display_done": display_done,
        "display_total": display_total,
        "current_keyword": current_keyword,
        "raw_done": raw_done,
        "raw_total": raw_total,
        "keyword_done": keyword_done,
        "keyword_total": keyword_total,
        "progress_percent": progress_percent,
        "progress_text": progress_text,
        "progress_unit": progress_unit,
        "phase_steps": _build_phase_steps(stage_key, progress_percent),
    }


@router.get("/crawl/progress", response_model=CrawlProgress | None)
async def get_crawl_progress(_current_user: AppUser = Depends(get_current_user)):
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
        progress = _normalize_crawl_progress(data)
        return CrawlProgress(
            batch_id=data.get("batch_id", ""),
            stage=progress["stage_label"],
            stage_key=progress["stage_key"],
            done=progress["display_done"],
            total=progress["display_total"],
            current_keyword=progress["current_keyword"],
            success_count=data.get("success_count", 0),
            fail_count=data.get("fail_count", 0),
            total_items=data.get("total_items", 0),
            bargains_found=data.get("bargains_found", 0),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            raw_done=progress["raw_done"],
            raw_total=progress["raw_total"],
            keyword_done=progress["keyword_done"],
            keyword_total=progress["keyword_total"],
            progress_percent=progress["progress_percent"],
            progress_text=progress["progress_text"],
            progress_unit=progress["progress_unit"],
            phase_steps=progress["phase_steps"],
        )
    except Exception as e:
        logger.warning(f"读取爬取进度失败: {e}")
        return None


@router.get("/stats/overview", response_model=SystemStats)
async def get_stats_overview(
    _current_user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    # 统一型号池：低并发下所有型号同一优先级，不再按层级分组。
    from app.services.keyword_tier import get_all_model_ids, get_canonical_model
    model_ids = get_all_model_ids()
    cache_rows_result = await db.execute(
        select(CCDPriceCache.keyword, CCDPriceCache.crawled_at)
    )
    cache_rows = cache_rows_result.fetchall()
    cached_keywords = [kw for kw, _ in cache_rows if kw]
    fresh_cutoff = datetime.utcnow() - timedelta(hours=48)
    fresh_keywords = [
        kw for kw, crawled_at in cache_rows
        if kw and crawled_at and crawled_at >= fresh_cutoff
    ]
    cached_models, expected_models = count_model_covered_models(
        cached_keywords,
        model_ids,
        get_canonical_model,
    )
    fresh_models_48h, _ = count_model_covered_models(
        fresh_keywords,
        model_ids,
        get_canonical_model,
    )
    stale_models_48h = max(0, expected_models - fresh_models_48h)
    latest_dt = max((dt for _, dt in cache_rows if dt), default=None)
    latest_crawl = latest_dt.isoformat() if latest_dt else None

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
            "error_message": "后台任务失败，请联系管理员" if r.error_message else None,
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
        crawl_expected_models=expected_models,
        crawl_fresh_models_48h=fresh_models_48h,
        crawl_stale_models_48h=stale_models_48h,
        total_items=total_items,
        total_bargains=total_bargains,
        bargains_by_brand=bargains_by_brand,
        price_history_count=price_history_count,
        recent_batches=recent_batches,
        brands=brands,
        model_coverage_cached=cached_models,
        model_coverage_expected=expected_models,
    )
