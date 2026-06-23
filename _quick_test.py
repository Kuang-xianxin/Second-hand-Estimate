import sys
sys.path.insert(0, r"D:\my progect\估二手\backend")

# Test 1: keyword_tier
from app.services.keyword_tier import get_tier_counts, get_canonical_model
counts = get_tier_counts()
msg1 = f"T0={counts['t0']}, T1={counts['t1']}"
m = get_canonical_model("佳能ixus130")
msg2 = f"ixus130 -> {m.model_id}"

# Test 2: crawl_worker
from app.services.crawl_worker import DynamicConcurrency
dc = DynamicConcurrency()
msg3 = f"DC init={dc.current}"

# Test 3: _match_items_to_keyword
from app.services.cache_updater import _match_items_to_keyword
msg4 = "_match_items_to_keyword imported"

# Write results
with open(r"D:\my progect\估二手\_test_result.txt", "w") as f:
    f.write(f"{msg1}\n{msg2}\n{msg3}\n{msg4}\nALL OK")
