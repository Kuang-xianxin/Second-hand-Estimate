"""
全局捡漏检测——定时任务完成后，从全量爬取商品中检测所有型号的捡漏机会。
"""
import logging
import json
from dataclasses import dataclass

from app.services.bargain import (
    _extract_ccd_brand,
    _is_risky_by_category,
    _infer_category,
    _is_model_mismatch,
    _is_xd_bundle_from_text,
    _get_xd_card_value,
    XD_CARD_PRICES,
)
from app.models.global_bargain import GlobalBargain
from app.config import settings

logger = logging.getLogger(__name__)

BARGAIN_MIN_PROFIT = 80  # 最低绝对利润 80 元
BARGAIN_MIN_DISCOUNT = 0.3  # 或折扣率 >= 30%


@dataclass
class GlobalBargainRecord:
    item_id: str
    keyword: str
    brand: str
    title: str
    current_price: float
    base_price: float
    profit_estimate: float
    discount_rate: float
    condition: str
    quality_score: float
    is_xd_card: bool
    xd_card_size: str
    xd_card_value: float
    url: str
    image_url: str


def detect_xd_bonus(item) -> tuple[str, float]:
    """从单个商品中检测 xD 卡捆绑，返回 (card_size, card_value)。"""
    is_bundle, card_size = _is_xd_bundle_from_text(item, "")
    if not card_size:
        return "", 0.0
    card_value = _get_xd_card_value(card_size)
    return card_size, card_value


def extract_first_image(images) -> str:
    """从图片列表中提取第一张图片 URL。"""
    if not images:
        return ""
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            return ""
    if isinstance(images, list) and images:
        return str(images[0])
    return ""


def detect_global_bargains(
    all_items: list,
    keyword_prices: dict[str, float],
    keyword_qualities: dict[str, float] = None,
) -> list[GlobalBargainRecord]:
    """
    全局捡漏检测：从全部爬取商品中检测所有型号的捡漏机会。

    规则：总利润 >= 80 元 或 (利润 / 基准价) >= 30%

    全局捡漏存储在 global_bargains 表，与条件捡漏（bargain_alerts 表）严格区分。
    """
    global_bargains: list[GlobalBargainRecord] = []
    qualities = keyword_qualities or {}

    for item in all_items:
        if getattr(item, "sold", False):
            continue
        if not getattr(item, "is_valid", True):
            continue

        keyword = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
        base_price = keyword_prices.get(keyword, 0)
        if base_price <= 0:
            try:
                from app.services.keyword_tier import get_canonical_keyword
                base_price = keyword_prices.get(get_canonical_keyword(keyword), 0)
            except Exception:
                base_price = 0
        if base_price <= 0:
            continue

        category = _infer_category(keyword)
        if _is_risky_by_category(item, category):
            continue
        if _is_model_mismatch(keyword, getattr(item, "title", ""), category):
            continue

        card_size, card_value = detect_xd_bonus(item)
        profit = base_price - float(getattr(item, "price", 0))
        total_profit = profit + card_value

        if total_profit < BARGAIN_MIN_PROFIT and (profit / base_price) < BARGAIN_MIN_DISCOUNT:
            continue

        discount_rate = round(total_profit / base_price, 3) if base_price > 0 else 0
        brand = _extract_ccd_brand(getattr(item, "title", ""))
        quality_score = float(getattr(item, "quality_score", 50) or 50)
        condition = getattr(item, "condition", "") or ""

        global_bargains.append(GlobalBargainRecord(
            item_id=getattr(item, "item_id", ""),
            keyword=keyword,
            brand=brand,
            title=getattr(item, "title", ""),
            current_price=float(getattr(item, "price", 0)),
            base_price=base_price,
            profit_estimate=round(total_profit, 2),
            discount_rate=discount_rate,
            condition=condition,
            quality_score=quality_score,
            is_xd_card=bool(card_value > 0),
            xd_card_size=card_size,
            xd_card_value=round(card_value, 2),
            url=getattr(item, "url", ""),
            image_url=extract_first_image(getattr(item, "images", [])),
        ))

    global_bargains.sort(key=lambda x: x.profit_estimate, reverse=True)
    logger.info(f"全局捡漏检测完成：{len(global_bargains)} 件符合条件")
    return global_bargains


async def replace_global_bargains(
    records: list[GlobalBargainRecord],
    batch_id: str,
    session,
) -> int:
    """
    全量替换 global_bargains 表。
    先清空，再批量插入，返回实际写入数量。
    """
    from sqlalchemy import delete

    try:
        # 清空旧数据
        await session.execute(delete(GlobalBargain))
        await session.flush()

        # 批量插入新数据
        for record in records:
            session.add(GlobalBargain(
                item_id=record.item_id,
                keyword=record.keyword,
                brand=record.brand,
                title=record.title,
                current_price=record.current_price,
                base_price=record.base_price,
                profit_estimate=record.profit_estimate,
                discount_rate=record.discount_rate,
                condition=record.condition,
                quality_score=record.quality_score,
                is_xd_card=record.is_xd_card,
                xd_card_size=record.xd_card_size,
                xd_card_value=record.xd_card_value,
                url=record.url,
                image_url=record.image_url,
                refresh_batch=batch_id,
            ))

        await session.commit()
        logger.info(f"全局捡漏表全量替换完成：写入 {len(records)} 条")
        return len(records)
    except Exception as e:
        logger.error(f"全局捡漏表替换失败: {e}")
        await session.rollback()
        return 0


async def replace_global_bargains_for_keywords(
    records: list[GlobalBargainRecord],
    batch_id: str,
    keywords: list[str],
    session,
) -> int:
    """Replace bargains only for the model updated by a stable sweep worker."""
    from sqlalchemy import delete

    normalized = list({keyword.strip() for keyword in keywords if keyword.strip()})
    item_ids = list({record.item_id for record in records if record.item_id})
    try:
        if normalized:
            await session.execute(
                delete(GlobalBargain).where(GlobalBargain.keyword.in_(normalized))
            )
            await session.flush()
        if item_ids:
            await session.execute(
                delete(GlobalBargain).where(GlobalBargain.item_id.in_(item_ids))
            )
            await session.flush()

        for record in records:
            session.add(GlobalBargain(
                item_id=record.item_id,
                keyword=record.keyword,
                brand=record.brand,
                title=record.title,
                current_price=record.current_price,
                base_price=record.base_price,
                profit_estimate=record.profit_estimate,
                discount_rate=record.discount_rate,
                condition=record.condition,
                quality_score=record.quality_score,
                is_xd_card=record.is_xd_card,
                xd_card_size=record.xd_card_size,
                xd_card_value=record.xd_card_value,
                url=record.url,
                image_url=record.image_url,
                refresh_batch=batch_id,
            ))

        await session.commit()
        return len(records)
    except Exception as exc:
        logger.error("Incremental global bargain replacement failed: %s", exc)
        await session.rollback()
        return 0
