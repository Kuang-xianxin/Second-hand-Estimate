"""Run one crawl tier in a dedicated short-lived process.

Production uses this module from systemd timers so Playwright never runs inside
the long-lived Uvicorn process. The database crawl_status row is authoritative:
the process exits non-zero unless that exact batch completed successfully.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.models.crawl_status import CrawlStatus
from app.models.database import AsyncSessionLocal, engine, init_db
from app.models.redis_client import close_redis
from app.services.keyword_tier import KeywordTier

logger = logging.getLogger("crawl_runner")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG = 64
EXIT_TEMPORARY = 75

TIER_MAP = {
    "t0": KeywordTier.T0_HOT,
    "t1": KeywordTier.T1_WARM,
    "t2": KeywordTier.T2_COLD,
}


def build_batch_id(tier: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{tier}_{timestamp}_{os.getpid()}"


def status_exit_code(status: str | None) -> int:
    if status == "completed":
        return EXIT_OK
    if status in {"failed", "aborted"}:
        return EXIT_FAILED
    return EXIT_TEMPORARY


def tier_is_enabled(tier: str) -> bool:
    return {
        "t0": settings.crawl_t0_enabled,
        "t1": settings.crawl_t1_enabled,
        "t2": settings.crawl_t2_enabled,
    }[tier]


async def read_batch_status(batch_id: str) -> CrawlStatus | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CrawlStatus).where(CrawlStatus.batch_id == batch_id)
        )
        return result.scalar_one_or_none()


async def run_once(
    tier_name: str,
    *,
    keyword_limit: int = 0,
    max_items_per_keyword: int | None = None,
    concurrency: int | None = None,
) -> int:
    from app.scheduler import _run_tier_crawl

    settings.validate_production()
    if not settings.crawl_enabled:
        logger.error("CRAWL_ENABLED is false; refusing to run external crawl worker")
        return EXIT_CONFIG
    if not tier_is_enabled(tier_name):
        logger.info("Tier %s is disabled; nothing to do", tier_name)
        return EXIT_OK

    tier = TIER_MAP[tier_name]
    batch_id = build_batch_id(tier_name)
    if max_items_per_keyword is None:
        max_items_per_keyword = (
            settings.max_items_per_query_t0
            if tier == KeywordTier.T0_HOT
            else settings.max_items_per_query
        )
    if concurrency is None:
        concurrency = settings.crawl_concurrency

    logger.info(
        "Starting external crawl batch=%s tier=%s keyword_limit=%s max_items=%s concurrency=%s",
        batch_id,
        tier_name,
        keyword_limit or "all",
        max_items_per_keyword,
        concurrency,
    )

    await init_db()
    await _run_tier_crawl(
        tier=tier,
        db_session_factory=AsyncSessionLocal,
        max_items_per_kw=max_items_per_keyword,
        concurrency=concurrency,
        keyword_limit=keyword_limit,
        batch_id_override=batch_id,
    )

    record = await read_batch_status(batch_id)
    if record is None:
        logger.error(
            "Batch %s produced no crawl_status row; another worker may hold the Redis lock",
            batch_id,
        )
        return EXIT_TEMPORARY

    exit_code = status_exit_code(record.status)
    log = logger.info if exit_code == EXIT_OK else logger.error
    log(
        "External crawl finished batch=%s status=%s success=%s failed=%s items=%s error=%s",
        batch_id,
        record.status,
        record.success_count,
        record.fail_count,
        record.total_items,
        record.error_message or "",
    )
    return exit_code


async def async_main(args: argparse.Namespace) -> int:
    try:
        return await run_once(
            args.tier,
            keyword_limit=args.keyword_limit,
            max_items_per_keyword=args.max_items,
            concurrency=args.concurrency,
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIG
    except Exception:
        logger.exception("External crawl worker crashed")
        return EXIT_FAILED
    finally:
        await close_redis()
        await engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=sorted(TIER_MAP), required=True)
    parser.add_argument(
        "--keyword-limit",
        type=int,
        default=0,
        help="Limit keywords for a manual canary run; 0 runs the complete tier",
    )
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    return asyncio.run(async_main(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
