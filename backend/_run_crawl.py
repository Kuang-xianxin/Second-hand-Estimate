"""
一键启动服务 → 触发爬取 → 监控进度 → 输出结果
"""
import subprocess
import sys
import json
import time
import urllib.request
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "http://localhost:8000"
OUT_FILE = os.path.join(BACKEND_DIR, "_crawl_result.txt")


def api(path, method="GET", data=None):
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        if data:
            req.method = "POST"
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(data).encode()
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_err": str(e)}


results = []

# 1. Kill any existing instances on port 8000
print("1. Cleaning up old processes...")
subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq uvicorn*"],
               capture_output=True, shell=True)

# 2. Start server
print("2. Starting server...")
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", BACKEND_DIR,
     "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

# 3. Wait for server to be ready
print("3. Waiting for server...")
for i in range(20):
    time.sleep(1)
    h = api("/health")
    if "status" in h:
        print(f"   Server ready: {h}")
        results.append(f"health: {h}")
        break
else:
    print("   Server timeout!")
    server.kill()
    with open(OUT_FILE, "w") as f:
        f.write("Server failed to start\n")
    sys.exit(1)

# 4. Check crawler status
print("4. Checking crawler...")
cs = api("/api/crawler/status")
print(f"   canary_ok={cs.get('canary_ok')}, login_valid={cs.get('login_valid')}")
results.append(f"crawler_status: {json.dumps(cs, ensure_ascii=False)[:200]}")

# 5. Trigger crawl (small test first)
print("5. Triggering T0 crawl (5 keywords)...")
trigger = api("/api/crawler/trigger", method="POST", data={
    "tier": "t0",
    "limit": 0,
    "max_items_per_kw": 40,
    "concurrency": 2,
    "skip_canary": False,
})
print(f"   {trigger}")
results.append(f"trigger: {trigger}")

# 6. Monitor progress
print("6. Monitoring progress...")
last_stage = ""
for i in range(300):  # 10 minutes max
    time.sleep(3)
    try:
        p = api("/api/crawl/progress")
    except Exception:
        continue
    if not p or "_err" in p:
        continue
    stage = p.get("stage", "?")
    done = p.get("done", 0)
    total = p.get("total", 0)
    items = p.get("total_items", 0)
    bargains = p.get("bargains_found", 0)
    percentage = done * 100 // total if total > 0 else 0
    print(f"   [{stage}] {done}/{total} ({percentage}%) | items={items} | bargains={bargains}    ", end="\r", flush=True)
    if stage in ("completed", "failed"):
        print()
        results.append(f"final: {json.dumps(p, ensure_ascii=False)[:500]}")
        break
    if stage != last_stage:
        print()
        last_stage = stage
else:
    print("\n   Monitor timeout after 10min")

# 7. Show cache stats
print("\n7. Cache stats...")
cs2 = api("/api/cache/status")
print(f"   {json.dumps(cs2, ensure_ascii=False)[:300]}")
results.append(f"cache: {json.dumps(cs2, ensure_ascii=False)[:300]}")

# 8. Stop server
print("\n8. Stopping server...")
server.terminate()
try:
    server.wait(timeout=5)
except Exception:
    server.kill()

# Write results
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print(f"\nResults saved to {OUT_FILE}")
