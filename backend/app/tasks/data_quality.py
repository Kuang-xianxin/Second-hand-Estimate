"""Async task definitions for 估二手.

Tasks:
  - crawl_sweep: single-keyword sweep crawl
  - batch_vectorize: index knowledge docs into Qdrant (Phase 2+)
  - clean_stale_data: periodic data quality maintenance
  - compute_data_quality_report: daily stats aggregation
"""
import logging

from app.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_sweep(self, tier: str = "t0", limit: int = 1):
    """Sweep crawl N keywords from a tier (called by scheduler / timer)."""
    import asyncio
    from app.services.crawl_worker import crawl_single_keyword
    from app.services.keyword_tier import get_keywords_by_tier, KeywordTier

    tier_enum = {"t0": KeywordTier.T0, "t1": KeywordTier.T1, "t2": KeywordTier.T2}.get(tier)
    if tier_enum is None:
        raise ValueError(f"Unknown tier: {tier}")

    keywords = get_keywords_by_tier(tier_enum)[:limit]
    results = []
    for kw in keywords:
        try:
            items = asyncio.run(crawl_single_keyword(kw))
            results.append({"keyword": kw, "items": len(items), "status": "ok"})
        except Exception as e:
            logger.warning(f"Crawl failed for keyword={kw}: {e}")
            results.append({"keyword": kw, "items": 0, "status": "error", "error": str(e)})
    return results


@app.task
def batch_vectorize(document_ids: list[str] | None = None):
    """Re-index knowledge documents into Qdrant. Placeholder for Phase 2."""
    logger.info("Batch vectorize requested for %s documents", len(document_ids) if document_ids else "all")
    # Phase 2: Qdrant indexing will go here
    return {"status": "not_implemented", "phase": 2}


@app.task(name="app.tasks.data_quality.clean_stale_data")
def clean_stale_data(retention_days: int = 90):
    """Remove stale crawled items and price observations older than retention_days.

    Idempotent: can be run multiple times without side effects.
    """
    import asyncio
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import delete, select, func

    from app.models.database import AsyncSessionLocal
    from app.models.item import CrawledItem

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    async def _run():
        async with AsyncSessionLocal() as session:
            # Count before
            count_r = await session.execute(
                select(func.count()).select_from(CrawledItem)
            )
            before = count_r.scalar()

            # Delete stale
            result = await session.execute(
                delete(CrawledItem).where(CrawledItem.crawled_at < cutoff)
            )
            await session.commit()

            deleted = result.rowcount
            logger.info("Data quality: removed %d stale items (before: %d, cutoff: %s)",
                         deleted, before, cutoff.isoformat())
            return {"before": before, "deleted": deleted, "cutoff": cutoff.isoformat()}

    return asyncio.run(_run())


@app.task(name="app.tasks.data_quality.compute_data_quality_report")
def compute_data_quality_report():
    """Generate a daily data quality summary.

    Returns counts by keyword, freshness, and invalid-sample ratio.
    """
    import asyncio
    from datetime import datetime, timezone
    from sqlalchemy import select, func

    from app.models.database import AsyncSessionLocal
    from app.models.item import CrawledItem
    from app.models.cache import CCDPriceCache

    async def _run():
        async with AsyncSessionLocal() as session:
            # Total items
            total = await session.scalar(select(func.count()).select_from(CrawledItem))

            # Items with prices
            priced = await session.scalar(
                select(func.count()).select_from(CrawledItem).where(CrawledItem.price > 0)
            )

            # Unique keywords
            kw_r = await session.execute(
                select(func.count(func.distinct(CrawledItem.keyword))).select_from(CrawledItem)
            )
            unique_keywords = kw_r.scalar()

            # Cache entries
            cache_count = await session.scalar(select(func.count()).select_from(CCDPriceCache))

            # Latest crawl time
            latest_r = await session.execute(
                select(func.max(CrawledItem.crawled_at)).select_from(CrawledItem)
            )
            latest_crawl = latest_r.scalar()

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_items": total,
            "priced_items": priced,
            "unique_keywords": unique_keywords,
            "cached_models": cache_count,
            "latest_crawl": latest_crawl.isoformat() if latest_crawl else None,
        }
        logger.info("Data quality report: %s", report)
        return report

    return asyncio.run(_run())
