"""
Xianyu Crawler Diagnostic Script
Run: cd backend && python diagnose_crawler.py

Diagnoses:
1. storage.state login status check
2. Xianyu search API raw response format analysis
3. Search result data parsing test
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from playwright.sync_api import sync_playwright
from app.crawler.xianyu import STORAGE_STATE_FILE, CHROMIUM_PATH, XianyuCrawler

def check_storage_state():
    print("\n" + "=" * 60)
    print("[DIAG 1] storage.state login status")
    print("=" * 60)

    if not STORAGE_STATE_FILE.exists():
        print("FAIL: file not found: " + str(STORAGE_STATE_FILE))
        return

    data = json.loads(STORAGE_STATE_FILE.read_text(encoding="utf-8"))
    cookies = data.get("cookies", [])
    origins = data.get("origins", [])

    print("File: " + str(STORAGE_STATE_FILE))
    print("cookies count: " + str(len(cookies)))
    print("origins count: " + str(len(origins)))

    if not cookies:
        print("FAIL: cookies is EMPTY! Playwright cannot restore login state.")
        print("  -> Need to re-login to Xianyu and sync Cookie.")
        print("  -> Or manually visit goofish.com in browser, login, then")
        print("     run save_xianyu_state.py to save the state.")
    else:
        print("OK: cookies exist:")
        for c in cookies[:5]:
            print("  " + str(c.get("name", "?")) + "=" + str(c.get("value", "?")[:30]) + "...")

    for origin in origins:
        local_storage = origin.get("localStorage", [])
        print("\norigins[0].localStorage count: " + str(len(local_storage)))
        for ls in local_storage[:5]:
            print("  " + str(ls.get("name", "?")) + "=" + str(ls.get("value", "?")[:40]) + "...")

def analyze_responses():
    print("\n" + "=" * 60)
    print("[DIAG 2] Xianyu search API raw response format")
    print("=" * 60)

    crawler = XianyuCrawler()

    with sync_playwright() as p:
        print("Chromium path: " + str(CHROMIUM_PATH))
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_PATH if CHROMIUM_PATH else None,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            storage_state=str(STORAGE_STATE_FILE) if STORAGE_STATE_FILE.exists() and STORAGE_STATE_FILE.stat().st_size > 0 else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        if STORAGE_STATE_FILE.exists() and STORAGE_STATE_FILE.stat().st_size > 0:
            print("Loaded storage.state")
        else:
            print("No storage.state loaded (file missing or empty)")

        page = context.new_page()
        intercepted = []

        def on_response(response):
            url = response.url
            if "mtop.taobao.idlemtopsearch.pc.search" not in url:
                return

            try:
                raw_body = response.body()
                body_len = len(raw_body)
                first_bytes = raw_body[:20]
                is_gzip = raw_body[:2] == b'\x1f\x8b'
                is_zlib = raw_body[:2] in (b'\x78\x01', b'\x78\x9c', b'\x78\xda')

                print("\nMATCH search API: " + url[60:120])
                print("  body len: " + str(body_len) + " bytes")
                print("  first 20 bytes hex: " + first_bytes.hex())

                if is_gzip:
                    print("  -> gzip compressed data")
                    import gzip
                    try:
                        decompressed = gzip.decompress(raw_body)
                        print("  decompressed len: " + str(len(decompressed)))
                        text = decompressed.decode("utf-8", errors="replace")
                        print("  first 300 chars: " + text[:300])
                        try:
                            data = json.loads(text)
                            print("  -> JSON parse SUCCESS!")
                            for key in ["resultList", "items", "data", "results"]:
                                if key in data:
                                    items = data[key]
                                    if isinstance(items, list):
                                        print("  Found '" + key + "': " + str(len(items)) + " items")
                                        if items:
                                            print("  Item[0]: " + json.dumps(items[0], ensure_ascii=False)[:300])
                        except json.JSONDecodeError as e:
                            print("  -> JSON parse FAIL: " + str(e))
                    except Exception as e:
                        print("  -> Decompress FAIL: " + str(e))

                elif is_zlib:
                    print("  -> zlib compressed data")
                    import zlib
                    try:
                        decompressed = zlib.decompress(raw_body)
                        text = decompressed.decode("utf-8", errors="replace")
                        print("  decompressed first 300 chars: " + text[:300])
                        try:
                            data = json.loads(text)
                            print("  -> JSON parse SUCCESS!")
                            print("  first 300 chars: " + json.dumps(data, ensure_ascii=False)[:300])
                        except json.JSONDecodeError as e:
                            print("  -> JSON parse FAIL: " + str(e))
                    except Exception as e:
                        print("  -> Decompress FAIL: " + str(e))

                else:
                    print("  -> raw text data (not compressed)")
                    try:
                        data = json.loads(raw_body)
                        print("  -> JSON parse SUCCESS!")
                        print("  first 300 chars: " + json.dumps(data, ensure_ascii=False)[:300])
                    except json.JSONDecodeError:
                        try:
                            text = raw_body.decode("utf-8", errors="replace")
                            print("  first 300 chars: " + text[:300])
                        except Exception as e:
                            print("  -> Decode FAIL: " + str(e))

                intercepted.append({
                    "url": url,
 "body_len": body_len,
                    "is_gzip": is_gzip,
                    "is_zlib": is_zlib,
                })
            except Exception as e:
                print("  -> Intercept FAIL: " + str(e))

        page.on("response", on_response)

        print("\nNavigating to Xianyu search page...")
        for attempt in range(1, 4):
            try:
                page.goto("https://www.goofish.com/search?q=ixus 70", wait_until="domcontentloaded", timeout=20000)
                print(f"  Page loaded: {page.url[:60]}")
                break
            except Exception as e:
                print(f"  Nav attempt {attempt} failed: {e}")
                import time; time.sleep(3)
                if attempt == 3:
                    print("  Navigation failed after 3 attempts. Network may be unstable.")
                    print("  Checking if any API responses were captured before the error...")
                    context.close()
                    browser.close()
                    if intercepted:
                        print(f"\nIntercepted {len(intercepted)} search API responses (captured before navigation error)")
                        for idx, r in enumerate(intercepted):
                            print(f"  [{idx+1}] len={r['body_len']} gzip={r['is_gzip']} zlib={r['is_zlib']} {r['url'][60:120]}")
                    return
        page.wait_for_timeout(5000)

        print("\nIntercepted " + str(len(intercepted)) + " search API responses")

        page_text = page.content().lower()
        page_start = page_text[:500]
        login_page_hint = ("login" in page_start or "\u8bf7\u5148\u767b\u5f55" in page_start) and "请先登录" in page_text[:1000]
        risk_page_hint = "\u9a8c\u8bc1\u7801" in page_text or "verify" in page_text[:2000] or "\u98ce\u63a7" in page_text[:2000]

        for idx, r in enumerate(intercepted):
            print("  [" + str(idx+1) + "] len=" + str(r["body_len"]) + " gzip=" + str(r["is_gzip"]) + " zlib=" + str(r["is_zlib"]) + " " + r["url"][60:120])

        context.close()
        browser.close()


def test_normalize():
    print("\n" + "=" * 60)
    print("[DIAG 3] _normalize_item data structure test")
    print("=" * 60)

    test_cases = [
        {
            "data": {
                "item": {
                    "main": {
                        "clickParam": {"args": {"item_id": "123456", "price": "299"}},
                        "exContent": {"title": "Test Item", "detailParams": {"title": "Test Item"}},
                        "fishTags": {},
                    }
                }
            }
        },
        {
            "data": {
                "api": "mtop.taobao.idlemtopsearch.pc.search",
                "data": {
                    "resultList": [
                        {"data": {"item": {"main": {"clickParam": {"args": {"item_id": "789", "price": "199"}}, "exContent": {"title": "Camera"}, "fishTags": {}}}}}
                    ]
                }
            }
        },
        {
            "resultList": [
                {"item_id": "111", "title": "Item A", "price": "350"}
            ]
        }
    ]

    crawler = XianyuCrawler()

    for idx, test_data in enumerate(test_cases):
        print("\nTest Case " + str(idx+1) + ":")
        items = crawler._extract_items_from_page_data(test_data)
        print("  _extract_items_from_page_data returned: " + str(len(items)) + " items")

        if items:
            normalized = crawler._normalize_item(items[0], keyword="test")
            if normalized:
                print("  OK: _normalize_item success: id=" + normalized.item_id + " price=" + str(normalized.price) + " title=" + normalized.title)
            else:
                print("  FAIL: _normalize_item returned None (field mapping mismatch)")
                print("     Raw data[0]: " + json.dumps(items[0], ensure_ascii=False)[:200])


if __name__ == "__main__":
    print("Xianyu Crawler Diagnostic v1.0")
    print("=" * 60)

    check_storage_state()
    test_normalize()

    print("\n" + "=" * 60)
    print("Running online diagnostic...")
    print("=" * 60)

    try:
        analyze_responses()
    except Exception as e:
        print("Online diagnostic error: " + str(e))
        import traceback
        traceback.print_exc()
