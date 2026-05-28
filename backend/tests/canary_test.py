"""
E2E test script for canary pre-check and meltdown logic.

Usage:
  python -m tests.canary_test              # run all checks
  python -m tests.canary_test --dry-run    # print config, don't crawl
  python -m tests.canary_test --single     # crawl a single safe keyword
  python -m tests.canary_test --canary-only  # only run canary check
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from app.services.crawl_worker import (
    crawl_canary,
    crawl_single_keyword,
    crawl_all_ccd_models,
    DynamicConcurrency,
)
from app.services.keyword_tier import (
    get_tier_counts,
    get_keywords_by_tier,
    get_canonical_model,
    KeywordTier,
)
from app.config import settings

__test__ = False


def print_config():
    print("=== Config ===")
    print(f"  canary_enabled: {settings.crawl_canary_enabled}")
    print(f"  canary_keywords: {settings.crawl_canary_keywords}")
    print(f"  dynamic_concurrency: {settings.crawl_dynamic_concurrency}")
    print(f"  concurrency_max: {settings.crawl_concurrency_max}")
    print(f"  failure_threshold: {settings.crawl_failure_rate_threshold}")
    print(f"  slowdown_delay: {settings.crawl_slowdown_delay}")
    counts = get_tier_counts()
    print(f"  tier counts: T0={counts['t0']}, T1={counts['t1']}, T2={counts['t2']}")


async def run_canary():
    print("\n=== Canary Check ===")
    ok, reason, debug = await crawl_canary()
    print(f"  ok: {ok}")
    print(f"  reason: {reason}")
    print(f"  debug: {debug}")
    return ok


async def run_single():
    print("\n=== Single Keyword Crawl ===")
    kw = "佳能ixus130"
    print(f"  keyword: {kw}")
    model = get_canonical_model(kw)
    print(f"  canonical: {model.model_id if model else 'N/A'}")
    result = await crawl_single_keyword(kw, max_items=10)
    print(f"  success: {result.success}")
    print(f"  items: {len(result.items)}")
    print(f"  risk: {result.risk_detected}")
    print(f"  login: {result.login_required}")
    return result.success


async def run_tier_test():
    print("\n=== Tier Crawl Test (T0, 3 keywords, dry) ===")
    t0_kw = get_keywords_by_tier(KeywordTier.T0_HOT)[:3]
    print(f"  keywords: {t0_kw}")
    report = await crawl_all_ccd_models(
        t0_kw, concurrency=1, batch_size=3, tier="t0",
        max_items_per_kw=5, skip_canary=True,
    )
    print(f"  aborted: {report.aborted}")
    print(f"  success: {report.success_count}")
    print(f"  fail: {report.fail_count}")
    print(f"  risk: {report.risk_detected_count}")
    print(f"  login: {report.login_required_count}")
    print(f"  total items: {len(report.all_items)}")
    return not report.aborted


async def test_dynamic_concurrency():
    print("\n=== DynamicConcurrency Unit ===")
    dc = DynamicConcurrency(initial=3, max_concurrency=5)
    print(f"  initial: {dc.current}")
    for _ in range(3):
        dc.record(True)
    for _ in range(3):
        dc.record(False)
    print(f"  failure_rate: {dc.failure_rate:.2f}")
    dc.adjust()
    print(f"  after adjust: {dc.current}")
    assert dc.current < 3, f"Expected drop, got {dc.current}"
    assert dc.current >= 1, f"Should not go below 1, got {dc.current}"
    print("  PASS")
    return True


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--single", action="store_true")
    parser.add_argument("--canary-only", action="store_true")
    args = parser.parse_args()

    print_config()

    if args.dry_run:
        print("\n[Dry run - no crawling]")
        await test_dynamic_concurrency()
        return

    # Always run unit test
    await test_dynamic_concurrency()

    if args.canary_only:
        await run_canary()
        return

    if args.single:
        await run_single()
        return

    # Full test
    canary_ok = await run_canary()
    if not canary_ok:
        print("\nCanary failed, skipping tier test (would abort in production)")
        return

    await run_tier_test()
    print("\n=== ALL DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
