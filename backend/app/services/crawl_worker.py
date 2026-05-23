"""
批量爬取逻辑——供定时任务调用，并发控制 + 错误重试 + 批次管理。
"""
import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from app.crawler.xianyu import get_crawler
from app.models.redis_client import get_redis
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10
DEFAULT_CONCURRENCY = 1


def _get_concurrency() -> int:
    val = settings.crawl_concurrency
    if val is None or val <= 0:
        return DEFAULT_CONCURRENCY
    return val


def _get_batch_size() -> int:
    val = settings.crawl_batch_size
    if val is None or val <= 0:
        return DEFAULT_BATCH_SIZE
    return val


@dataclass
class CrawlResult:
    keyword: str
    items: list
    success: bool
    error: Optional[str] = None
    total_collected: int = 0
    login_required: bool = False
    risk_detected: bool = False
    debug_summary: dict = field(default_factory=dict)


@dataclass
class BatchCrawlReport:
    total_keywords: int
    success_count: int
    fail_count: int
    all_items: list  # 所有成功爬取的商品
    login_required_count: int = 0  # 检测到需要登录的关键词数
    risk_detected_count: int = 0   # 检测到风控页面的关键词数
    aborted: bool = False
    abort_reason: str = ""


async def crawl_single_keyword(
    keyword: str,
    sem: Optional[asyncio.Semaphore] = None,
    crawler=None,
    max_retries: int = 2,
) -> CrawlResult:
    """爬取单个关键词，带指数退避重试。semaphore 包住 sleep + search 保证并发控制有效。"""
    for attempt in range(max_retries + 1):
        try:
            if crawler is None:
                crawler = get_crawler()
            if sem:
                async with sem:
                    await asyncio.sleep(random.uniform(0.3, 1.0))
                    items = await crawler.search(
                        keyword,
                        max_items=settings.max_items_per_query,
                        cookie_override=None,
                        filter_keyword=keyword,
                    )
            else:
                await asyncio.sleep(random.uniform(0.3, 1.0))
                items = await crawler.search(
                    keyword,
                    max_items=settings.max_items_per_query,
                    cookie_override=None,
                    filter_keyword=keyword,
                )

            # 检查爬虫调试摘要中的登录/风控状态。
            debug = getattr(crawler, "_last_debug_summary", {}) or {}
            login_required = debug.get("login_page_hint", False)
            risk_detected = debug.get("risk_page_hint", False)
            if (login_required or risk_detected) and not items:
                error = "登录态失效" if login_required else "触发风控验证"
                return CrawlResult(
                    keyword=keyword,
                    items=[],
                    success=False,
                    error=error,
                    total_collected=0,
                    login_required=login_required,
                    risk_detected=risk_detected,
                    debug_summary=debug,
                )
            return CrawlResult(
                keyword=keyword,
                items=items,
                success=True,
                total_collected=len(items),
                login_required=login_required,
                risk_detected=risk_detected,
                debug_summary=debug,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if attempt < max_retries:
                wait_time = 3 * (attempt + 1)
                logger.info(f"关键词「{keyword}」第 {attempt+1} 次失败: {e}，{wait_time}s 后重试")
                await asyncio.sleep(wait_time)
            else:
                logger.warning(f"关键词「{keyword}」重试耗尽，跳过: {e}")
                return CrawlResult(
                    keyword=keyword,
                    items=[],
                    success=False,
                    error=str(e),
                )


async def crawl_all_ccd_models(
    keywords: List[str],
    concurrency: int = None,
    batch_size: int = None,
    progress_callback=None,
    keyword_result_callback=None,
    batch_id: str = "",
    started_at: str = "",
) -> BatchCrawlReport:
    """
    并发爬取全部 CCD 型号关键词。

    1. 分批并发（每批 50 个关键词，20 并发）
    2. 每批结束后等待 5 秒再进行下一批
    3. 错误关键词重试 1 次
    4. 返回所有成功爬取的商品
    5. 若提供 progress_callback，每次批次完成后调用 (done, total, current_keyword)
    """
    if concurrency is None:
        concurrency = _get_concurrency()
    if batch_size is None:
        batch_size = _get_batch_size()

    all_items: list = []
    success_count = 0
    fail_count = 0
    failed_keywords: list = []
    seen_ids: set = set()
    login_required_count = 0
    risk_detected_count = 0
    aborted = False
    abort_reason = ""

    sem = asyncio.Semaphore(concurrency)
    crawler = get_crawler()

    total_keywords = len(keywords)
    if settings.crawl_dev_keyword_limit and settings.crawl_dev_keyword_limit > 0:
        keywords = keywords[:settings.crawl_dev_keyword_limit]
        total_keywords = len(keywords)
        logger.info(f"开发模式：限制为 {total_keywords} 个关键词")
    logger.info(f"开始全量爬取：{total_keywords} 个关键词，{concurrency} 并发")

    for batch_start in range(0, total_keywords, batch_size):
        batch = keywords[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (total_keywords + batch_size - 1) // batch_size
        logger.info(f"批次 {batch_num}/{total_batches}：{len(batch)} 个关键词")

        # 进度回调：批次开始
        if progress_callback:
            current_kw = f"{batch[0]}...{batch[-1]}" if len(batch) > 1 else batch[0]
            await progress_callback(
                stage="crawling",
                done=batch_start,
                total=total_keywords,
                current_keyword=current_kw,
                success=success_count,
                fail=fail_count,
                items=len(all_items),
                started_at=started_at,
            )

        batch_success = 0
        batch_fail = 0
        batch_processed = 0
        tasks = [
            asyncio.create_task(crawl_single_keyword(kw, sem, crawler))
            for kw in batch
        ]

        for task in asyncio.as_completed(tasks):
            result = await task
            batch_processed += 1
            if isinstance(result, Exception):
                batch_fail += 1
                fail_count += 1
                continue
            if keyword_result_callback:
                await keyword_result_callback(result)
            if result.login_required:
                login_required_count += 1
                logger.warning(f"关键词「{result.keyword}」返回登录页，可能未登录或 cookie 已过期")
            if result.risk_detected:
                risk_detected_count += 1
                logger.warning(f"关键词「{result.keyword}」触发了风控验证页")
            if not result.success:
                if not result.login_required and not result.risk_detected:
                    failed_keywords.append(result.keyword)
                batch_fail += 1
                fail_count += 1
            else:
                batch_success += 1
                success_count += 1
                for item in result.items:
                    if item.item_id not in seen_ids:
                        seen_ids.add(item.item_id)
                        all_items.append(item)

            if settings.crawl_stop_on_risk and (result.login_required or result.risk_detected):
                aborted = True
                abort_reason = "登录态失效" if result.login_required else "触发风控验证"
                logger.error(f"检测到{abort_reason}，熔断当前批次，取消剩余关键词")
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                break

        # 进度回调：批次完成
        if progress_callback:
            current_kw = f"{batch[0]}...{batch[-1]}" if len(batch) > 1 else batch[0]
            await progress_callback(
                stage="crawling",
                done=batch_start + batch_processed,
                total=total_keywords,
                current_keyword=current_kw,
                success=success_count,
                fail=fail_count,
                items=len(all_items),
                started_at=started_at,
            )

        logger.info(f"批次 {batch_num} 完成：成功 {batch_success}，失败 {batch_fail}，累计 {len(all_items)} 条商品")

        if aborted:
            break

        if batch_start + batch_size < total_keywords:
            delay = random.uniform(2, 5)
            logger.info(f"批次间隔等待 {delay:.1f}s")
            await asyncio.sleep(delay)

    # 重试失败关键词
    if failed_keywords and not aborted:
        logger.info(f"重试 {len(failed_keywords)} 个失败关键词...")
        retry_sem = asyncio.Semaphore(max(1, concurrency // 2))
        tasks = [
            crawl_single_keyword(kw, retry_sem, crawler)
            for kw in failed_keywords
        ]
        retry_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in retry_results:
            if isinstance(result, Exception):
                fail_count += 1
                continue
            if keyword_result_callback:
                await keyword_result_callback(result)
            if result.success:
                success_count += 1
                for item in result.items:
                    if item.item_id not in seen_ids:
                        seen_ids.add(item.item_id)
                        all_items.append(item)

    # 最终进度回调
    if progress_callback:
        await progress_callback(
            stage="crawling",
            done=total_keywords,
            total=total_keywords,
            current_keyword="爬取完成",
            success=success_count,
            fail=fail_count,
            items=len(all_items),
            started_at=started_at,
        )

    if login_required_count > 0:
        logger.warning(f"登录态缺失：{login_required_count} 个关键词返回登录页，请检查 xianyu_storage_state.json")
    if risk_detected_count > 0:
        logger.warning(f"风控触发：{risk_detected_count} 个关键词触发验证码/风控页面")
    logger.info(f"全量爬取完成：成功 {success_count}/{total_keywords}，共收集 {len(all_items)} 条去重商品")
    return BatchCrawlReport(
        total_keywords=total_keywords,
        success_count=success_count,
        fail_count=fail_count,
        all_items=all_items,
        login_required_count=login_required_count,
        risk_detected_count=risk_detected_count,
        aborted=aborted,
        abort_reason=abort_reason,
    )
