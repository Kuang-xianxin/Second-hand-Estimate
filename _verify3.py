"""Verification script - writes results to temp file."""
import sys, os, traceback

sys.path.insert(0, r"D:\my progect\估二手\backend")

output_path = os.path.join(os.environ.get("TEMP", "."), "_verify_result.txt")
results = []

def check(name):
    def decorator(fn):
        try:
            fn()
            results.append(f"[OK] {name}")
        except Exception as e:
            results.append(f"[FAIL] {name}: {e}")
            results.append(traceback.format_exc())
    return decorator

@check("keyword_tier import + indices")
def _():
    from app.services.keyword_tier import (
        KeywordTier, get_canonical_model, get_keywords_by_tier,
        get_tier_counts, get_model_keywords_for_pricing, get_all_keywords,
    )
    counts = get_tier_counts()
    results.append(f"  T0={counts['t0']}, T1={counts['t1']}")
    m = get_canonical_model("佳能ixus130")
    assert m and m.model_id == "canon-ixus-130"
    results.append(f"  ixus130 → {m.model_id} ({len(m.keywords)} keywords)")
    m2 = get_canonical_model("索尼t700")
    assert m2 and m2.model_id == "sony-t700"
    t0 = set(k.lower() for k in get_keywords_by_tier(KeywordTier.T0_HOT))
    t1 = set(k.lower() for k in get_keywords_by_tier(KeywordTier.T1_WARM))
    assert not (t0 & t1), "T0/T1 overlap!"
    results.append(f"  No overlap, total={len(get_all_keywords())}")

@check("DynamicConcurrency")
def _():
    from app.services.crawl_worker import DynamicConcurrency
    dc = DynamicConcurrency(initial=2, max_concurrency=5)
    for _ in range(5): dc.record(True)
    for _ in range(5): dc.record(False)
    assert dc.failure_rate == 0.5

@check("_match_items_to_keyword (canonical merge)")
def _():
    from app.services.cache_updater import _match_items_to_keyword
    class F:
        def __init__(s, iid, qkw, price, title):
            s.item_id = iid; s.query_keyword = qkw; s.keyword = qkw
            s.price = price; s.title = title; s.quality_score = 50
    items = [
        F("1", "佳能ixus130", 500, "Canon IXUS 130"),
        F("2", "sd1400is", 480, "Canon SD1400 IS"),
        F("3", "索尼t700", 700, "Sony T700"),
    ]
    m = _match_items_to_keyword("canon-ixus-130", items)
    assert len(m) == 2, f"expected 2, got {len(m)}"
    results.append(f"  canon-ixus-130 matched {len(m)} items")

@check("config values")
def _():
    from app.config import settings
    for a in ["crawl_t0_enabled", "crawl_t1_enabled", "crawl_t2_enabled",
              "crawl_canary_enabled", "crawl_dynamic_concurrency",
              "max_items_per_query_t0"]:
        results.append(f"  {a}={getattr(settings, a)}")

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(results))

print(f"Results written to {output_path}")
print(f"Total checks: {len([r for r in results if r.startswith('[OK]')])} OK, "
      f"{len([r for r in results if r.startswith('[FAIL]')])} FAIL")
