"""
APScheduler 定时任务——分层爬取 + 缓存更新 + 全局捡漏检测。

T0 热门型号：每 5min 高频爬取，少量样本够用即停
T1 普通型号：每 12h 爬取一次
T2 长尾型号：每 3d 或按需爬取
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.redis_client import get_redis, CRAWL_PROGRESS_KEY, LOCK_CRAWL_KEY
from app.services.redis_lock import acquire_crawl_lock
from app.services.keyword_tier import (
    KeywordTier,
    get_keywords_by_tier,
    get_canonical_model,
    get_canonical_keyword,
    get_model_keywords_for_pricing,
    get_tier,
)
from app.services.crawl_worker import crawl_all_ccd_models, crawl_canary
from app.services.cache_updater import compute_price_for_keyword, batch_update_cache, warm_l1_cache, write_crawled_items
from app.services.bargain_detector import (
    detect_global_bargains,
    replace_global_bargains,
    replace_global_bargains_for_keywords,
)
from app.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None


def _make_batch_id(tier: str = "") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return f"{tier}_{ts}" if tier else ts


def _format_dt(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


async def _write_progress(r, batch_id: str, stage: str, done: int, total: int,
                          current_keyword: str, success_count: int, fail_count: int,
                          total_items: int, bargains_found: int, started_at: str,
                          finished_at: str = "", tier: str = ""):
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
            "tier": tier,
        }
        await r.setex(CRAWL_PROGRESS_KEY, 7200, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"写入爬取进度失败: {e}")


async def _clear_progress(r):
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


async def _run_tier_crawl(
    tier: KeywordTier,
    db_session_factory,
    skip_lock: bool = False,
    max_items_per_kw: int = None,
    skip_canary: bool = False,
    concurrency: int = None,
    keyword_limit: int = 0,
    storage_state_override: str = None,
    batch_id_override: str = None,
    keyword_offset: int = 0,
):
    """
    执行单层爬取任务：爬取 → 写入原始商品 → 算法估价 → 全局捡漏 → 缓存更新。
    每个 tier 的爬取任务结构相同，只是关键词列表和频率不同。
    """
    batch_id = batch_id_override or _make_batch_id(tier.value)
    started_at = datetime.utcnow().isoformat()
    r = await get_redis()

    logger.info(f"[{tier.value}] 批次 {batch_id} 开始执行")

    # 分布式锁
    # Stability mode uses one global lock across all tiers. This prevents a
    # manual tier worker from overlapping the all-model sweep.
    lock_id = "crawl-global" if settings.crawl_stability_mode else f"crawl-{tier.value}"

    # CPU 保护：负载过高时延迟或跳过
    cpu_load = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0
    cpu_cores = os.cpu_count() or 2
    if cpu_load > cpu_cores * 2.5:
        logger.warning(f"[{tier.value}] CPU 负载过高 ({cpu_load:.1f})，跳过本轮爬取")
        r and await r.delete(lock_id)
        return
    if cpu_load > cpu_cores * 1.5:
        wait_sec = int((cpu_load - cpu_cores) * 5)
        logger.info(f"[{tier.value}] CPU 负载偏高 ({cpu_load:.1f})，等待 {wait_sec}s")
        await asyncio.sleep(wait_sec)
    if not skip_lock:
        try:
            lock = await acquire_crawl_lock(
                worker_id=lock_id,
                ttl=300 if settings.crawl_stability_mode else 7200,
            )
        except RuntimeError as e:
            logger.warning(f"[{tier.value}] {e}")
            return
    else:
        lock = None

    try:
        await _write_progress(r, batch_id, "starting", 0, 0, "初始化中...", 0, 0, 0, 0, started_at, tier=tier.value)

        if storage_state_override is None:
            try:
                from app.services.xianyu_auth import choose_scheduler_storage_state
                async with db_session_factory() as session:
                    storage_state_override = await choose_scheduler_storage_state(session)
            except Exception as e:
                logger.warning(f"[{tier.value}] 选择闲鱼授权态失败，回退默认登录态: {e}")

        # 记录爬取状态（upsert）
        async with db_session_factory() as session:
            from app.models.crawl_status import CrawlStatus
            from sqlalchemy import select
            result = await session.execute(
                select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
            )
            status = result.scalar_one_or_none()
            if status is None:
                status = CrawlStatus(batch_id=batch_id)
                session.add(status)
            status.started_at = datetime.utcnow()
            status.status = "running"
            await session.commit()

        # 获取该层关键词
        keywords = get_keywords_by_tier(tier)
        if keywords and keyword_offset:
            offset = keyword_offset % len(keywords)
            keywords = keywords[offset:] + keywords[:offset]
        if keyword_limit and keyword_limit > 0:
            keywords = keywords[:keyword_limit]
        total_kw = len(keywords)
        logger.info(f"[{tier.value}] 批次 {batch_id}，共 {total_kw} 个关键词")

        await _write_progress(r, batch_id, "crawling", 0, total_kw, "准备爬取...", 0, 0, 0, 0, started_at, tier=tier.value)

        # 进度回调
        async def _progress_callback(**kw):
            await _write_progress(
                r, batch_id, "crawling",
                kw.get("done", 0), kw.get("total", total_kw),
                kw.get("current_keyword", ""),
                kw.get("success", 0), kw.get("fail", 0),
                kw.get("items", 0), 0,
                started_at, tier=tier.value,
            )

        async def _keyword_result_callback(result):
            await _record_keyword_result(db_session_factory, batch_id, result)

        crawl_report = await crawl_all_ccd_models(
            keywords,
            concurrency=concurrency,
            progress_callback=_progress_callback,
            keyword_result_callback=_keyword_result_callback,
            batch_id=batch_id,
            started_at=started_at,
            tier=tier.value,
            max_items_per_kw=max_items_per_kw,
            skip_canary=skip_canary,
            storage_state_override=storage_state_override,
        )

        try:
            from app.services.xianyu_auth import update_scheduler_storage_state_health

            auth_ok = (
                crawl_report.canary_ok
                and crawl_report.login_required_count == 0
                and crawl_report.risk_detected_count == 0
                and crawl_report.success_count > 0
            )
            auth_failed = (
                not crawl_report.canary_ok
                or crawl_report.login_required_count > 0
                or crawl_report.risk_detected_count > 0
            )
            if auth_ok or auth_failed:
                reason = crawl_report.canary_reason or crawl_report.abort_reason
                if not reason and crawl_report.login_required_count > 0:
                    reason = "后台爬取检测到登录态失效"
                if not reason and crawl_report.risk_detected_count > 0:
                    reason = "后台爬取检测到风控限制"
                async with db_session_factory() as session:
                    await update_scheduler_storage_state_health(
                        session,
                        storage_state_override,
                        ok=auth_ok,
                        reason=reason,
                        risk_limited=crawl_report.risk_detected_count > 0,
                    )
        except Exception:
            logger.exception("[%s] 更新闲鱼授权健康状态失败", tier.value)

        logger.info(f"[{tier.value}] 批次 {batch_id} 爬取完成：{crawl_report.success_count} 成功，{crawl_report.fail_count} 失败，{len(crawl_report.all_items)} 条商品")
        if crawl_report.login_required_count > 0:
            logger.warning(f"[{tier.value}] 登录态缺失：{crawl_report.login_required_count} 个关键词需重新登录")
        if crawl_report.risk_detected_count > 0:
            logger.warning(f"[{tier.value}] 风控触发：{crawl_report.risk_detected_count} 个关键词触发了风控")

        if not crawl_report.all_items:
            reason_parts = ["没有爬到任何商品"]
            if crawl_report.login_required_count > 0:
                reason_parts.append(f"{crawl_report.login_required_count} 个关键词需重新登录")
            if crawl_report.risk_detected_count > 0:
                reason_parts.append(f"{crawl_report.risk_detected_count} 个关键词触发风控")
            if not crawl_report.canary_ok:
                reason_parts.append(f"canary 预检失败: {crawl_report.canary_reason}")
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
                started_at, datetime.utcnow().isoformat(), tier=tier.value,
            )
            logger.error(f"[{tier.value}] 批次 {batch_id} 终止：{error_message}")
            return

        # 写入原始商品表
        async with db_session_factory() as session:
            written = await write_crawled_items(crawl_report.all_items, session)
            logger.info(f"[{tier.value}] 批次 {batch_id} 原始商品写入：{written} 条")

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
                datetime.utcnow().isoformat(), tier=tier.value,
            )
            logger.error(f"[{tier.value}] 批次 {batch_id} 终止：{error_message}")
            return

        # 算法估价：按 canonical model 归并后计算
        await _write_progress(r, batch_id, "pricing", total_kw, total_kw, "正在计算估价...",
                              crawl_report.success_count, crawl_report.fail_count,
                              len(crawl_report.all_items), 0, started_at, tier=tier.value)

        keyword_prices: dict[str, dict] = {}
        items_by_canonical: dict[str, list] = {}

        for item in crawl_report.all_items:
            kw = getattr(item, "query_keyword", "") or getattr(item, "keyword", "")
            if not kw:
                continue
            canonical = get_canonical_keyword(kw)
            items_by_canonical.setdefault(canonical, []).append(item)

        priced_count = 0
        for canonical, items in items_by_canonical.items():
            # 取第一个 item 的原始关键词作为 display keyword
            result = compute_price_for_keyword(canonical, items)
            if result and result.get("base_price", 0) > 0:
                keyword_prices[canonical] = result
                priced_count += 1

        logger.info(f"[{tier.value}] 批次 {batch_id} 估价完成：{priced_count} 个 canonical model 有有效价格")

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
                datetime.utcnow().isoformat(), tier=tier.value,
            )
            logger.error(f"[{tier.value}] 批次 {batch_id} 终止：{error_message}")
            return

        # T0 和 T1 做捡漏检测；T2 只更新价格缓存
        bargains = []
        if tier in (KeywordTier.T0_HOT, KeywordTier.T1_WARM):
            await _write_progress(r, batch_id, "detecting_bargains", total_kw, total_kw, "检测捡漏中...",
                                  crawl_report.success_count, crawl_report.fail_count,
                                  len(crawl_report.all_items), 0, started_at, tier=tier.value)

            bargain_prices = {kw: data["base_price"] for kw, data in keyword_prices.items()}
            bargains = detect_global_bargains(crawl_report.all_items, bargain_prices)

        # 写入数据库
        action = "saving"
        if tier == KeywordTier.T2_COLD:
            action = "saving (prices only)"
        await _write_progress(r, batch_id, action, total_kw, total_kw, "写入数据库...",
                              crawl_report.success_count, crawl_report.fail_count,
                              len(crawl_report.all_items), len(bargains), started_at, tier=tier.value)

        async with db_session_factory() as session:
            await batch_update_cache(keyword_prices, list(keyword_prices.keys()),
                                     crawl_report.all_items, session)
            if tier in (KeywordTier.T0_HOT, KeywordTier.T1_WARM):
                if settings.crawl_stability_mode:
                    affected_keywords = []
                    for canonical in keyword_prices:
                        affected_keywords.extend(get_model_keywords_for_pricing(canonical))
                    await replace_global_bargains_for_keywords(
                        bargains,
                        batch_id,
                        affected_keywords,
                        session,
                    )
                else:
                    # 成功爬取但没有捡漏时也要清空旧结果，避免捡漏广场展示过期机会。
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

        # L1 预热
        await _write_progress(r, batch_id, "warming", total_kw, total_kw, "预热缓存...",
                              crawl_report.success_count, crawl_report.fail_count,
                              len(crawl_report.all_items), len(bargains), started_at, tier=tier.value)
        async with db_session_factory() as session:
            warm_count = await warm_l1_cache(
                list(keyword_prices.keys())[:100],
                keyword_prices,
                session,
            )
            logger.info(f"[{tier.value}] 批次 {batch_id} L1 缓存预热完成：{warm_count} 个型号")

        finished_at = datetime.utcnow().isoformat()
        await _write_progress(r, batch_id, "completed", total_kw, total_kw, "全部完成",
                              crawl_report.success_count, crawl_report.fail_count,
                              len(crawl_report.all_items), len(bargains),
                              started_at, finished_at, tier=tier.value)
        logger.info(f"[{tier.value}] 批次 {batch_id} 全部完成：{len(bargains)} 件全局捡漏")

    except Exception as e:
        logger.exception(f"[{tier.value}] 批次 {batch_id} 执行出错: {e}")
        finished_at = datetime.utcnow().isoformat()
        await _write_progress(r, batch_id, "failed", 0, 0, f"出错: {str(e)[:50]}", 0, 0, 0, 0,
                              started_at, finished_at, tier=tier.value)
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
        if r:
            asyncio.get_event_loop().call_later(300, lambda: asyncio.create_task(_clear_progress(r)))


# ============================================================
# 公开入口：供 main.py 的 lifespan 调用
# ============================================================

async def run_full_crawl_task(db_session_factory, skip_lock: bool = False):
    """
    [兼容旧接口] 定时任务主函数——默认对 T0 热门型号执行全流程。
    """
    await _run_tier_crawl(
        tier=KeywordTier.T0_HOT,
        db_session_factory=db_session_factory,
        skip_lock=skip_lock,
        max_items_per_kw=settings.max_items_per_query_t0,
    )


async def run_t0_crawl(db_session_factory):
    """T0 热门型号爬取（高频，少量样本）。"""
    await _run_tier_crawl(
        tier=KeywordTier.T0_HOT,
        db_session_factory=db_session_factory,
        max_items_per_kw=settings.max_items_per_query_t0,
        concurrency=settings.crawl_concurrency,
    )


async def run_t1_crawl(db_session_factory):
    """T1 普通型号爬取（中频，全量样本）。"""
    await _run_tier_crawl(
        tier=KeywordTier.T1_WARM,
        db_session_factory=db_session_factory,
        max_items_per_kw=settings.max_items_per_query,
        concurrency=settings.crawl_concurrency,
    )


async def run_t2_crawl(db_session_factory):
    """T2 长尾型号爬取（低频）。"""
    await _run_tier_crawl(
        tier=KeywordTier.T2_COLD,
        db_session_factory=db_session_factory,
        max_items_per_kw=settings.max_items_per_query,
        concurrency=settings.crawl_concurrency,
    )


def setup_scheduler(db_session_factory):
    """
    配置 APScheduler 并注册分层定时任务。
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    # T0 热门型号：高频爬取
    if settings.crawl_t0_enabled:
        _scheduler.add_job(
            run_t0_crawl,
            trigger=IntervalTrigger(seconds=settings.crawl_interval_seconds),
            id="crawl_t0",
            name="T0热门型号爬取",
            kwargs={"db_session_factory": db_session_factory},
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"T0 定时任务已注册（每 {settings.crawl_interval_seconds}s）")

    # T1 普通型号：中频爬取
    if settings.crawl_t1_enabled:
        _scheduler.add_job(
            run_t1_crawl,
            trigger=IntervalTrigger(seconds=settings.crawl_interval_t1_seconds),
            id="crawl_t1",
            name="T1普通型号爬取",
            kwargs={"db_session_factory": db_session_factory},
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"T1 定时任务已注册（每 {settings.crawl_interval_t1_seconds}s）")

    # T2 长尾型号：低频爬取
    if settings.crawl_t2_enabled:
        _scheduler.add_job(
            run_t2_crawl,
            trigger=IntervalTrigger(seconds=settings.crawl_interval_t2_seconds),
            id="crawl_t2",
            name="T2长尾型号爬取",
            kwargs={"db_session_factory": db_session_factory},
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"T2 定时任务已注册（每 {settings.crawl_interval_t2_seconds}s）")

    _scheduler.start()
    logger.info("分层定时任务调度器已启动")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("定时任务调度器已关闭")
