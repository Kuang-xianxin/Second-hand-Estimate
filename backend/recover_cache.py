"""
恢复脚本：从 crawled_items 表已有的数据中计算估价并写入缓存。
用于定时任务中断后的数据恢复。
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy import select, inspect

from app.models.database import AsyncSessionLocal, init_db
from app.models.item import CrawledItem
from app.services.cache_updater import compute_price_for_keyword, batch_update_cache
from app.services.bargain_detector import detect_global_bargains, replace_global_bargains

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


async def recover_cache():
    """从 crawled_items 恢复缓存数据。"""
    await init_db()

    async with AsyncSessionLocal() as session:
        # 读取所有已爬取商品
        result = await session.execute(select(CrawledItem))
        items = result.scalars().all()
        logger.info(f"从 crawled_items 读取到 {len(items)} 条商品记录")

        if not items:
            logger.info("没有数据需要恢复")
            return

        # 按关键词分组
        keyword_items: dict = {}
        for item in items:
            kw = item.query_keyword or item.keyword or ''
            if not kw:
                continue
            keyword_items.setdefault(kw, []).append(item)

        logger.info(f"共 {len(keyword_items)} 个关键词")

        # 计算每个关键词的估价
        keyword_prices: dict = {}
        priced_count = 0
        for kw, kw_items in keyword_items.items():
            result = compute_price_for_keyword(kw, kw_items)
            if result and result.get("base_price", 0) > 0:
                keyword_prices[kw] = result
                priced_count += 1

        logger.info(f"估价计算完成：{priced_count}/{len(keyword_items)} 个关键词有有效价格")

        # 收集所有商品（用于全局捡漏检测）
        all_items = [item for items in keyword_items.values() for item in items]

        # 检测全局捡漏（detect_global_bargains 需要 {kw: base_price} 格式）
        bargains = detect_global_bargains(
            all_items,
            {kw: data["base_price"] for kw, data in keyword_prices.items()}
        )
        logger.info(f"检测到 {len(bargains)} 个全局捡漏")

        # 写入缓存
        keywords_list = list(keyword_prices.keys())
        success, fail = await batch_update_cache(
            keyword_prices, keywords_list, all_items, session
        )
        logger.info(f"缓存写入完成：成功 {success}，失败 {fail}")

        # 写入全局捡漏
        if bargains:
            batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M_recover")
            await replace_global_bargains(bargains, batch_id, session)
            logger.info(f"全局捡漏写入完成：{len(bargains)} 条")

        logger.info("恢复完成！")


if __name__ == "__main__":
    asyncio.run(recover_cache())
