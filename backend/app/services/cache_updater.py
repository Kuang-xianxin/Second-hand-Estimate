"""
缓存更新逻辑——定时任务完成后，将爬取结果批量写入缓存表 + L1 预热。
"""
import logging
from datetime import datetime
from typing import List, Dict

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cache import CCDPriceCache
from app.models.price_history import PriceHistory
from app.services.cache import (
    upsert_cache_l2,
    warm_cache_l1_batch,
    CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)


def _dt_to_str(dt) -> str:
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt) if dt else ""


def _match_items_to_keyword(keyword: str, items: list) -> list:
    """按 canonical model 等价关键词匹配 item，解决 canonical ID 与 item.query_keyword 不一致的问题。"""
    from app.services.keyword_tier import get_canonical_keyword, get_model_keywords_for_pricing
    equivalent_kw = set(kw.strip().lower() for kw in get_model_keywords_for_pricing(keyword))
    canonical = get_canonical_keyword(keyword)
    matched = []
    for item in items:
        item_kw = (getattr(item, "query_keyword", "") or getattr(item, "keyword", "")).strip().lower()
        if item_kw in equivalent_kw or get_canonical_keyword(item_kw) == canonical:
            matched.append(item)
    if not matched:
        keyword_lower = keyword.lower()
        matched = [i for i in items if keyword_lower in getattr(i, "title", "").lower()]
    return matched


def compute_price_for_keyword(
    keyword: str,
    items: list,
) -> dict:
    """
    为单个关键词计算估价结果。
    复用 /api/valuate/stream 的本地筛选与 pricing.py 算法逻辑，但返回 dict 格式。
    """
    from app.services.pricing import calculate_price
    from app.services.bargain import (
        detect_xd_card_model_from_items,
        filter_target_items,
        strip_xd_card_prices,
    )

    keyword_items = _match_items_to_keyword(keyword, items)

    if not keyword_items:
        return {}

    display_keyword = _get_display_name(keyword) or keyword
    # WHY: scheduler pricing passes canonical keys such as tier:olympus:0544;
    # filtering with that key loses the real model token (FE25/S7100/A2400)
    # and lets unrelated lenses/service ads pollute the price median.
    filtered_items = filter_target_items(keyword_items, display_keyword)

    if not filtered_items:
        logger.info(
            "缓存估价跳过 %s：%s 条原始样本经 stream 同源筛选后无有效整机样本",
            keyword,
            len(keyword_items),
        )
        return {}

    is_xd = False
    xd_bundle_count = 0
    items_for_algo = filtered_items

    try:
        from app.services.xd_card_models import is_xd_card_model
        is_xd = is_xd_card_model(display_keyword) or is_xd_card_model(keyword)
    except ImportError:
        pass

    if is_xd and detect_xd_card_model_from_items(filtered_items, keyword=display_keyword):
        camera_only, bundle_infos = strip_xd_card_prices(filtered_items, query_keyword=display_keyword)
        xd_bundle_count = len(bundle_infos)
        items_for_algo = camera_only

    if not items_for_algo:
        logger.info(
            "缓存估价跳过 %s：XD 拆价后无纯相机样本",
            keyword,
        )
        return {}

    prices = [float(getattr(i, "price", 0)) for i in items_for_algo]
    quality_scores = [float(getattr(i, "quality_score", 50) or 50) for i in items_for_algo]

    pricing = calculate_price(prices, quality_scores=quality_scores)

    avg_price = round(sum(prices) / len(prices), 2) if prices else 0
    import statistics
    median_price = round(statistics.median(prices), 2) if prices else 0

    return {
        "keyword": keyword,
        "display_name": display_keyword,
        "brand": extract_brand(keyword),
        "series": extract_series(keyword),
        "base_price": pricing.base_price,
        "price_min": pricing.price_min,
        "price_max": pricing.price_max,
        "median_price": median_price,
        "avg_price": avg_price,
        "sample_count": pricing.sample_count,
        "is_xd_card": is_xd,
        "xd_card_bundle_count": xd_bundle_count,
        "crawled_at": datetime.utcnow(),
    }


def _get_display_name(keyword: str) -> str:
    from app.services.keyword_tier import get_display_name
    return get_display_name(keyword)


def extract_brand(keyword: str) -> str:
    """从关键词提取品牌名。"""
    low = keyword.lower()
    brands = [
        ("canon", "佳能"),
        ("nikon", "尼康"),
        ("sony", "索尼"),
        ("fujifilm", "富士"),
        ("fuji", "富士"),
        ("olympus", "奥林巴斯"),
        ("panasonic", "松下"),
        ("lumix", "松下"),
        ("casio", "卡西欧"),
        ("samsung", "三星"),
        ("pentax", "宾得"),
        ("kodak", "柯达"),
    ]
    for en, cn in brands:
        if en in low or cn in keyword:
            return en
    return ""


def extract_series(keyword: str) -> str:
    """从关键词提取系列名。"""
    low = keyword.lower()
    series_map = [
        ("ixus", "IXUS"),
        ("powershot", "PowerShot"),
        ("coolpix", "Coolpix"),
        ("cybershot", "Cyber-shot"),
        ("dsc-", "Cyber-shot"),
        ("finepix", "FinePix"),
        ("lumix", "Lumix"),
        ("exilim", "Exilim"),
        ("optio", "Optio"),
        ("easyshare", "EasyShare"),
        ("mu ", "μ"),
        ("stylus", "Stylus"),
    ]
    for pattern, name in series_map:
        if pattern in low:
            return name
    return ""


async def batch_update_cache(
    keyword_prices: Dict[str, dict],
    keywords: List[str],
    items: list,
    session: AsyncSession,
) -> tuple[int, int]:
    """
    批量更新 L2 缓存（ccd_price_cache 表）。
    返回 (成功数, 失败数)。
    """
    success_count = 0
    fail_count = 0

    for keyword in keywords:
        if keyword not in keyword_prices:
            # 没有价格数据，跳过
            fail_count += 1
            continue

        data = keyword_prices[keyword]
        ok = await upsert_cache_l2(data, session)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    # 写入价格历史（每个关键词取最新一条）
    for keyword, data in keyword_prices.items():
        if data.get("base_price", 0) > 0:
            history_data = {
                "keyword": keyword,
                "base_price": data["base_price"],
                "median_price": data.get("median_price", 0),
                "price_min": data.get("price_min", 0),
                "price_max": data.get("price_max", 0),
                "sample_count": data.get("sample_count", 0),
                "crawled_at": datetime.utcnow(),
            }
            try:
                session.add(PriceHistory(**history_data))
            except Exception as e:
                logger.warning(f"价格历史写入失败 {keyword}: {e}")

    try:
        await session.commit()
    except Exception as e:
        logger.warning(f"批量缓存更新提交失败: {e}")
        await session.rollback()

    logger.info(f"缓存批量更新完成：成功 {success_count}，失败 {fail_count}")
    return success_count, fail_count


async def backfill_missing_cache_from_crawled_items(
    keywords: List[str],
    session: AsyncSession,
    *,
    max_items_per_keyword: int = 200,
) -> tuple[int, int]:
    """Use stored crawled_items to backfill missing ccd_price_cache rows."""
    from app.models.item import CrawledItem
    from app.services.keyword_tier import (
        get_canonical_keyword,
        get_model_keywords_for_pricing,
    )

    canonical_keywords = list(dict.fromkeys(get_canonical_keyword(kw) for kw in keywords))
    if not canonical_keywords:
        return 0, 0

    result = await session.execute(
        select(CCDPriceCache.keyword).where(CCDPriceCache.keyword.in_(canonical_keywords))
    )
    existing = set(result.scalars().all())
    missing = [kw for kw in canonical_keywords if kw not in existing]
    if not missing:
        return 0, 0

    keyword_prices: Dict[str, dict] = {}
    skipped_count = 0
    for canonical in missing:
        aliases = list(dict.fromkeys(
            get_model_keywords_for_pricing(canonical) + [canonical]
        ))
        result = await session.execute(
            select(CrawledItem)
            .where(
                or_(
                    CrawledItem.query_keyword.in_(aliases),
                    CrawledItem.keyword.in_(aliases),
                ),
                CrawledItem.is_valid.is_not(False),
            )
            .order_by(CrawledItem.crawled_at.desc())
            .limit(max_items_per_keyword)
        )
        items = result.scalars().all()
        if not items:
            skipped_count += 1
            continue
        data = compute_price_for_keyword(canonical, items)
        if data and data.get("base_price", 0) > 0:
            keyword_prices[canonical] = data
        else:
            skipped_count += 1

    if not keyword_prices:
        logger.info("缓存回填跳过：%s 个缺失型号在 crawled_items 中没有可估价样本", len(missing))
        return 0, len(missing)

    # WHY: sweep only crawls a tiny slice per run; replaying already persisted
    # samples prevents ccd_price_cache coverage from lagging far behind raw data.
    success_count, fail_count = await batch_update_cache(
        keyword_prices,
        list(keyword_prices.keys()),
        [],
        session,
    )
    return success_count, fail_count + skipped_count


async def write_crawled_items(
    items: list,
    session,
) -> int:
    """
    将 XianyuItem 列表批量写入 crawled_items 表（upsert by item_id）。
    返回实际写入/更新数量。
    """
    import json as _json
    from app.models.item import CrawledItem

    if not items:
        return 0

    session.autoflush = False
    written = 0
    for item in items:
        try:
            item_id = getattr(item, "item_id", "")
            if not item_id:
                continue

            result = await session.execute(
                select(CrawledItem).where(CrawledItem.item_id == item_id)
            )
            existing = result.scalar_one_or_none()

            images_val = getattr(item, "images", []) or []
            if isinstance(images_val, list):
                images_val = _json.dumps(images_val, ensure_ascii=False)
            quality_flags_val = getattr(item, "quality_flags", []) or []
            if isinstance(quality_flags_val, list):
                quality_flags_val = _json.dumps(quality_flags_val, ensure_ascii=False)

            if existing:
                existing.keyword = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
                existing.query_keyword = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
                existing.title = getattr(item, "title", "")
                existing.price = float(getattr(item, "price", 0))
                existing.condition = getattr(item, "condition", "")
                existing.description = getattr(item, "description", "")
                existing.sold = getattr(item, "sold", False)
                existing.images = images_val
                existing.quality_score = getattr(item, "quality_score", None)
                existing.quality_flags = quality_flags_val
                existing.url = getattr(item, "url", "")
            else:
                session.add(CrawledItem(
                    item_id=item_id,
                    keyword=getattr(item, "query_keyword", "") or getattr(item, "keyword", ""),
                    query_keyword=getattr(item, "query_keyword", "") or getattr(item, "keyword", ""),
                    title=getattr(item, "title", ""),
                    price=float(getattr(item, "price", 0)),
                    condition=getattr(item, "condition", ""),
                    description=getattr(item, "description", ""),
                    sold=getattr(item, "sold", False),
                    images=images_val,
                    quality_score=getattr(item, "quality_score", None),
                    quality_flags=quality_flags_val,
                    url=getattr(item, "url", ""),
                ))
            written += 1
        except Exception as e:
            logger.warning(f"写入 crawled_items 失败 item_id={getattr(item, 'item_id', '?')}: {e}")

    try:
        await session.commit()
    except Exception as e:
        logger.warning(f"crawled_items 提交失败: {e}")
        await session.rollback()

    logger.info(f"crawled_items 写入完成：{written} 条")
    return written


async def warm_l1_cache(
    keywords: List[str],
    keyword_prices: Dict[str, dict],
    session: AsyncSession,
) -> int:
    """
    将热门型号预热到 L1（Redis）。
    返回成功预热数量。
    """
    if not keywords:
        return 0

    # 优先预热有价格数据的关键词
    warm_keywords = [kw for kw in keywords if kw in keyword_prices]
    if not warm_keywords:
        warm_keywords = keywords[:100]  # 最多预热 100 个

    return await warm_cache_l1_batch(warm_keywords, session)
