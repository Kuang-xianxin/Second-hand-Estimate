import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/backend")

results = []

# 1. keyword_tier
try:
    from app.services.keyword_tier import (
        KeywordTier, CanonicalModel, get_tier_counts, get_canonical_model,
        get_canonical_keyword, get_keywords_by_tier, get_t0_model_ids,
        get_model_keywords_for_pricing, get_display_name, get_all_keywords,
    )
    counts = get_tier_counts()
    results.append(f"PASS keyword_tier: T0={counts['t0']}, T1={counts['t1']}")
    m = get_canonical_model("佳能ixus130")
    assert m is not None and m.model_id == "canon-ixus-130", f"Wrong model: {m}"
    results.append(f"PASS canonical mapping: 佳能ixus130 -> {m.model_id}")
except Exception as e:
    results.append(f"FAIL keyword_tier: {e}\n{traceback.format_exc()}")

# 2. crawl_worker
try:
    from app.services.crawl_worker import (
        DynamicConcurrency, crawl_canary, crawl_single_keyword,
        crawl_all_ccd_models, BatchCrawlReport, CrawlResult,
    )
    dc = DynamicConcurrency(initial=2, max_concurrency=5)
    assert dc.current == 2
    results.append(f"PASS crawl_worker: DynamicConcurrency init={dc.current}")
except Exception as e:
    results.append(f"FAIL crawl_worker: {e}\n{traceback.format_exc()}")

# 3. cache_updater
try:
    from app.services.cache_updater import (
        compute_price_for_keyword, batch_update_cache,
        warm_l1_cache, write_crawled_items, _match_items_to_keyword,
    )
    results.append("PASS cache_updater: all imports OK")
except Exception as e:
    results.append(f"FAIL cache_updater: {e}\n{traceback.format_exc()}")

# 4. scheduler
try:
    from app.scheduler import (
        setup_scheduler, run_full_crawl_task, run_t0_crawl, run_t1_crawl, run_t2_crawl, shutdown_scheduler,
    )
    results.append("PASS scheduler: all imports OK")
except Exception as e:
    results.append(f"FAIL scheduler: {e}\n{traceback.format_exc()}")

# 5. cache_api
try:
    from app.api.cache_api import router, CrawlerStatusResponse
    results.append("PASS cache_api: router imported")
except Exception as e:
    results.append(f"FAIL cache_api: {e}\n{traceback.format_exc()}")

# Write results
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_result.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
    f.write("\n\nDONE")
