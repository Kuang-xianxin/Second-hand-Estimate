import json
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import asdict

from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.redis_client import get_redis, redis_key, LIST_ALL_KEYWORDS
from app.models.cache import CCDPriceCache
from app.models.price_history import PriceHistory

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 5400  # 1.5 小时


def _dt_to_str(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _serialize_cache(data: dict) -> str:
    """将缓存数据序列化为 JSON 字符串。"""
    out = dict(data)
    for f in ("crawled_at", "updated_at"):
        if f in out and out[f]:
            out[f] = _dt_to_str(out[f])
    return json.dumps(out, ensure_ascii=False)


def _deserialize_cache(raw: str) -> dict:
    """将 JSON 反序列化为缓存数据。"""
    return json.loads(raw)


async def get_cache_l1(keyword: str) -> Optional[dict]:
    """
    L1 缓存查询（Redis）：< 1ms
    命中则返回缓存数据，未命中返回 None。
    """
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(redis_key(keyword))
        if raw:
            return _deserialize_cache(raw)
    except Exception as e:
        logger.warning(f"Redis L1 查询失败: {e}")
    return None


async def set_cache_l1(keyword: str, data: dict, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """
    L1 缓存写入（Redis）：TTL 1.5 小时。
    返回是否写入成功。
    """
    r = await get_redis()
    if r is None:
        return False
    try:
        serialized = _serialize_cache(data)
        await r.setex(redis_key(keyword), ttl, serialized)
        return True
    except Exception as e:
        logger.warning(f"Redis L1 写入失败: {e}")
        return False


async def invalidate_cache_l1(keyword: str) -> bool:
    """L1 缓存失效（Redis）：删除指定关键词的缓存。"""
    r = await get_redis()
    if r is None:
        return False
    try:
        await r.delete(redis_key(keyword))
        return True
    except Exception as e:
        logger.warning(f"Redis L1 删除失败: {e}")
        return False


async def warm_cache_l1_batch(keywords: list[str], session: AsyncSession) -> int:
    """
    缓存预热：将一批关键词从 L2 批量回填 L1。
    爬取完成后调用，避免冷启动。
    返回成功预热的数量。
    """
    r = await get_redis()
    if r is None:
        return 0
    count = 0
    pipe = r.pipeline()
    for kw in keywords:
        result = await session.execute(
            select(CCDPriceCache).where(CCDPriceCache.keyword == kw)
        )
        record = result.scalar_one_or_none()
        if record:
            data = {
                "keyword": record.keyword,
                "display_name": record.display_name,
                "brand": record.brand,
                "base_price": record.base_price,
                "price_min": record.price_min,
                "price_max": record.price_max,
                "median_price": record.median_price,
                "sample_count": record.sample_count,
                "is_xd_card": record.is_xd_card,
                "xd_card_bundle_count": record.xd_card_bundle_count,
                "crawled_at": _dt_to_str(record.crawled_at),
                "updated_at": _dt_to_str(record.updated_at),
            }
            pipe.setex(redis_key(kw), CACHE_TTL_SECONDS, _serialize_cache(data))
            count += 1
    try:
        await pipe.execute()
    except Exception as e:
        logger.warning(f"Redis L1 批量预热失败: {e}")
        return 0
    return count


async def get_cache_l2(keyword: str, session: AsyncSession) -> Optional[dict]:
    """
    L2 缓存查询（PostgreSQL ccd_price_cache）：5-20ms
    命中则返回缓存数据，并异步回填 L1。
    """
    result = await session.execute(
        select(CCDPriceCache).where(CCDPriceCache.keyword == keyword)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    data = {
        "keyword": record.keyword,
        "display_name": record.display_name,
        "brand": record.brand,
        "base_price": record.base_price,
        "price_min": record.price_min,
        "price_max": record.price_max,
        "median_price": record.median_price,
        "sample_count": record.sample_count,
        "avg_price": record.avg_price,
        "is_xd_card": record.is_xd_card,
        "xd_card_bundle_count": record.xd_card_bundle_count,
        "crawled_at": _dt_to_str(record.crawled_at),
        "updated_at": _dt_to_str(record.updated_at),
    }

    # 异步回填 L1（不阻塞主流程）
    import asyncio
    asyncio.create_task(set_cache_l1(keyword, data))
    return data


async def upsert_cache_l2(data: dict, session: AsyncSession) -> bool:
    """
    L2 缓存写入（PostgreSQL ccd_price_cache）：批量 upsert。
    data 应包含 keyword, base_price, price_min, price_max 等字段。
    """
    try:
        result = await session.execute(
            select(CCDPriceCache).where(CCDPriceCache.keyword == data["keyword"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
        else:
            session.add(CCDPriceCache(**data))
        return True
    except Exception as e:
        logger.warning(f"L2 缓存写入失败: {e}")
        return False


async def get_cache_l3(keyword: str, session: AsyncSession, limit: int = 30) -> list[dict]:
    """
    L3 缓存查询（PostgreSQL price_history）：价格历史趋势。
    返回最近 N 条历史记录。
    """
    result = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.keyword == keyword)
        .order_by(PriceHistory.crawled_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "keyword": r.keyword,
            "base_price": r.base_price,
            "median_price": r.median_price,
            "price_min": r.price_min,
            "price_max": r.price_max,
            "sample_count": r.sample_count,
            "trend": r.trend,
            "crawled_at": _dt_to_str(r.crawled_at),
        }
        for r in records
    ]


async def append_price_history(data: dict, session: AsyncSession) -> bool:
    """写入一条价格历史记录。"""
    try:
        session.add(PriceHistory(**data))
        return True
    except Exception as e:
        logger.warning(f"价格历史写入失败: {e}")
        return False


async def get_cache_status(session: AsyncSession) -> dict:
    """
    返回缓存系统整体状态：
    - L1: Redis 连接状态
    - L2: ccd_price_cache 覆盖型号数、最新爬取时间
    - L3: price_history 条数
    """
    r = await get_redis()
    l1_ok = False
    try:
        if r:
            await r.ping()
            l1_ok = True
    except Exception:
        pass

    l2_result = await session.execute(
        select(
            sql_func.count(CCDPriceCache.id),
            sql_func.max(CCDPriceCache.crawled_at),
        )
    )
    l2_row = l2_result.one()
    l2_count = l2_row[0] or 0
    l2_latest = _dt_to_str(l2_row[1])

    l3_result = await session.execute(
        select(sql_func.count(PriceHistory.id))
    )
    l3_count = l3_result.scalar() or 0

    return {
        "l1": {"ok": l1_ok, "engine": "redis"},
        "l2": {
            "ok": True,
            "engine": "postgresql",
            "total_keywords": l2_count,
            "latest_crawl": l2_latest,
        },
        "l3": {
            "total_records": l3_count,
        },
    }
