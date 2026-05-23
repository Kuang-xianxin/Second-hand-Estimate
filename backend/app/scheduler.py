"""
APScheduler 定时任务——每 1.5 小时全量爬取 + 缓存更新 + 全局捡漏检测。
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.redis_client import get_redis, CRAWL_PROGRESS_KEY, LOCK_CRAWL_KEY
from app.services.redis_lock import acquire_crawl_lock
from app.services.ccd_keywords import get_all_keywords
from app.services.crawl_worker import crawl_all_ccd_models
from app.services.cache_updater import compute_price_for_keyword, batch_update_cache, warm_l1_cache, write_crawled_items
from app.services.bargain_detector import detect_global_bargains, replace_global_bargains
from app.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None


def _make_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")


def _format_dt(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


async def _write_progress(r, batch_id: str, stage: str, done: int, total: int,
                          current_keyword: str, success_count: int, fail_count: int,
                          total_items: int, bargains_found: int, started_at: str,
                          finished_at: str = ""):
    """将爬取进度写入 Redis，供前端轮询展示。"""
    if r is None:
        return
    try:
        data = {
            "batch_id": batch_id,
            "stage": stage,
            "done": done,
            "total": total,
            "current_keyword": current_keyword,
            "success_count": success_count,
            "fail_count": fail_count,
            "total_items": total_items,
            "bargains_found": bargains_found,
            "started_at": started_at,
            "finished_at": finished_at,
        }
        # 进度数据 TTL 设为 2 小时，防止残留
        await r.setex(CRAWL_PROGRESS_KEY, 7200, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"写入爬取进度失败: {e}")


async def _clear_progress(r):
    """清除 Redis 中的爬取进度。"""
    if r is None:
        return
    try:
        await r.delete(CRAWL_PROGRESS_KEY)
    except Exception:
        pass


def _keyword_status_from_result(result) -> str:
    if result.login_required:
        return "login_required"
    if result.risk_detected:
        return "risk_detected"
    if result.success:
        return "success"
    return "failed"


async def _record_keyword_result(db_session_factory, batch_id: str, result):
    """记录单关键词爬取结果，供故障排查和后续断点续跑使用。"""
    from app.models.crawl_status import CrawlKeywordStatus
    from sqlalchemy import select

    async with db_session_factory() as session:
        existing_result = await session.execute(
            select(CrawlKeywordStatus).where(
                CrawlKeywordStatus.batch_id == batch_id,
                CrawlKeywordStatus.keyword == result.keyword,
            )
        )
        record = existing_result.scalar_one_or_none()
        debug_summary = json.dumps(result.debug_summary or {}, ensure_ascii=False)
        if record is None:
            record = CrawlKeywordStatus(
                batch_id=batch_id,
                keyword=result.keyword,
            )
            session.add(record)
        record.status = _keyword_status_from_result(result)
        record.item_count = result.total_collected
        record.login_required = result.login_required
        record.risk_detected = result.risk_detected
        record.error_message = result.error
        record.debug_summary = debug_summary
        record.finished_at = datetime.utcnow()
        await session.commit()


async def run_full_crawl_task(db_session_factory, skip_lock: bool = False):
    """
    定时任务主函数：全量爬取 → 算法估价 → 全局捡漏 → 缓存更新。
    在独立的数据库 session 中运行，避免污染主请求的 session。

    skip_lock=True 时跳过分布式锁，用于初次部署自动触发（避免锁残留导致无法执行）。
    """
    batch_id = _make_batch_id()
    started_at = datetime.utcnow().isoformat()
    r = await get_redis()

    logger.info(f"[定时任务] 批次 {batch_id} 开始执行")

    # 获取分布式锁（多 Worker 防重）
    if not skip_lock:
        try:
            lock = await acquire_crawl_lock(worker_id="full-crawl")
        except RuntimeError as e:
            logger.warning(f"[定时任务] {e}")
            return
    else:
        lock = None

    try:
        # 进度：启动中
        await _write_progress(r, batch_id, "starting", 0, 0, "初始化中...", 0, 0, 0, 0, started_at)

        # Step 1: 记录爬取开始状态
        async with db_session_factory() as session:
            from app.models.crawl_status import CrawlStatus
            status = CrawlStatus(
                batch_id=batch_id,
                started_at=datetime.utcnow(),
                status="running",
            )
            session.add(status)
            await session.commit()

        # Step 2: 获取全量关键词
        keywords = get_all_keywords()
        total_kw = len(keywords)
        logger.info(f"[定时任务] 批次 {batch_id}，共 {total_kw} 个关键词")

        # 进度：开始爬取
        await _write_progress(r, batch_id, "crawling", 0, total_kw, "准备爬取...", 0, 0, 0, 0, started_at)

        # Step 3: 全量爬取（带进度回调）
        async def _progress_callback(**kw):
            await _write_progress(
                r, batch_id, "crawling",
                kw.get("done", 0), kw.get("total", total_kw),
                kw.get("current_keyword", ""),
                kw.get("success", 0), kw.get("fail", 0),
                kw.get("items", 0), 0,
                started_at,
            )

        async def _keyword_result_callback(result):
            await _record_keyword_result(db_session_factory, batch_id, result)

        crawl_report = await crawl_all_ccd_models(
            keywords,
            progress_callback=_progress_callback,
            keyword_result_callback=_keyword_result_callback,
            batch_id=batch_id,
            started_at=started_at,
        )

        logger.info(f"[定时任务] 批次 {batch_id} 爬取完成：{crawl_report.success_count} 成功，{crawl_report.fail_count} 失败，{len(crawl_report.all_items)} 条商品")
        if crawl_report.login_required_count > 0:
            logger.warning(f"[定时任务] 登录态缺失：{crawl_report.login_required_count} 个关键词需重新登录")
        if crawl_report.risk_detected_count > 0:
            logger.warning(f"[定时任务] 风控触发：{crawl_report.risk_detected_count} 个关键词触发了风控")
        if not crawl_report.all_items:
            reason_parts = ["没有爬到任何商品"]
            if crawl_report.login_required_count > 0:
                reason_parts.append(f"{crawl_report.login_required_count} 个关键词需重新登录")
            if crawl_report.risk_detected_count > 0:
                reason_parts.append(f"{crawl_report.risk_detected_count} 个关键词触发风控")
            error_message = "；".join(reason_parts)
            async with db_session_factory() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
                )
                status_record = result.scalar_one_or_none()
                if status_record:
                    status_record.finished_at = datetime.utcnow()
                    status_record.status = "failed"
                    status_record.total_keywords = crawl_report.total_keywords
                    status_record.success_count = crawl_report.success_count
                    status_record.fail_count = crawl_report.fail_count
                    status_record.total_items = 0
                    status_record.error_message = error_message
                    await session.commit()
            await _write_progress(
                r, batch_id, "failed", total_kw, total_kw, error_message,
                crawl_report.success_count, crawl_report.fail_count, 0, 0,
                started_at, datetime.utcnow().isoformat(),
            )
            logger.error(f"[定时任务] 批次 {batch_id} 终止：{error_message}")
            return

        # Step 3b: 写入原始商品表（在估价之前，保证原始数据落地）
        async with db_session_factory() as session:
            written = await write_crawled_items(crawl_report.all_items, session)
            logger.info(f"[定时任务] 批次 {batch_id} 原始商品写入：{written} 条")

        if crawl_report.aborted:
            error_message = f"爬取熔断：{crawl_report.abort_reason}"
            async with db_session_factory() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
                )
                status_record = result.scalar_one_or_none()
                if status_record:
                    status_record.finished_at = datetime.utcnow()
                    status_record.status = "aborted"
                    status_record.total_keywords = crawl_report.total_keywords
                    status_record.success_count = crawl_report.success_count
                    status_record.fail_count = crawl_report.fail_count
                    status_record.total_items = len(crawl_report.all_items)
                    status_record.error_message = error_message
                    await session.commit()
            await _write_progress(
                r, batch_id, "failed", total_kw, total_kw, error_message,
                crawl_report.success_count, crawl_report.fail_count,
                len(crawl_report.all_items), 0, started_at,
                datetime.utcnow().isoformat(),
            )
            logger.error(f"[定时任务] 批次 {batch_id} 终止：{error_message}")
            return

        # 进度：计算估价
        await _write_progress(r, batch_id, "pricing", total_kw, total_kw, "正在计算估价...", crawl_report.success_count, crawl_report.fail_count, len(crawl_report.all_items), 0, started_at)

        # Step 4: 算法估价（逐型号）
        keyword_prices: dict[str, dict] = {}
        items_by_keyword: dict[str, list] = {}
        for item in crawl_report.all_items:
            kw = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
            if not kw:
                continue
            items_by_keyword.setdefault(kw, []).append(item)

        priced_count = 0
        for kw, items in items_by_keyword.items():
            result = compute_price_for_keyword(kw, items)
            if result and result.get("base_price", 0) > 0:
                keyword_prices[kw] = result
                priced_count += 1

        logger.info(f"[定时任务] 批次 {batch_id} 估价完成：{priced_count} 个型号有有效价格")
        if not keyword_prices:
            error_message = "没有可写入缓存的有效估价结果，保留旧缓存和旧捡漏数据"
            async with db_session_factory() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
                )
                status_record = result.scalar_one_or_none()
                if status_record:
                    status_record.finished_at = datetime.utcnow()
                    status_record.status = "failed"
                    status_record.total_keywords = crawl_report.total_keywords
                    status_record.success_count = crawl_report.success_count
                    status_record.fail_count = crawl_report.fail_count
                    status_record.total_items = len(crawl_report.all_items)
                    status_record.error_message = error_message
                    await session.commit()
            await _write_progress(
                r, batch_id, "failed", total_kw, total_kw, error_message,
                crawl_report.success_count, crawl_report.fail_count,
                len(crawl_report.all_items), 0, started_at,
                datetime.utcnow().isoformat(),
            )
            logger.error(f"[定时任务] 批次 {batch_id} 终止：{error_message}")
            return

        # 进度：检测捡漏
        await _write_progress(r, batch_id, "detecting_bargains", total_kw, total_kw, "检测捡漏中...", crawl_report.success_count, crawl_report.fail_count, len(crawl_report.all_items), 0, started_at)

        # Step 5: 全局捡漏检测（detect_global_bargains 需要 {kw: base_price} 格式）
        bargain_prices = {kw: data["base_price"] for kw, data in keyword_prices.items()}
        bargains = detect_global_bargains(crawl_report.all_items, bargain_prices)

        # 进度：写入数据
        await _write_progress(r, batch_id, "saving", total_kw, total_kw, "写入数据库...", crawl_report.success_count, crawl_report.fail_count, len(crawl_report.all_items), len(bargains), started_at)

        # Step 6: 写入数据库（缓存 + 捡漏）
        async with db_session_factory() as session:
            await batch_update_cache(keyword_prices, list(keyword_prices.keys()),
                                     crawl_report.all_items, session)
            await replace_global_bargains(bargains, batch_id, session)

            from sqlalchemy import select
            result = await session.execute(
                select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
            )
            status_record = result.scalar_one_or_none()
            if status_record:
                status_record.finished_at = datetime.utcnow()
                status_record.status = "completed"
                status_record.total_keywords = crawl_report.total_keywords
                status_record.success_count = crawl_report.success_count
                status_record.fail_count = crawl_report.fail_count
                status_record.total_items = len(crawl_report.all_items)
                status_record.bargains_found = len(bargains)
            await session.commit()

        # 进度：L1 预热（后台，不阻塞）
        await _write_progress(r, batch_id, "warming", total_kw, total_kw, "预热缓存...", crawl_report.success_count, crawl_report.fail_count, len(crawl_report.all_items), len(bargains), started_at)
        async with db_session_factory() as session:
            warm_count = await warm_l1_cache(
                list(keyword_prices.keys())[:100],
                keyword_prices,
                session,
            )
            logger.info(f"[定时任务] 批次 {batch_id} L1 缓存预热完成：{warm_count} 个型号")

        # 进度：完成
        finished_at = datetime.utcnow().isoformat()
        await _write_progress(r, batch_id, "completed", total_kw, total_kw, "全部完成", crawl_report.success_count, crawl_report.fail_count, len(crawl_report.all_items), len(bargains), started_at, finished_at)
        logger.info(f"[定时任务] 批次 {batch_id} 全部完成：{len(bargains)} 件全局捡漏")

    except Exception as e:
        logger.exception(f"[定时任务] 批次 {batch_id} 执行出错: {e}")
        finished_at = datetime.utcnow().isoformat()
        await _write_progress(r, batch_id, "failed", 0, 0, f"出错: {str(e)[:50]}", 0, 0, 0, 0, started_at, finished_at)
        try:
            async with db_session_factory() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
                )
                status_record = result.scalar_one_or_none()
                if status_record:
                    status_record.finished_at = datetime.utcnow()
                    status_record.status = "failed"
                    status_record.error_message = str(e)
                    await session.commit()
        except Exception:
            pass
    finally:
        if lock is not None:
            await lock.release()
        # 完成后延迟清除进度（让前端还能看到"完成"状态一段时间）
        if r:
            asyncio.get_event_loop().call_later(300, lambda: asyncio.create_task(_clear_progress(r)))


def setup_scheduler(db_session_factory):
    """
    配置 APScheduler 并注册定时任务。
    调度器在后台运行，不阻塞 FastAPI 启动。
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    _scheduler.add_job(
        run_full_crawl_task,
        trigger=IntervalTrigger(seconds=settings.crawl_interval_seconds),
        id="full_crawl",
        name="CCD全量爬取",
        kwargs={"db_session_factory": db_session_factory, "skip_lock": False},
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(f"定时任务调度器已启动（每 {settings.crawl_interval_seconds} 秒全量爬取）")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("定时任务调度器已关闭")
