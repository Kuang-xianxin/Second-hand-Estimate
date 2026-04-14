"""
深度UI测试 - 验证样本详情、XD卡标记、捡漏标签
"""
import asyncio
import json
import time
import os
from playwright.async_api import async_playwright
from datetime import datetime

class DeepUITest:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.results = {
            "samples_checked": [],
            "xd_card_found": [],
            "issues": [],
            "screenshots": []
        }
        self.screenshot_dir = None

    async def init(self):
        """初始化浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # 显示浏览器
            args=['--start-maximized']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True
        )
        self.page = await self.context.new_page()

        # 创建带时间戳的截图目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshot_dir = f"d:/cursor项目文件/估二手/test_results/deep_test_{timestamp}"
        os.makedirs(self.screenshot_dir, exist_ok=True)

        print(f"截图目录: {self.screenshot_dir}")

    async def screenshot(self, name: str, full_page: bool = False):
        """截图并保存"""
        path = f"{self.screenshot_dir}/{name}.png"
        await self.page.screenshot(path=path, full_page=full_page)
        self.results["screenshots"].append(path)
        print(f"  截图: {name}.png")
        return path

    async def wait_for_result(self, timeout: int = 90):
        """等待估价结果出现（价格区间）"""
        print("  等待估价结果...")
        start = time.time()
        while time.time() - start < timeout:
            # 检查是否显示了价格
            try:
                price_elem = await self.page.query_selector("[class*='price']")
                if price_elem:
                    text = await price_elem.text_content()
                    if text and "¥" in text:
                        print(f"  检测到价格: {text}")
                        return True
            except:
                pass

            # 检查是否显示基准价
            try:
                algo_elem = await self.page.query_selector("[class*='algo']")
                if algo_elem:
                    text = await algo_elem.text_content()
                    if text and "基准" in text:
                        print(f"  检测到基准价区域")
                        return True
            except:
                pass

            await asyncio.sleep(2)

        return False

    async def test_homepage_and_valuation(self):
        """测试首页估价流程"""
        print("\n" + "=" * 70)
        print("深度UI测试 - 首页估价流程")
        print("=" * 70)

        # 1. 访问首页
        print("\n[1] 访问首页...")
        await self.page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(3)
        await self.screenshot("01_homepage")

        # 2. 输入XD卡相关关键词
        print("\n[2] 输入测试关键词...")
        search_input = await self.page.wait_for_selector("input.search-input", timeout=5000)

        # 测试多个XD卡机型
        test_keywords = ["富士 J150", "富士 JX680", "奥林巴斯 TG"]

        for keyword in test_keywords:
            print(f"\n--- 测试: {keyword} ---")

            await search_input.fill(keyword)
            await asyncio.sleep(0.5)
            await self.screenshot(f"02_search_{keyword.replace(' ', '_')}")

            # 点击新增并行
            parallel_btn = await self.page.wait_for_selector("button:has-text('新增并行')", timeout=3000)
            await parallel_btn.click()
            print(f"  已点击新增并行")

            # 等待任务出现
            await asyncio.sleep(1)

        # 截图当前状态
        await self.screenshot("03_multiple_tasks")

        # 3. 等待估价完成
        print("\n[3] 等待估价完成...")
        await self.wait_for_result(timeout=120)
        await asyncio.sleep(5)  # 额外等待确保所有数据加载
        await self.screenshot("04_valuation_results")

    async def check_samples_detail(self):
        """检查样本详情"""
        print("\n" + "=" * 70)
        print("深度UI测试 - 样本详情检查")
        print("=" * 70)

        # 截图当前页面
        await self.screenshot("05_samples_before")

        # 查找所有样本项
        print("\n[4] 检查样本列表...")

        # 尝试多种选择器
        sample_selectors = [
            ".sample-item",
            "[class*='sample']",
            "[class*='item']:not([class*='bargain'])",
            ".card",
        ]

        samples = []
        for selector in sample_selectors:
            try:
                samples = await self.page.query_selector_all(selector)
                if len(samples) > 3:
                    print(f"  使用选择器: {selector}")
                    print(f"  找到 {len(samples)} 个样本")
                    break
            except:
                continue

        # 检查每个样本
        sample_info = []
        for i, sample in enumerate(samples[:5]):  # 只检查前5个
            try:
                # 获取标题
                title_elem = await sample.query_selector("[class*='title'], .title")
                title = await title_elem.text_content() if title_elem else "无标题"

                # 获取价格
                price_elem = await sample.query_selector("[class*='price']")
                price = await price_elem.text_content() if price_elem else "无价格"

                # 获取成色
                condition_elem = await sample.query_selector("[class*='condition']")
                condition = await condition_elem.text_content() if condition_elem else "未标注"

                # 检查XD卡标签
                xd_badge = await sample.query_selector("[class*='xd'], [class*='XD'], [class*='card-badge']")
                has_xd_tag = xd_badge is not None

                # 检查质量分
                score_elem = await sample.query_selector("[class*='score'], [class*='质量']")
                score = await score_elem.text_content() if score_elem else "无"

                # 获取URL（如果有链接）
                link = await sample.get_attribute("href")
                url = link if link else ""

                sample_info.append({
                    "index": i + 1,
                    "title": title[:60] if title else "",
                    "price": price,
                    "condition": condition,
                    "has_xd_tag": has_xd_tag,
                    "quality_score": score,
                    "url": url
                })

                print(f"\n  样本 {i+1}:")
                print(f"    标题: {title[:60]}...")
                print(f"    价格: {price}")
                print(f"    成色: {condition}")
                print(f"    XD卡标签: {'有' if has_xd_tag else '无'}")
                print(f"    质量分: {score}")
                if url:
                    print(f"    URL: {url[:80]}...")

                self.results["samples_checked"].append({
                    "title": title,
                    "price": price,
                    "has_xd_tag": has_xd_tag
                })

                if has_xd_tag:
                    self.results["xd_card_found"].append(title)

            except Exception as e:
                print(f"  样本 {i+1} 检查失败: {str(e)[:50]}")
                self.results["issues"].append(f"样本{i+1}: {str(e)[:50]}")

        # 截图样本列表
        await self.screenshot("06_samples_list")

        return sample_info

    async def check_bargains_detail(self):
        """检查捡漏详情"""
        print("\n" + "=" * 70)
        print("深度UI测试 - 捡漏详情检查")
        print("=" * 70)

        # 访问捡漏页面
        print("\n[5] 访问捡漏页面...")
        await self.page.goto("http://localhost:5173/bargains", timeout=15000)
        await asyncio.sleep(3)
        await self.screenshot("07_bargains_page")

        # 查找所有捡漏项
        bargain_selectors = [
            ".bargain-item",
            "[class*='bargain']",
            "[class*='alert']",
            ".card"
        ]

        bargains = []
        for selector in bargain_selectors:
            try:
                bargains = await self.page.query_selector_all(selector)
                if len(bargains) > 0:
                    print(f"  使用选择器: {selector}")
                    print(f"  找到 {len(bargains)} 个捡漏项")
                    break
            except:
                continue

        # 检查每个捡漏项
        bargain_info = []
        for i, bargain in enumerate(bargains[:10]):  # 检查前10个
            try:
                # 获取标题
                title_elem = await bargain.query_selector("[class*='title']")
                title = await title_elem.text_content() if title_elem else "无标题"

                # 获取价格
                price_elem = await bargain.query_selector("[class*='price']")
                price = await price_elem.text_content() if price_elem else "无价格"

                # 获取利润
                profit_elem = await bargain.query_selector("[class*='profit']")
                profit = await profit_elem.text_content() if profit_elem else "无"

                # 检查XD卡标记
                xd_badge = await bargain.query_selector("[class*='xd-card'], [class*='XD'], [class*='card-badge']")
                has_xd_badge = xd_badge is not None
                xd_text = await xd_badge.text_content() if xd_badge else ""

                # 获取链接
                link = await bargain.get_attribute("href")
                url = link if link else ""

                bargain_info.append({
                    "index": i + 1,
                    "title": title[:60] if title else "",
                    "price": price,
                    "profit": profit,
                    "has_xd_badge": has_xd_badge,
                    "xd_text": xd_text,
                    "url": url
                })

                print(f"\n  捡漏 {i+1}:")
                print(f"    标题: {title[:60]}...")
                print(f"    价格: {price}")
                print(f"    利润: {profit}")
                print(f"    XD卡标记: {'有 - ' + xd_text if has_xd_badge else '无'}")

                if url:
                    print(f"    闲鱼链接: {url[:80]}...")

                if has_xd_badge:
                    self.results["xd_card_found"].append(f"捡漏-{title[:30]}")

            except Exception as e:
                print(f"  捡漏 {i+1} 检查失败: {str(e)[:50]}")
                self.results["issues"].append(f"捡漏{i+1}: {str(e)[:50]}")

        await self.screenshot("08_bargains_detail")

        return bargain_info

    async def open_sample_link(self):
        """尝试打开样本链接（验证URL是否正确）"""
        print("\n" + "=" * 70)
        print("深度UI测试 - 样本链接验证")
        print("=" * 70)

        print("\n[6] 验证样本链接...")

        # 返回首页查看最新估价结果
        await self.page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)

        # 查找链接
        links = await self.page.query_selector_all("a[href*='goofish'], a[href*='xianyu'], a[href*='item']")

        print(f"  找到 {len(links)} 个闲鱼相关链接")

        valid_urls = 0
        for i, link in enumerate(links[:5]):  # 检查前5个
            try:
                url = await link.get_attribute("href")
                if url and ("goofish" in url or "xianyu" in url or "item" in url):
                    print(f"  链接 {i+1}: {url[:80]}...")
                    valid_urls += 1

                    # 尝试点击（在后台新标签页打开）
                    # 注意：不真正等待加载，只是验证链接格式
                    if i == 0:  # 只测试第一个
                        await link.click(button="middle")  # 中键在新标签页打开
                        await asyncio.sleep(2)

                        # 检查是否打开了新页面
                        new_pages = await self.context.pages
                        if len(new_pages) > 1:
                            print(f"    [OK] 新标签页已打开: {len(new_pages)} 个页面")
                            # 关闭新标签页
                            await new_pages[-1].close()
                        else:
                            print(f"    [INFO] 未打开新标签页")

            except Exception as e:
                print(f"  链接 {i+1} 检查失败: {str(e)[:50]}")

        await self.screenshot("09_links_check")

        return valid_urls

    async def check_xd_card_recognition(self):
        """检查XD卡识别是否正确"""
        print("\n" + "=" * 70)
        print("深度UI测试 - XD卡识别验证")
        print("=" * 70)

        print("\n[7] 检查XD卡识别逻辑...")

        # 检查是否有XD卡确认提示
        xd_confirm = await self.page.query_selector("[class*='xd_confirmed'], [class*='xd-confirm'], [class*='info']:has-text('XD')")
        if xd_confirm:
            text = await xd_confirm.text_content()
            print(f"  检测到XD卡确认信息: {text[:100]}...")
            self.results["xd_card_found"].append(f"确认提示: {text[:50]}")
        else:
            print("  未检测到XD卡确认提示（可能当前关键词不是XD卡机型）")

        # 检查样本中是否有XD卡标签
        sample_with_xd = await self.page.query_selector_all("[class*='xd-card'], [class*='XD'], [class*='sd-card']")
        if sample_with_xd:
            print(f"  样本中检测到XD卡相关标签: {len(sample_with_xd)} 个")
            for i, elem in enumerate(sample_with_xd[:3]):
                text = await elem.text_content()
                print(f"    {i+1}: {text}")
                self.results["xd_card_found"].append(text)
        else:
            print("  样本中未检测到XD卡标签")

        await self.screenshot("10_xd_card_check")

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "#" * 70)
        print("# 深度UI自动化测试开始")
        print("#" * 70)

        try:
            await self.init()

            # 1. 估价流程
            await self.test_homepage_and_valuation()

            # 2. 检查样本详情
            sample_info = await self.check_samples_detail()

            # 3. 检查捡漏详情
            bargain_info = await self.check_bargains_detail()

            # 4. 验证链接
            await self.open_sample_link()

            # 5. 检查XD卡识别
            await self.check_xd_card_recognition()

        except Exception as e:
            print(f"\n测试异常: {e}")
            import traceback
            traceback.print_exc()
            self.results["issues"].append(f"测试异常: {str(e)}")

        finally:
            # 保存报告
            self.save_report()

            print("\n" + "#" * 70)
            print("# 测试完成！按回车键关闭浏览器...")
            print("#" * 70)
            input()

            if self.browser:
                await self.browser.close()

    def save_report(self):
        """保存测试报告"""
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "samples_checked": self.results["samples_checked"],
            "xd_card_found": self.results["xd_card_found"],
            "issues": self.results["issues"],
            "screenshots": self.results["screenshots"],
            "summary": {
                "total_samples": len(self.results["samples_checked"]),
                "xd_card_samples": len([s for s in self.results["samples_checked"] if s.get("has_xd_tag")]),
                "xd_card_items": len(self.results["xd_card_found"]),
                "total_issues": len(self.results["issues"]),
                "total_screenshots": len(self.results["screenshots"])
            }
        }

        report_path = f"{self.screenshot_dir}/deep_test_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 70)
        print("测试报告")
        print("=" * 70)
        print(f"\n检查的样本数: {report['summary']['total_samples']}")
        print(f"带有XD卡标签的样本: {report['summary']['xd_card_samples']}")
        print(f"XD卡相关项目: {report['summary']['xd_card_items']}")
        print(f"发现的问题: {report['summary']['total_issues']}")
        print(f"截图数量: {report['summary']['total_screenshots']}")

        if self.results["xd_card_found"]:
            print(f"\nXD卡相关内容:")
            for item in self.results["xd_card_found"]:
                print(f"  - {item}")

        if self.results["issues"]:
            print(f"\n发现的问题:")
            for issue in self.results["issues"]:
                print(f"  - {issue}")

        print(f"\n报告路径: {report_path}")
        print(f"截图目录: {self.screenshot_dir}")
        print("=" * 70)

async def main():
    test = DeepUITest()
    await test.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
