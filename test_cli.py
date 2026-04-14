"""
简单截图脚本 - 截取页面截图并分析内容
"""
from playwright.sync_api import sync_playwright
import os
import sys

# 设置输出目录
output_dir = r"d:\cursor项目文件\估二手\test_results\cli_test"
os.makedirs(output_dir, exist_ok=True)

def main():
    with sync_playwright() as p:
        # 启动带界面的浏览器
        browser = p.chromium.launch(headless=False, args=['--start-maximized'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print("=" * 60)
        print("开始截图测试")
        print("=" * 60)

        # 1. 访问首页
        print("\n[1] 访问首页...")
        page.goto("http://localhost:5173")
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(output_dir, "01_homepage.png"), full_page=True)
        print(f"   截图: 01_homepage.png")

        # 2. 输入关键词
        print("\n[2] 输入关键词 '富士 J150'...")
        try:
            search_input = page.wait_for_selector("input.search-input", timeout=5000)
            search_input.fill("富士 J150")
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(output_dir, "02_input_keyword.png"), full_page=True)
            print(f"   截图: 02_input_keyword.png")
        except Exception as e:
            print(f"   错误: {e}")

        # 3. 点击估价按钮
        print("\n[3] 点击估价按钮...")
        try:
            btn = page.wait_for_selector("button.search-btn", timeout=5000)
            btn.click()
            print(f"   已点击")

            # 4. 等待估价完成
            print("\n[4] 等待估价完成（最多90秒）...")
            page.wait_for_timeout(90000)

            page.screenshot(path=os.path.join(output_dir, "03_valuation_result.png"), full_page=True)
            print(f"   截图: 03_valuation_result.png")

            # 5. 分析样本列表
            print("\n[5] 分析样本列表...")

            # 尝试查找样本元素
            sample_selectors = [
                ".sample-item",
                "[class*='sample']",
                "a[href*='goofish']",
                "a[href*='item']"
            ]

            for selector in sample_selectors:
                samples = page.query_selector_all(selector)
                if samples:
                    print(f"   选择器 '{selector}' 找到 {len(samples)} 个元素")

                    # 获取每个样本的信息
                    for i, sample in enumerate(samples[:5]):
                        try:
                            # 获取文本内容
                            text = sample.inner_text()
                            href = sample.get_attribute("href")

                            print(f"\n   样本 {i+1}:")
                            print(f"      文本: {text[:100]}...")
                            if href:
                                print(f"      链接: {href[:80]}...")

                            # 检查是否有XD卡标签
                            xd_elements = sample.query_selector_all("[class*='xd'], [class*='XD'], [class*='card']")
                            if xd_elements:
                                print(f"      XD卡标签: 有 ({len(xd_elements)} 个)")

                        except Exception as e:
                            print(f"   样本 {i+1} 分析失败: {e}")

                    break

            # 6. 截图样本区域
            page.screenshot(path=os.path.join(output_dir, "04_samples_detail.png"), full_page=True)
            print(f"\n   截图: 04_samples_detail.png")

        except Exception as e:
            print(f"   错误: {e}")

        # 7. 访问捡漏页面
        print("\n[6] 访问捡漏页面...")
        try:
            page.goto("http://localhost:5173/bargains")
            page.wait_for_timeout(3000)
            page.screenshot(path=os.path.join(output_dir, "05_bargains_page.png"), full_page=True)
            print(f"   截图: 05_bargains_page.png")

            # 分析捡漏项
            bargains = page.query_selector_all(".bargain-item, [class*='bargain'], .card")
            print(f"   找到 {len(bargains)} 个捡漏项")

            for i, bargain in enumerate(bargains[:5]):
                try:
                    text = bargain.inner_text()
                    print(f"\n   捡漏 {i+1}:")
                    print(f"      {text[:150]}...")

                    # 检查XD卡标记
                    xd = bargain.query_selector_all("[class*='xd-card'], [class*='XD']")
                    if xd:
                        for xd_elem in xd:
                            print(f"      XD卡: {xd_elem.inner_text()}")

                except Exception as e:
                    print(f"   捡漏 {i+1} 分析失败: {e}")

        except Exception as e:
            print(f"   错误: {e}")

        # 8. 返回首页截图
        print("\n[7] 返回首页...")
        page.goto("http://localhost:5173")
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(output_dir, "06_final_home.png"), full_page=True)
        print(f"   截图: 06_final_home.png")

        print("\n" + "=" * 60)
        print(f"截图保存在: {output_dir}")
        print("=" * 60)
        print("\n按回车键关闭浏览器...")
        input()

        browser.close()

if __name__ == "__main__":
    main()
