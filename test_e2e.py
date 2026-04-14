"""
端到端自动化测试 - 测试完整的估价流程
包括：XD卡识别、捡漏检测、多模型分析
"""
import asyncio
import json
import time
from playwright.async_api import async_playwright

async def test_full_valuation_flow():
    """测试完整的估价流程"""
    print("=" * 60)
    print("端到端测试 - 估价流程")
    print("=" * 60)

    browser = None
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()

        # 1. 访问首页
        print("\n[1] 访问首页...")
        await page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)

        # 2. 输入XD卡相关关键词进行测试
        test_keywords = ["富士 JX680", "富士 J150", "奥林巴斯"]

        for keyword in test_keywords:
            print(f"\n[2] 测试关键词: {keyword}")

            # 清空并输入关键词
            search_input = await page.wait_for_selector("input.search-input", timeout=5000)
            await search_input.fill(keyword)
            print(f"    已输入: {keyword}")

            # 点击估价按钮
            submit_btn = await page.wait_for_selector("button.search-btn", timeout=5000)
            await submit_btn.click()
            print(f"    已点击估价按钮")

            # 等待估价结果（最多60秒）
            print(f"    等待估价结果...")
            max_wait = 60
            start_time = time.time()

            # 监听页面变化，检测估价结果
            while time.time() - start_time < max_wait:
                await asyncio.sleep(2)

                # 检查是否有错误提示
                error_elements = await page.query_selector_all("[class*='error'], [class*='alert']")
                if error_elements:
                    for elem in error_elements:
                        text = await elem.text_content()
                        if text and len(text) > 10:
                            print(f"    错误提示: {text[:100]}")
                            break

                # 检查是否显示了估价结果（价格区间）
                price_elements = await page.query_selector_all("[class*='price'], .result, .valuation")
                if price_elements:
                    for elem in price_elements:
                        text = await elem.text_content()
                        if text and any(c.isdigit() for c in text) and "¥" in text or "元" in text or "价格" in text:
                            print(f"    检测到结果元素: {text[:80]}...")
                            break

                # 检查是否有XD卡相关提示
                page_text = await page.text_content("body")
                if "xd" in page_text.lower() or "XD" in page_text:
                    print(f"    检测到XD卡相关信息!")

                # 检查控制台错误
                console_logs = []
                page.on("console", lambda msg: console_logs.append(msg.text) if msg.type == "error" else None)

                # 检查是否加载完成（按钮变为"分析中..."状态结束）
                btn_text = await submit_btn.text_content()
                if "开始估价" in btn_text or "新增并行" in btn_text:
                    print(f"    估价完成，按钮状态: {btn_text}")
                    break

            elapsed = time.time() - start_time
            print(f"    耗时: {elapsed:.1f}秒")

            # 清空输入框
            await search_input.fill("")
            await asyncio.sleep(1)

        # 3. 测试捡漏页面
        print("\n[3] 测试捡漏页面...")
        await page.goto("http://localhost:5173/bargains", timeout=15000)
        await asyncio.sleep(2)

        bargains = await page.query_selector_all("[class*='bargain'], [class*='alert'], .card")
        print(f"    找到 {len(bargains)} 个捡漏项")

        # 4. 测试历史页面
        print("\n[4] 测试历史页面...")
        await page.goto("http://localhost:5173/history", timeout=15000)
        await asyncio.sleep(2)

        history_items = await page.query_selector_all("[class*='history'], [class*='record'], .item")
        print(f"    找到 {len(history_items)} 条历史记录")

        # 截图
        await page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(1)
        await page.screenshot(path="d:/cursor项目文件/估二手/test_results/e2e_final.png")
        print("\n[E2E] 最终状态截图已保存")

        print("\n" + "=" * 60)
        print("端到端测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if browser:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_full_valuation_flow())
