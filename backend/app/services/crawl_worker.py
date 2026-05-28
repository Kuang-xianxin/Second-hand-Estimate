"""
批量爬取逻辑——供定时任务调用，并发控制 + 错误重试 + 批次管理 + 动态并发 + Canary 预检。
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


class DynamicConcurrency:
    """根据失败率动态调整并发数，实现自动降速/恢复。"""

    def __init__(self, initial: int = 1, max_concurrency: int = 3):
        self.current = max(1, initial)
        self.max = max(self.current, max_concurrency)
        self._window: List[bool] = []  # True=成功, False=失败
        self._window_size = 10
        self._min_samples_for_increase = self._window_size

    def record(self, success: bool):
        self._window.append(success)
        if len(self._window) > self._window_size:
            self._window = self._window[-self._window_size:]

    @property
    def failure_rate(self) -> float:
        if not self._window:
            return 0.0
        return 1.0 - (sum(self._window) / len(self._window))

    def adjust(self) -> int:
        """根据最近窗口的失败率调整并发数。"""
        if not settings.crawl_dynamic_concurrency:
            return self.current
        if not self._window:
            return self.current
        rate = self.failure_rate
        threshold = settings.crawl_failure_rate_threshold
        if rate >= threshold and self.current > 1:
            self.current = max(1, self.current - 1)
            logger.warning(f"动态并发：失败率 {rate:.0%} >= {threshold:.0%}，降至 {self.current}")
        elif len(self._window) >= self._min_samples_for_increase and rate < threshold / 2 and self.current < self.max:
            self.current = min(self.max, self.current + 1)
            logger.info(f"动态并发：失败率 {rate:.0%} 健康，恢复至 {self.current}")
        return self.current


async def crawl_canary(storage_state_override: Optional[str] = None) -> Tuple[bool, str, dict]:
    """
    预检金丝雀：爬取 1-2 个测试关键词，验证登录态和风控状态。
    返回 (ok, reason, debug_summary)。
    金丝雀失败不应启动后续大批次。
    """
    if not settings.crawl_canary_enabled:
        return True, "canary disabled", {}

    canary_kw_str = settings.crawl_canary_keywords or ""
    canary_keywords = [kw.strip() for kw in canary_kw_str.split(",") if kw.strip()]
    if not canary_keywords:
        return True, "no canary keywords configured", {}

    crawler = get_crawler()

    async def _check_one(kw: str) -> Tuple[bool, str, dict]:
        for attempt in range(2):
            if attempt > 0:
                await asyncio.sleep(0.5)
            search_kwargs = {
                "max_items": min(5, settings.max_items_per_query_t0),
                "filter_keyword": kw,
            }
            if storage_state_override:
                search_kwargs["storage_state_override"] = storage_state_override
            try:
                items = await crawler.search(kw, **search_kwargs)
                debug = getattr(crawler, "_last_debug_summary", {}) or {}
                login_hint = debug.get("login_page_hint", False)
                risk_hint = debug.get("risk_page_hint", False)
                response_count = debug.get("response_count", 0)

                if login_hint:
                    reason = f"canary「{kw}」检测到登录页面，cookie 可能已过期"
                elif risk_hint:
                    reason = f"canary「{kw}」触发风控验证页，暂停爬取"
                elif not items:
                    if response_count == 0:
                        reason = f"canary「{kw}」无响应数据，可能被屏蔽"
                    else:
                        reason = f"canary「{kw}」响应正常但没有解析到商品，可能页面结构变化或被空结果拦截"
                else:
                    logger.info(f"Canary 预检通过：「{kw}」正常，获取 {len(items)} 条商品")
                    return True, "canary keyword ok", debug

                if attempt == 0:
                    logger.warning(f"{reason}，准备重试一次")
                    continue
                return False, reason, debug
            except Exception as e:
                reason = f"canary「{kw}」爬取异常: {e}"
                if attempt == 0:
                    logger.warning(f"{reason}，准备重试一次")
                    continue
                return False, reason, {}
        return False, f"canary「{kw}」未知失败", {}

    for kw in canary_keywords[:2]:  # 最多测 2 个
        ok, reason, debug = await _check_one(kw)
        if not ok:
            return False, reason, debug

    return True, "canary ok", {}


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
    canary_ok: bool = True
    canary_reason: str = ""
    tier: str = ""
    final_concurrency: int = 1


async def crawl_single_keyword(
    keyword: str,
    sem: Optional[asyncio.Semaphore] = None,
    crawler=None,
    max_retries: int = 2,
    max_items: int = None,
    storage_state_override: Optional[str] = None,
) -> CrawlResult:
    """爬取单个关键词，带指数退避重试。semaphore 包住 sleep + search 保证并发控制有效。"""
    if max_items is None:
        max_items = settings.max_items_per_query

    for attempt in range(max_retries + 1):
        try:
            if crawler is None:
                crawler = get_crawler()
            search_kwargs = {
                "max_items": max_items,
                "cookie_override": None,
                "filter_keyword": keyword,
            }
            if storage_state_override:
                search_kwargs["storage_state_override"] = storage_state_override
            if sem:
                async with sem:
                    await asyncio.sleep(random.uniform(0.3, 1.0))
                    items = await crawler.search(keyword, **search_kwargs)
            else:
                await asyncio.sleep(random.uniform(0.3, 1.0))
                items = await crawler.search(keyword, **search_kwargs)

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
            if not items:
                response_count = int(debug.get("response_count", 0) or 0)
                if response_count == 0:
                    error = "未获取到搜索接口响应"
                else:
                    error = "未解析到有效商品"
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
    tier: str = "",
    max_items_per_kw: int = None,
    skip_canary: bool = False,
    storage_state_override: Optional[str] = None,
) -> BatchCrawlReport:
    """
    分层并发爬取 CCD 型号关键词。

    1. Canary 预检（可跳过）
    2. 分批并发，动态调整并发数
    3. 每批结束后等待间隔再继续
    4. 错误关键词重试
    5. 检测到风控/登录失效立即熔断
    """
    if concurrency is None:
        concurrency = _get_concurrency()
    if batch_size is None:
        batch_size = _get_batch_size()
    if max_items_per_kw is None:
        max_items_per_kw = settings.max_items_per_query

    # Canary 预检
    canary_ok = True
    canary_reason = ""
    if not skip_canary and settings.crawl_canary_enabled:
        if storage_state_override:
            canary_ok, canary_reason, canary_debug = await crawl_canary(storage_state_override=storage_state_override)
        else:
            canary_ok, canary_reason, canary_debug = await crawl_canary()
        if not canary_ok:
            logger.error(f"Canary 预检失败，取消爬取: {canary_reason}")
            return BatchCrawlReport(
                total_keywords=len(keywords),
                success_count=0,
                fail_count=0,
                all_items=[],
                aborted=True,
                abort_reason=f"canary: {canary_reason}",
                canary_ok=False,
                canary_reason=canary_reason,
                tier=tier,
            )

    all_items: list = []
    success_count = 0
    fail_count = 0
    failed_keywords: list = []
    seen_ids: set = set()
    login_required_count = 0
    risk_detected_count = 0
    aborted = False
    abort_reason = ""

    dyn_concurrency = DynamicConcurrency(
        initial=concurrency,
        max_concurrency=settings.crawl_concurrency_max,
    )
    sem_limit = concurrency
    sem = asyncio.Semaphore(sem_limit)
    crawler = get_crawler()

    total_keywords = len(keywords)
    if settings.crawl_dev_keyword_limit and settings.crawl_dev_keyword_limit > 0:
        keywords = keywords[:settings.crawl_dev_keyword_limit]
        total_keywords = len(keywords)
        logger.info(f"开发模式：限制为 {total_keywords} 个关键词")
    logger.info(f"开始{'T0' if tier == 't0' else 'T1' if tier == 't1' else ''}爬取：{total_keywords} 个关键词，{concurrency} 并发，每词最多 {max_items_per_kw} 条")

    for batch_start in range(0, total_keywords, batch_size):
        batch = keywords[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (total_keywords + batch_size - 1) // batch_size
        logger.info(f"批次 {batch_num}/{total_batches}：{len(batch)} 个关键词")

        # 动态调整并发 + 重建信号量
        current_conc = dyn_concurrency.adjust()
        if current_conc != sem_limit:
            sem_limit = current_conc
            sem = asyncio.Semaphore(current_conc)

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
            asyncio.create_task(crawl_single_keyword(
                kw,
                sem,
                crawler,
                max_items=max_items_per_kw,
                storage_state_override=storage_state_override,
            ))
            for kw in batch
        ]

        for task in asyncio.as_completed(tasks):
            result = await task
            batch_processed += 1
            if isinstance(result, Exception):
                batch_fail += 1
                fail_count += 1
                dyn_concurrency.record(False)
                continue
            if keyword_result_callback:
                await keyword_result_callback(result)
            result_failed_for_risk = result.login_required or result.risk_detected
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
                dyn_concurrency.record(False)
            else:
                batch_success += 1
                success_count += 1
                dyn_concurrency.record(not result_failed_for_risk)
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
            # 动态间隔：失败率高时增加等待时间
            base_delay = random.uniform(2, 5)
            if dyn_concurrency.failure_rate > 0:
                base_delay += settings.crawl_slowdown_delay * dyn_concurrency.failure_rate
            logger.info(f"批次间隔等待 {base_delay:.1f}s（失败率 {dyn_concurrency.failure_rate:.0%}）")
            await asyncio.sleep(base_delay)

    # 重试失败关键词
    if failed_keywords and not aborted:
        logger.info(f"重试 {len(failed_keywords)} 个失败关键词...")
        retry_sem = asyncio.Semaphore(max(1, dyn_concurrency.current // 2))
        tasks = [
            crawl_single_keyword(
                kw,
                retry_sem,
                crawler,
                max_items=max_items_per_kw,
                storage_state_override=storage_state_override,
            )
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
    logger.info(f"爬取完成（{tier}）：成功 {success_count}/{total_keywords}，共收集 {len(all_items)} 条去重商品，最终并发 {dyn_concurrency.current}")
    return BatchCrawlReport(
        total_keywords=total_keywords,
        success_count=success_count,
        fail_count=fail_count,
        all_items=all_items,
        login_required_count=login_required_count,
        risk_detected_count=risk_detected_count,
        aborted=aborted,
        abort_reason=abort_reason,
        canary_ok=canary_ok,
        canary_reason=canary_reason,
        tier=tier,
        final_concurrency=dyn_concurrency.current,
    )
