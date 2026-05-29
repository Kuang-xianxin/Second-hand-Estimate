"""
手动触发全量爬取 / 金丝雀测试脚本。

用法:
    python trigger_crawl.py --dry-run                        # 金丝雀测试（推荐先用）
    python trigger_crawl.py --keyword "ixus 130" --dry-run   # 单型号金丝雀
    python trigger_crawl.py --max-keywords 3 --dry-run       # 限制 3 个关键词
    python trigger_crawl.py --brand canon --max-keywords 5   # 品牌过滤 + 限制
    python trigger_crawl.py                                  # 全量爬取（需 .env 中开启）

此脚本绕过 Redis 分布式锁，直接执行爬取流程：
1. 爬取 CCD 关键词
2. 算法估价
3. 全局捡漏检测
4. 写入缓存 + 捡漏广场
"""
import argparse
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)

logger = logging.getLogger("trigger_crawl")


BRAND_FILTERS = {
    "canon": ["canon", "佳能", "ixus", "powershot", "ixy", "kiss"],
    "nikon": ["nikon", "尼康", "coolpix"],
    "sony": ["sony", "索尼", "cybershot", "dsc"],
    "fujifilm": ["fuji", "富士", "finepix"],
    "fuji": ["fuji", "富士", "finepix", "fujifilm"],
    "olympus": ["olympus", "奥林巴斯", "mju", "stylus"],
    "panasonic": ["panasonic", "松下", "lumix"],
    "casio": ["casio", "卡西欧", "exilim"],
    "ricoh": ["ricoh", "理光"],
    "samsung": ["samsung", "三星"],
    "pentax": ["pentax", "宾得"],
    "kodak": ["kodak", "柯达"],
    "leica": ["leica", "徕卡"],
    "minolta": ["minolta", "美能达"],
    "kyocera": ["kyocera", "京瓷"],
    "sigma": ["sigma", "适马"],
}


def filter_keywords(keywords: list[str], brand: str = None, keyword: str = None,
                    max_keywords: int = 0) -> list[str]:
    """按条件过滤关键词列表。"""
    if keyword:
        kw_lower = keyword.lower()
        filtered = [kw for kw in keywords if kw_lower in kw.lower()]
        logger.info(f"关键词过滤「{keyword}」: {len(keywords)} -> {len(filtered)}")
        return filtered

    if brand and brand.lower() in BRAND_FILTERS:
        terms = BRAND_FILTERS[brand.lower()]
        filtered = [kw for kw in keywords
                     if any(t in kw.lower() for t in terms)]
        logger.info(f"品牌过滤「{brand}」: {len(keywords)} -> {len(filtered)}")
        return filtered

    if max_keywords and max_keywords > 0 and len(keywords) > max_keywords:
        logger.info(f"关键词限制: {len(keywords)} -> {max_keywords}")
        return keywords[:max_keywords]

    return keywords


async def main():
    parser = argparse.ArgumentParser(description="CCD 全量爬取 / 金丝雀测试")
    parser.add_argument("--brand", type=str, help="品牌过滤 (canon/nikon/sony/...)")
    parser.add_argument("--keyword", type=str, help="单个型号关键词过滤")
    parser.add_argument("--max-keywords", type=int, default=0, help="最大关键词数量（0=全部）")
    parser.add_argument("--limit", type=int, default=0, help="每关键词最大商品数（0=取配置值）")
    parser.add_argument("--max-pages", type=int, default=0, help="每关键词最大翻页数（0=取配置值）")
    parser.add_argument("--concurrency", type=int, default=0, help="并发数（0=取配置值）")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不写入数据库")
    args = parser.parse_args()

    from app.models.database import AsyncSessionLocal, init_db
    from app.services.ccd_keywords import get_all_keywords, get_keyword_count
    from app.services.crawl_worker import crawl_all_ccd_models
    from app.services.cache_updater import compute_price_for_keyword, batch_update_cache, write_crawled_items
    from app.services.bargain_detector import detect_global_bargains, replace_global_bargains
    from app.models.crawl_status import CrawlStatus
    from app.config import settings
    from datetime import datetime, timezone
    from sqlalchemy import select

    await init_db()

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    mode = "金丝雀测试" if (args.brand or args.keyword) else "全量爬取"
    if args.dry_run:
        mode += "（dry-run）"
    logger.info(f"[{mode}] 批次 {batch_id} 开始")

    session_factory = lambda: AsyncSessionLocal()

    # Step 1: 记录开始状态（dry-run 跳过）
    if not args.dry_run:
        async with session_factory() as session:
            status = CrawlStatus(
                batch_id=batch_id,
                started_at=datetime.now(timezone.utc),
                status="running",
            )
            session.add(status)
            await session.commit()
            logger.info("爬取状态已记录")

    # Step 2: 获取并过滤关键词
    all_keywords = get_all_keywords()
    keywords = filter_keywords(
        all_keywords,
        brand=args.brand,
        keyword=args.keyword,
        max_keywords=args.max_keywords,
    )
    if not keywords:
        logger.error("没有匹配的关键词，任务终止")
        return
    logger.info(f"共 {len(keywords)} 个关键词（全库 {get_keyword_count()} 个唯一型号）")

    # Step 3: 爬取（canary 模式限制）
    if args.limit > 0:
        settings.max_items_per_query = args.limit
        if args.max_pages <= 0:
            settings.max_pages_per_query = min(settings.max_pages_per_query, max(1, args.limit // 24))
    if args.max_pages > 0:
        settings.max_pages_per_query = args.max_pages
    if args.limit > 0 or args.max_pages > 0:
        logger.info(f"canary 模式: max_items={settings.max_items_per_query}, max_pages={settings.max_pages_per_query}")

    concurrency = args.concurrency if args.concurrency > 0 else None
    logger.info(f"开始爬取闲鱼数据（{len(keywords)} 关键词）...")
    crawl_report = await crawl_all_ccd_models(keywords, concurrency=concurrency)
    logger.info(
        f"爬取完成：{crawl_report.success_count} 成功 / {crawl_report.fail_count} 失败，"
        f"共 {len(crawl_report.all_items)} 条去重商品"
    )

    # 登录/风控状态报告
    if crawl_report.login_required_count > 0:
        logger.error(
            f"登录态缺失：{crawl_report.login_required_count} 个关键词返回了登录页！"
            f"请运行 http://localhost:{settings.backend_port}/open-xianyu-login 重新登录，"
            f"或检查 backend/xianyu_storage_state.json 是否有效。"
        )
    if crawl_report.risk_detected_count > 0:
        logger.error(
            f"风控触发：{crawl_report.risk_detected_count} 个关键词触发了风控验证。"
            f"请降低并发和频率，等待一段时间后再试。"
        )

    if not crawl_report.all_items:
        reason_parts = ["没有爬到任何商品"]
        if crawl_report.login_required_count > 0:
            reason_parts.append(f"（{crawl_report.login_required_count} 个关键词需登录）")
        if crawl_report.risk_detected_count > 0:
            reason_parts.append(f"（{crawl_report.risk_detected_count} 个关键词触发风控）")
        if crawl_report.fail_count > 0:
            reason_parts.append(f"（{crawl_report.fail_count} 个关键词爬取失败）")
        logger.error("".join(reason_parts) + "，任务终止")
        if not args.dry_run:
            async with session_factory() as session:
                result = await session.execute(
                    select(CrawlStatus).where(CrawlStatus.batch_id == batch_id))
                record = result.scalar_one_or_none()
                if record:
                    record.finished_at = datetime.now(timezone.utc)
                    record.status = "failed"
                    record.error_message = "没有爬到任何商品"
                    await session.commit()
        return

    # 预览前5件商品样本
    for i, item in enumerate(crawl_report.all_items[:5]):
        kw = getattr(item, "query_keyword", "") or "?"
        logger.info(f"  样本#{i+1}: [{kw}] {item.title[:50]}... ¥{item.price}")

    # Step 4: 算法估价（按 query_keyword 分组）
    logger.info("开始算法估价...")
    keyword_prices = {}
    items_by_keyword = {}
    for item in crawl_report.all_items:
        kw = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
        if not kw:
            continue
        items_by_keyword.setdefault(kw, []).append(item)

    logger.info(f"分组结果：{len(items_by_keyword)} 个关键词组，各组样本数: "
                f"{[len(v) for v in list(items_by_keyword.values())[:10]]}")

    for kw, items in items_by_keyword.items():
        result = compute_price_for_keyword(kw, items)
        if result and result.get("base_price", 0) > 0:
            keyword_prices[kw] = result

    logger.info(f"估价完成：{len(keyword_prices)} 个型号有有效价格")

    # Step 5: 全局捡漏检测
    logger.info("开始全局捡漏检测...")
    bargain_prices = {kw: data["base_price"] for kw, data in keyword_prices.items()}
    bargains = detect_global_bargains(crawl_report.all_items, bargain_prices)
    logger.info(f"检测到 {len(bargains)} 件全局捡漏")
    for b in bargains[:5]:
        logger.info(f"  捡漏: [{b.keyword}] {b.title[:40]}... 售价¥{b.current_price} "
                    f"→ 利润¥{b.profit_estimate}")

    if args.dry_run:
        logger.info(f"[dry-run 完成] 批次 {batch_id}，总计 {len(crawl_report.all_items)} 条商品，"
                    f"{len(bargains)} 件捡漏（未写库）")
        return

    # Step 6: 写入数据库
    logger.info("写入数据库...")
    async with session_factory() as session:
        # 先写入原始商品表
        item_count = await write_crawled_items(crawl_report.all_items, session)
        logger.info(f"原始商品写入完成（{item_count} 条）")

        await batch_update_cache(
            keyword_prices,
            list(keyword_prices.keys()),
            crawl_report.all_items,
            session,
        )
        logger.info(f"缓存写入完成（{len(keyword_prices)} 个型号）")

        count = await replace_global_bargains(bargains, batch_id, session)
        logger.info(f"全局捡漏表写入 {count} 条")

        result = await session.execute(
            select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.finished_at = datetime.now(timezone.utc)
            record.status = "completed"
            record.total_keywords = crawl_report.total_keywords
            record.success_count = crawl_report.success_count
            record.fail_count = crawl_report.fail_count
            record.total_items = len(crawl_report.all_items)
            record.bargains_found = len(bargains)
            await session.commit()

    logger.info(f"[完成] 批次 {batch_id}，总计 {len(crawl_report.all_items)} 条商品，"
                f"{len(bargains)} 件捡漏")


if __name__ == "__main__":
    asyncio.run(main())
