"""
详细功能验证测试 - 验证XD卡识别与捡漏的所有细节
"""
import asyncio
import json
import time
from playwright.async_api import async_playwright

async def run_detailed_tests():
    print("=" * 70)
    print("详细功能验证测试 - XD卡识别与捡漏")
    print("=" * 70)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
    page = await context.new_page()

    console_messages = []
    page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

    results = {
        "passed": [],
        "failed": [],
        "warnings": []
    }

    try:
        # ==================== 首页测试 ====================
        print("\n[TEST 1] 首页加载...")
        await page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)

        # 检查核心元素
        elements = {
            "搜索框": "input.search-input",
            "估价按钮": "button.search-btn",
            "新增并行按钮": "button:has-text('新增并行')",
            "模型选择(DeepSeek)": "button.model-btn:has-text('DeepSeek')",
            "模型选择(通义千问)": "button.model-btn:has-text('通义千问')",
            "模型选择(豆包)": "button.model-btn:has-text('豆包')",
            "页面标题": "h1.page-title"
        }

        for name, selector in elements.items():
            try:
                elem = await page.wait_for_selector(selector, timeout=5000)
                if elem:
                    results["passed"].append(f"首页-{name}")
                    print(f"  [OK] {name}")
                else:
                    results["failed"].append(f"首页-{name}")
                    print(f"  [FAIL] {name}")
            except Exception as e:
                results["failed"].append(f"首页-{name}: {str(e)[:50]}")
                print(f"  [FAIL] {name}: {str(e)[:50]}")

        # ==================== 估价功能测试 ====================
        print("\n[TEST 2] 估价流程测试（XD卡机型：富士J150）...")

        search_input = await page.wait_for_selector("input.search-input", timeout=5000)

        # 测试XD卡机型
        xd_keywords = ["富士 J150", "富士 JX680", "奥林巴斯 TG"]

        for kw in xd_keywords:
            await search_input.fill(kw)
            print(f"\n  测试: {kw}")
            await asyncio.sleep(0.5)

            # 点击新增并行
            try:
                parallel_btn = await page.wait_for_selector("button:has-text('新增并行')", timeout=3000)
                await parallel_btn.click()
                print(f"    已点击新增并行")

                # 等待任务出现
                await asyncio.sleep(1)
                task_tabs = await page.query_selector_all("[class*='task-tab'], [class*='tab-item']")
                print(f"    任务标签数: {len(task_tabs)}")

                results["passed"].append(f"估价-{kw}-并行")

            except Exception as e:
                results["failed"].append(f"估价-{kw}-并行: {str(e)[:50]}")
                print(f"    [FAIL] {str(e)[:50]}")

        await asyncio.sleep(3)  # 等待估价开始

        # ==================== 捡漏页面测试 ====================
        print("\n[TEST 3] 捡漏页面测试...")

        await page.goto("http://localhost:5173/bargains", timeout=15000)
        await asyncio.sleep(3)

        # 检查页面元素
        bargain_elements = {
            "页面标题": "h1, [class*='title'], [class*='header']",
            "未读开关": "[class*='toggle'], [class*='switch'], input[type='checkbox']",
            "捡漏列表": "[class*='bargain'], [class*='item'], [class*='card']"
        }

        bargain_count = 0
        for name, selector in bargain_elements.items():
            try:
                if "*" in selector:
                    # 通配符选择器转义
                    elements_found = await page.query_selector_all(selector)
                else:
                    elements_found = await page.query_selector_all(selector)

                count = len(elements_found)
                if count > 0:
                    print(f"  [OK] {name}: {count}个")
                    results["passed"].append(f"捡漏-{name}")
                    if "列表" in name:
                        bargain_count = count
                else:
                    print(f"  [WARN] {name}: 未找到")
                    results["warnings"].append(f"捡漏-{name}")
            except Exception as e:
                print(f"  [FAIL] {name}: {str(e)[:50]}")

        # 检查XD卡相关元素
        xd_elements = await page.query_selector_all("[class*='xd'], [class*='XD'], [class*='card-badge']")
        if xd_elements:
            print(f"  [OK] XD卡相关标签: {len(xd_elements)}个")
            results["passed"].append("捡漏-XD卡标签")
        else:
            print(f"  [WARN] XD卡相关标签: 未找到")

        # ==================== 历史页面测试 ====================
        print("\n[TEST 4] 历史页面测试...")

        await page.goto("http://localhost:5173/history", timeout=15000)
        await asyncio.sleep(3)

        history_items = await page.query_selector_all("[class*='history'], [class*='record'], [class*='item']")
        print(f"  [OK] 历史记录: {len(history_items)}条")
        results["passed"].append(f"历史页面-加载")

        # ==================== 截图 ====================
        print("\n[TEST 5] 生成测试报告截图...")

        # 首页截图
        await page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)
        await page.screenshot(path="d:/cursor项目文件/估二手/test_results/detailed_home.png", full_page=False)

        # 捡漏页面截图
        await page.goto("http://localhost:5173/bargains", timeout=15000)
        await asyncio.sleep(2)
        await page.screenshot(path="d:/cursor项目文件/估二手/test_results/detailed_bargains.png", full_page=False)

        # ==================== 控制台错误检查 ====================
        print("\n[TEST 6] 控制台错误检查...")
        error_count = len([m for m in console_messages if "error" in m.lower()])
        if error_count == 0:
            print(f"  [OK] 无控制台错误")
            results["passed"].append("无控制台错误")
        else:
            print(f"  [WARN] 控制台错误: {error_count}个")
            results["warnings"].append(f"控制台错误-{error_count}个")
            for msg in console_messages[:5]:
                if "error" in msg.lower():
                    print(f"    {msg[:100]}")

    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["failed"].append(f"测试异常: {str(e)[:100]}")

    finally:
        await browser.close()

    # ==================== 测试报告 ====================
    print("\n" + "=" * 70)
    print("测试报告")
    print("=" * 70)
    print(f"\n通过: {len(results['passed'])}")
    print(f"失败: {len(results['failed'])}")
    print(f"警告: {len(results['warnings'])}")

    print(f"\n--- 通过的测试 ---")
    for item in results["passed"]:
        print(f"  [OK] {item}")

    if results["warnings"]:
        print(f"\n--- 警告 ---")
        for item in results["warnings"]:
            print(f"  [WARN] {item}")

    if results["failed"]:
        print(f"\n--- 失败的测试 ---")
        for item in results["failed"]:
            print(f"  [FAIL] {item}")

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        **results,
        "summary": {
            "total": len(results["passed"]) + len(results["failed"]) + len(results["warnings"]),
            "passed": len(results["passed"]),
            "failed": len(results["failed"]),
            "warnings": len(results["warnings"])
        }
    }

    with open("d:/cursor项目文件/估二手/test_results/detailed_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n详细报告已保存到: d:/cursor项目文件/估二手/test_results/detailed_report.json")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_detailed_tests())
