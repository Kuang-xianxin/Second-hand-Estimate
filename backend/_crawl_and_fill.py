"""
独立爬取+入库脚本：爬取 T0 热门型号并写入数据库。

用法：python _crawl_and_fill.py [--tier t0|t1] [--limit N] [--dry-run]
"""
import asyncio
import sys
import argparse
import logging
from pathlib import Path

backend_root = Path(__file__).parent
sys.path.insert(0, str(backend_root))

from app.models.database import init_db, AsyncSessionLocal
from app.services.keyword_tier import (
    KeywordTier, get_keywords_by_tier, get_canonical_keyword,
    get_tier_counts,
)
from app.services.crawl_worker import crawl_all_ccd_models, crawl_canary
from app.services.cache_updater import (
    compute_price_for_keyword, batch_update_cache,
    write_crawled_items, warm_l1_cache,
)
from app.services.bargain import filter_target_items
from app.services.bargain_detector import detect_global_bargains, replace_global_bargains
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("crawl_fill")


def _rule_filter_crawled_items(items: list) -> list:
    """Use the same lightweight rule filter as /valuate, without LLM or image analysis."""
    filtered: list = []
    for item in items:
        keyword = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
        if not keyword:
            filtered.append(item)
            continue
        # WHY: 后台库也不能吃出租/咨询/盲盒/独立配件样本；这里只复用规则筛，不跑 LLM/图片以适配 2核2G。
        if filter_target_items([item], keyword):
            filtered.append(item)
    return filtered


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default="t0", choices=["t0", "t1"])
    parser.add_argument("--limit", type=int, default=0, help="限制爬取关键词数量，0=全部")
    parser.add_argument("--dry-run", action="store_true", help="只检查配置和 canary，不实际爬取")
    parser.add_argument("--max-items", type=int, default=40, help="每个关键词最多爬取商品数")
    parser.add_argument("--concurrency", type=int, default=2, help="并发数")
    parser.add_argument("--batch-size", type=int, default=10, help="每批关键词数")
    args = parser.parse_args()

    tier = KeywordTier.T0_HOT if args.tier == "t0" else KeywordTier.T1_WARM
    tier_label = args.tier

    # 0. 初始化数据库
    logger.info("初始化数据库...")
    await init_db()

    # 1. 统计信息
    counts = get_tier_counts()
    keywords = get_keywords_by_tier(tier)
    logger.info(f"关键词统计: T0={counts['t0']}, T1={counts['t1']}, T2={counts['t2']}")
    logger.info(f"当前层级 [{tier_label}] 共 {len(keywords)} 个关键词")

    if args.limit > 0:
        keywords = keywords[:args.limit]
        logger.info(f"限制为 {len(keywords)} 个关键词")

    # 2. Canary 预检
    logger.info("执行 Canary 预检...")
    canary_ok, canary_reason, canary_debug = await crawl_canary()
    logger.info(f"Canary: ok={canary_ok}, reason={canary_reason}")
    if not canary_ok:
        logger.error(f"Canary 预检失败！跳过爬取。原因: {canary_reason}")
        if args.dry_run:
            return
        # 不让 canary 失败阻止尝试
        logger.warning("继续尝试爬取...")

    if args.dry_run:
        logger.info("[dry-run] 跳过实际爬取")
        return

    # 3. 爬取
    logger.info(f"开始爬取 [{tier_label}]：{len(keywords)} 个关键词，并发={args.concurrency}，每词最多 {args.max_items} 条")
    report = await crawl_all_ccd_models(
        keywords,
        concurrency=args.concurrency,
        batch_size=args.batch_size,
        tier=tier_label,
        max_items_per_kw=args.max_items,
        skip_canary=True,  # 上面已手动跑过
    )

    logger.info(f"爬取完成: 成功 {report.success_count}, 失败 {report.fail_count}, "
                f"熔断 {report.aborted}, 登录失效 {report.login_required_count}, "
                f"风控 {report.risk_detected_count}, 商品数 {len(report.all_items)}")

    if not report.all_items:
        logger.error("没有爬到任何商品，终止")
        return

    filtered_items = _rule_filter_crawled_items(report.all_items)
    logger.info(f"规则筛选: 原始 {len(report.all_items)} 条，保留 {len(filtered_items)} 条，剔除 {len(report.all_items) - len(filtered_items)} 条")

    if not filtered_items:
        logger.error("规则筛选后没有可入库商品，终止")
        return

    # 4. 写入规则筛后的商品表
    async with AsyncSessionLocal() as session:
        written = await write_crawled_items(filtered_items, session)
        logger.info(f"规则筛后商品写入: {written} 条")

    # 5. 按 canonical model 归并
    items_by_canonical: dict[str, list] = {}
    for item in filtered_items:
        kw = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
        if not kw:
            continue
        canonical = get_canonical_keyword(kw)
        items_by_canonical.setdefault(canonical, []).append(item)
    logger.info(f"归并为 {len(items_by_canonical)} 个 canonical model")

    # 6. 估值
    keyword_prices: dict[str, dict] = {}
    for canonical, items in items_by_canonical.items():
        result = compute_price_for_keyword(canonical, items)
        if result and result.get("base_price", 0) > 0:
            keyword_prices[canonical] = result

    logger.info(f"有效估价: {len(keyword_prices)} 个 model")

    if not keyword_prices:
        logger.error("没有有效估价结果，终止")
        return

    # 7. 捡漏检测 (T0 才做)
    bargains = []
    if tier in (KeywordTier.T0_HOT, KeywordTier.T1_WARM):
        bargain_prices = {kw: data["base_price"] for kw, data in keyword_prices.items()}
        bargains = detect_global_bargains(filtered_items, bargain_prices)
        logger.info(f"检测到 {len(bargains)} 件捡漏")

    # 8. 写入缓存 + 捡漏表
    async with AsyncSessionLocal() as session:
        success_count, fail_count = await batch_update_cache(
            keyword_prices, list(keyword_prices.keys()), filtered_items, session
        )
        logger.info(f"缓存写入: 成功 {success_count}, 失败 {fail_count}")

        if bargains:
            await replace_global_bargains(bargains, f"manual_{tier_label}", session)
            logger.info(f"捡漏表已更新: {len(bargains)} 条")

    # 9. L1 预热
    async with AsyncSessionLocal() as session:
        warm_count = await warm_l1_cache(
            list(keyword_prices.keys())[:100], keyword_prices, session
        )
        logger.info(f"L1 缓存预热: {warm_count} 个")

    # 10. 最终汇总
    logger.info("=" * 60)
    logger.info("入库完成！汇总:")
    logger.info(f"  爬取关键词: {report.success_count}/{len(keywords)}")
    logger.info(f"  爬取商品数: {len(report.all_items)}")
    logger.info(f"  规则筛后商品数: {len(filtered_items)}")
    logger.info(f"  Canonical models: {len(items_by_canonical)}")
    logger.info(f"  有效估价: {len(keyword_prices)}")
    logger.info(f"  捡漏: {len(bargains)}")
    logger.info(f"  缓存写入: {success_count}")
    if report.login_required_count > 0:
        logger.warning(f"  登录失效关键词: {report.login_required_count} 个，需要更新 cookie")
    if report.risk_detected_count > 0:
        logger.warning(f"  风控触发: {report.risk_detected_count} 个")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
