"""
通过 FastAPI 接口触发爬取并监控进度。
用法：python _trigger_crawl.py
"""
import urllib.request
import urllib.error
import json
import time
import subprocess
import sys
import os
import signal

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "http://localhost:8000"


def api_get(path):
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def api_post(path, data):
    try:
        req = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def main():
    # 1. 检查健康
    print("1. 检查服务健康状态...")
    health = api_get("/health")
    print(f"   {health}")

    if "error" in health:
        print("   服务未启动，正在启动...")
        # 启动服务
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", BACKEND_DIR,
             "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # 等待服务就绪
        for _ in range(15):
            time.sleep(1)
            try:
                health = api_get("/health")
                if "status" in health:
                    print("   服务已启动")
                    break
            except Exception:
                pass
        else:
            print("   服务启动超时")
            return

    # 2. 查看 tier 统计
    print("\n2. 关键词分层统计...")
    tiers = api_get("/api/crawler/tiers")
    if "tier_counts" in tiers:
        print(f"   {tiers['tier_counts']}")

    # 3. 登录态检查
    print("\n3. 登录态检查...")
    login = api_get("/api/crawler/login-check")
    print(f"   storage_state: {login.get('has_storage_state')}")
    print(f"   needs_login: {login.get('needs_login')}")

    # 4. Canary 检查
    print("\n4. Canary 预检...")
    status = api_get("/api/crawler/status")
    print(f"   canary_ok: {status.get('canary_ok')}")
    print(f"   canary_message: {status.get('canary_message', '')[:80]}")

    # 5. 触发爬取 (小批量先测试)
    print("\n5. 触发 T0 爬取（5 个关键词）...")
    trigger = api_post("/api/crawler/trigger", {
        "tier": "t0",
        "limit": 5,
        "max_items_per_kw": 10,
        "concurrency": 1,
        "skip_canary": False,
    })
    print(f"   {trigger}")

    # 6. 监控进度
    print("\n6. 监控爬取进度...")
    for i in range(120):
        time.sleep(2)
        progress = api_get("/api/crawl/progress")
        if not progress or isinstance(progress, dict) and "error" in progress:
            if i == 0:
                print("   等待进度...")
            continue
        stage = progress.get("stage", "?")
        done = progress.get("done", 0)
        total = progress.get("total", 0)
        items = progress.get("total_items", 0)
        bargains = progress.get("bargains_found", 0)
        bar = "=" * (done * 40 // total) if total > 0 else ""
        print(f"   [{stage}] {done}/{total} | items={items} | bargains={bargains} | {bar}", end="\r")
        if stage in ("completed", "failed"):
            print()
            print(f"\n7. 最终结果:")
            print(f"   stage: {stage}")
            print(f"   items: {items}")
            print(f"   bargains: {bargains}")
            if progress.get("current_keyword"):
                print(f"   message: {progress['current_keyword'][:100]}")
            break
    else:
        print("\n   监控超时")

    # 8. 显示缓存统计
    print("\n8. 缓存状态...")
    cache_status = api_get("/api/cache/status")
    if "l1_count" in cache_status:
        print(f"   L1(Redis): {cache_status.get('l1_count', 'N/A')}")
    if "l2_count" in cache_status:
        print(f"   L2(DB): {cache_status.get('l2_count', 'N/A')}")

    print("\nDone!")


if __name__ == "__main__":
    main()
