"""Quick verification script - checks that all new modules can be imported."""
import sys
sys.path.insert(0, r"D:\my progect\估二手\backend")

errors = []

# 1. Test keyword_tier import
try:
    from app.services.keyword_tier import (
        KeywordTier, CanonicalModel,
        get_canonical_model, get_keywords_by_tier, get_tier,
        get_canonical_keyword, get_tier_counts, get_t0_model_ids,
        get_model_keywords_for_pricing, get_all_keywords, get_display_name,
    )
    print("[OK] keyword_tier imported")

    # Verify indices
    counts = get_tier_counts()
    print(f"  Tier counts: {counts}")
    assert counts["t0"] > 0, "T0 must have keywords"
    assert counts["t1"] > 0, "T1 must have keywords"

    # Verify canonical model
    model = get_canonical_model("佳能ixus130")
    assert model is not None, "ixus130 should have canonical model"
    assert model.model_id == "canon-ixus-130", f"Expected canon-ixus-130, got {model.model_id}"
    print(f"  Canonical mapping: 佳能ixus130 -> {model.model_id}")

    # Verify keyword merging
    pricing_kw = get_model_keywords_for_pricing("佳能ixus130")
    assert len(pricing_kw) >= 4, f"ixus130 should have >=4 pricing keywords, got {len(pricing_kw)}"
    print(f"  Pricing keywords for ixus130: {pricing_kw}")

    # Verify no duplicates
    t0 = set(kw.strip().lower() for kw in get_keywords_by_tier(KeywordTier.T0_HOT))
    t1 = set(kw.strip().lower() for kw in get_keywords_by_tier(KeywordTier.T1_WARM))
    overlap = t0 & t1
    assert len(overlap) == 0, f"Overlap between T0 and T1: {overlap}"
    print(f"  No T0/T1 overlap: OK")

    # Verify all keywords
    all_kw = get_all_keywords()
    print(f"  Total keywords: {len(all_kw)}")
    assert len(all_kw) == len(t0) + len(t1)

except Exception as e:
    errors.append(f"keyword_tier: {e}")
    import traceback
    traceback.print_exc()

# 2. Test crawl_worker import
try:
    from app.services.crawl_worker import (
        crawl_canary, DynamicConcurrency, CrawlResult, BatchCrawlReport,
        crawl_all_ccd_models, crawl_single_keyword,
    )
    print("[OK] crawl_worker imported")

    # Test DynamicConcurrency
    dc = DynamicConcurrency(initial=2, max_concurrency=5)
    assert dc.current == 2
    assert dc.failure_rate == 0.0
    for _ in range(5):
        dc.record(True)
    for _ in range(5):
        dc.record(False)
    assert dc.failure_rate == 0.5
    print(f"  DynamicConcurrency: failure_rate={dc.failure_rate:.1%}, current={dc.current}")
except Exception as e:
    errors.append(f"crawl_worker: {e}")
    import traceback
    traceback.print_exc()

# 3. Test scheduler import
try:
    from app.scheduler import (
        setup_scheduler, shutdown_scheduler,
        run_full_crawl_task, run_t0_crawl, run_t1_crawl, run_t2_crawl,
    )
    print("[OK] scheduler imported")
except Exception as e:
    errors.append(f"scheduler: {e}")
    import traceback
    traceback.print_exc()

# 4. Test cache_updater _match_items_to_keyword
try:
    from app.services.cache_updater import _match_items_to_keyword, compute_price_for_keyword

    class FakeItem:
        def __init__(self, item_id, query_keyword, price, title, quality_score=50):
            self.item_id = item_id
            self.query_keyword = query_keyword
            self.keyword = query_keyword
            self.price = price
            self.title = title
            self.quality_score = quality_score

    items = [
        FakeItem("1", "佳能ixus130", 500, "Canon IXUS 130 相机"),
        FakeItem("2", "sd1400is", 480, "Canon SD1400 IS 相机"),
        FakeItem("3", "索尼t700", 700, "Sony T700 相机"),
    ]

    matched = _match_items_to_keyword("canon-ixus-130", items)
    assert len(matched) == 2, f"canon-ixus-130 should match 2 items, got {len(matched)}"
    print(f"[OK] _match_items_to_keyword: canon-ixus-130 matched {len(matched)} items")

    matched2 = _match_items_to_keyword("索尼t700", items)
    assert len(matched2) == 1, f"索尼t700 should match 1 item, got {len(matched2)}"
    print(f"[OK] _match_items_to_keyword: 索尼t700 matched {len(matched2)} items")

except Exception as e:
    errors.append(f"cache_updater: {e}")
    import traceback
    traceback.print_exc()

# 5. Test config
try:
    from app.config import settings
    print(f"[OK] config imported")
    print(f"  crawl_t0_enabled: {settings.crawl_t0_enabled}")
    print(f"  crawl_t1_enabled: {settings.crawl_t1_enabled}")
    print(f"  crawl_canary_enabled: {settings.crawl_canary_enabled}")
    print(f"  crawl_dynamic_concurrency: {settings.crawl_dynamic_concurrency}")
    print(f"  max_items_per_query_t0: {settings.max_items_per_query_t0}")
except Exception as e:
    errors.append(f"config: {e}")
    import traceback
    traceback.print_exc()

# Summary
print()
print("=" * 60)
if errors:
    print(f"FAILED: {len(errors)} error(s)")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)
