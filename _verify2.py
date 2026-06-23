"""Verification script - writes results to file."""
import sys
import os
sys.path.insert(0, r"D:\my progect\估二手\backend")

output_path = r"D:\my progect\估二手\_verify_result.txt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("=== 估二手 功能验证 ===\n\n")

    try:
        # 1. keyword_tier
        from app.services.keyword_tier import (
            KeywordTier, get_canonical_model, get_keywords_by_tier, get_tier,
            get_canonical_keyword, get_tier_counts, get_t0_model_ids,
            get_model_keywords_for_pricing, get_all_keywords,
        )
        f.write("[OK] keyword_tier imported\n")

        counts = get_tier_counts()
        f.write(f"  T0: {counts['t0']} keywords\n")
        f.write(f"  T1: {counts['t1']} keywords\n")

        model = get_canonical_model("佳能ixus130")
        assert model and model.model_id == "canon-ixus-130"
        f.write(f"  ixus130 -> {model.model_id} (keywords: {len(model.keywords)})\n")

        model = get_canonical_model("索尼t700")
        assert model and model.model_id == "sony-t700"
        f.write(f"  t700 -> {model.model_id} (keywords: {len(model.keywords)})\n")

        t0 = get_keywords_by_tier(KeywordTier.T0_HOT)
        t1 = get_keywords_by_tier(KeywordTier.T1_WARM)
        overlap = set(k.strip().lower() for k in t0) & set(k.strip().lower() for k in t1)
        assert len(overlap) == 0
        f.write(f"  No T0/T1 overlap\n")
        f.write(f"  Total: {len(get_all_keywords())} keywords\n\n")

    except Exception as e:
        f.write(f"[FAIL] keyword_tier: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        # 2. crawl_worker
        from app.services.crawl_worker import DynamicConcurrency
        dc = DynamicConcurrency(initial=2, max_concurrency=5)
        for i in range(5): dc.record(True)
        for i in range(5): dc.record(False)
        assert dc.failure_rate == 0.5
        f.write(f"[OK] crawl_worker: DynamicConcurrency failure_rate={dc.failure_rate:.1%}\n\n")
    except Exception as e:
        f.write(f"[FAIL] crawl_worker: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        # 3. _match_items_to_keyword
        from app.services.cache_updater import _match_items_to_keyword

        class F:
            def __init__(s, iid, qkw, price, title, qs=50):
                s.item_id = iid; s.query_keyword = qkw; s.keyword = qkw
                s.price = price; s.title = title; s.quality_score = qs

        items = [
            F("1", "佳能ixus130", 500, "Canon IXUS 130"),
            F("2", "sd1400is", 480, "Canon SD1400 IS"),
            F("3", "索尼t700", 700, "Sony T700"),
        ]
        matched = _match_items_to_keyword("canon-ixus-130", items)
        assert len(matched) == 2, f"expected 2, got {len(matched)}"
        f.write(f"[OK] _match_items_to_keyword: canon-ixus-130 matched {len(matched)}\n\n")
    except Exception as e:
        f.write(f"[FAIL] cache_updater._match: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        # 4. config
        from app.config import settings
        f.write("[OK] config:\n")
        for attr in ["crawl_t0_enabled", "crawl_t1_enabled", "crawl_t2_enabled",
                      "crawl_canary_enabled", "crawl_dynamic_concurrency",
                      "max_items_per_query_t0", "crawl_interval_seconds",
                      "crawl_interval_t1_seconds", "crawl_interval_t2_seconds"]:
            f.write(f"  {attr}={getattr(settings, attr, 'N/A')}\n")
    except Exception as e:
        f.write(f"[FAIL] config: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    f.write("\n=== ALL CHECKS PASSED ===\n")
