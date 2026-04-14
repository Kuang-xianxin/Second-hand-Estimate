"""
快速测试脚本 - 验证品牌过滤修复效果
"""
from playwright.sync_api import sync_playwright
import os

output_dir = r"d:\cursor项目文件\估二手\test_results\fix_test"
os.makedirs(output_dir, exist_ok=True)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--start-maximized'])
        page = browser.new_page()

        print("=" * 60)
        print("验证品牌过滤修复")
        print("=" * 60)

        # 1. 访问首页
        print("\n[1] 访问首页...")
        page.goto("http://localhost:5173")
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(output_dir, "01_home.png"))

        # 2. 清除之前的任务
        print("\n[2] 清除旧任务...")
        try:
            # 尝试找到并点击清除按钮或刷新
            close_btns = page.query_selector_all("[class*='close'], [class*='remove'], [class*='delete']")
            for btn in close_btns:
                try:
                    btn.click()
                    page.wait_for_timeout(300)
                except:
                    pass
        except:
            pass

        # 3. 输入富士 J150
        print("\n[3] 输入 '富士 J150'...")
        search_input = page.wait_for_selector("input.search-input", timeout=5000)
        search_input.fill("富士 J150")
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(output_dir, "02_keyword.png"))

        # 4. 点击估价
        print("\n[4] 点击估价...")
        btn = page.wait_for_selector("button.search-btn", timeout=5000)
        btn.click()

        # 5. 等待结果
        print("\n[5] 等待估价完成...")
        page.wait_for_timeout(90000)
        page.screenshot(path=os.path.join(output_dir, "03_result.png"), full_page=True)

        # 6. 检查样本列表
        print("\n[6] 检查样本列表...")
        samples = page.query_selector_all(".sample-item, a[href*='goofish']")
        print(f"   找到 {len(samples)} 个样本")

        fuji_count = 0
        other_brand_count = 0
        other_brands = []

        for i, sample in enumerate(samples[:10]):
            try:
                text = sample.inner_text()
                href = sample.get_attribute("href")

                # 检查是否是富士相关
                if any(kw in text.lower() for kw in ["富士", "j150", "jx", "j100", "finepix"]):
                    fuji_count += 1
                    print(f"   样本{i+1} [富士相关]: {text[:60]}...")
                else:
                    other_brand_count += 1
                    other_brands.append(text[:60])
                    print(f"   样本{i+1} [非富士] ❌: {text[:60]}...")

            except Exception as e:
                print(f"   样本{i+1} 错误: {e}")

        # 7. 总结
        print("\n" + "=" * 60)
        print("测试结果:")
        print(f"   富士相关样本: {fuji_count}")
        print(f"   非富士样本: {other_brand_count}")

        if other_brand_count > 0:
            print(f"\n   ❌ 发现 {other_brand_count} 个非富士样本!")
            print(f"   示例: {other_brands[:3]}")
        else:
            print(f"\n   ✅ 品牌过滤正常，所有样本都是富士相机")

        print("=" * 60)

        # 8. 截图
        page.screenshot(path=os.path.join(output_dir, "04_final.png"), full_page=True)

        print(f"\n截图保存在: {output_dir}")
        print("=" * 60)

        # 自动关闭
        browser.close()
        print("浏览器已关闭")

if __name__ == "__main__":
    main()
