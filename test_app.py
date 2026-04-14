"""
自动化测试脚本 - 使用 Playwright 测试估二手应用
"""
import asyncio
import os
import sys
import time
import json
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser

# 项目路径
PROJECT_PATH = Path(r"d:\cursor项目文件\估二手")
TEST_RESULTS_PATH = PROJECT_PATH / "test_results"

# 确保测试结果目录存在
TEST_RESULTS_PATH.mkdir(exist_ok=True)

class TestRunner:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        self.console_errors = []

    async def init(self):
        """初始化浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        self.page = await self.context.new_page()

        # 设置控制台错误监听
        self.console_errors = []
        self.page.on("console", lambda msg: self.console_errors.append(msg.text) if msg.type == "error" else None)
        self.page.on("pageerror", lambda err: self.console_errors.append(f"Page Error: {str(err)}"))

        # 设置截图目录
        self.screenshot_dir = TEST_RESULTS_PATH / f"screenshots_{int(time.time())}"
        self.screenshot_dir.mkdir(exist_ok=True)

    async def take_screenshot(self, name: str):
        """截图"""
        path = self.screenshot_dir / f"{name}.png"
        await self.page.screenshot(path=str(path))
        print(f"  截图: {path}")
        return str(path)

    async def test_frontend_service(self) -> dict:
        """测试前端服务是否可访问"""
        result = {"name": "前端服务访问", "status": "pending", "details": "", "errors": []}

        try:
            response = await self.page.goto("http://localhost:5173", timeout=15000)
            if response and response.status == 200:
                result["status"] = "pass"
                result["details"] = f"前端服务响应正常 (HTTP {response.status})"
                await self.take_screenshot("01_frontend_loaded")
            else:
                result["status"] = "fail"
                result["details"] = f"响应状态码: {response.status if response else 'None'}"
        except Exception as e:
            result["status"] = "fail"
            result["details"] = str(e)

        self.results.append(result)
        return result

    async def test_backend_api(self) -> dict:
        """测试后端 API"""
        result = {"name": "后端API连接", "status": "pending", "details": "", "errors": []}

        try:
            response = await self.page.goto("http://localhost:8000/api/login-state", timeout=10000)
            if response and response.status == 200:
                result["status"] = "pass"
                result["details"] = "后端API正常响应"
            else:
                result["status"] = "fail"
                result["details"] = f"响应状态码: {response.status if response else 'None'}"
        except Exception as e:
            result["status"] = "fail"
            result["details"] = str(e)

        self.results.append(result)
        return result

    async def test_homepage_elements(self) -> dict:
        """测试首页元素"""
        result = {"name": "首页元素检查", "status": "pending", "details": "", "issues": []}

        await self.page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)  # 等待页面加载

        # 根据实际代码结构检查元素
        elements_to_check = {
            "搜索框": "input.search-input",
            "估价按钮": "button.search-btn",
            "模型选择按钮": "button.model-btn",
            "页面标题": "h1.page-title"
        }

        for name, selector in elements_to_check.items():
            try:
                element = await self.page.wait_for_selector(selector, timeout=5000)
                if element:
                    result["details"] += f"{name} [OK]; "
                else:
                    result["issues"].append(f"{name} 未找到 ({selector})")
            except Exception as e:
                result["issues"].append(f"{name} 未找到 ({selector}): {str(e)[:50]}")

        # 检查页面标题内容
        try:
            title = await self.page.text_content("h1.page-title")
            if title and "二手" in title:
                result["details"] += f"标题正确: {title[:20]}"
            else:
                result["issues"].append(f"标题不正确: {title}")
        except Exception as e:
            result["issues"].append(f"获取标题失败: {str(e)[:50]}")

        if result["issues"]:
            result["status"] = "warning"
        else:
            result["status"] = "pass"

        await self.take_screenshot("02_homepage_elements")
        self.results.append(result)
        return result

    async def test_valuation_flow(self) -> dict:
        """测试估价流程"""
        result = {"name": "估价流程测试", "status": "pending", "details": "", "issues": []}

        await self.page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)

        # 使用正确的选择器
        search_input = await self.page.wait_for_selector("input.search-input", timeout=5000)
        if not search_input:
            result["issues"].append("未找到搜索框")
            result["status"] = "fail"
            await self.take_screenshot("03_search_input_not_found")
            self.results.append(result)
            return result

        result["details"] += "搜索框已找到; "

        # 测试不同关键词
        test_keywords = ["SD卡 64G", "iPhone 14", "XD卡 2G"]

        for keyword in test_keywords:
            await search_input.fill(keyword)
            await asyncio.sleep(0.5)

            # 验证输入
            value = await search_input.input_value()
            if value == keyword:
                result["details"] += f"'{keyword}' [OK]; "
            else:
                result["issues"].append(f"'{keyword}' 输入失败")

            # 查找估价按钮
            submit_btn = await self.page.wait_for_selector("button.search-btn", timeout=3000)
            if submit_btn:
                result["details"] += f"估价按钮 [OK]; "
            else:
                result["issues"].append("估价按钮未找到")

            # 清空输入以便下次测试
            await search_input.fill("")

        # 检查控制台错误
        if self.console_errors:
            result["issues"].append(f"控制台错误: {len(self.console_errors)} 个")
            for err in self.console_errors[:3]:
                result["details"] += f"错误: {err[:50]}; "

        await self.take_screenshot("04_valuation_flow")
        result["status"] = "pass" if not result["issues"] else "warning"
        self.results.append(result)
        return result

    async def test_model_selection(self) -> dict:
        """测试模型选择"""
        result = {"name": "模型选择功能", "status": "pending", "details": "", "issues": []}

        await self.page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)

        # 检查模型按钮
        model_btns = await self.page.query_selector_all("button.model-btn")
        if len(model_btns) >= 2:
            result["details"] += f"找到 {len(model_btns)} 个模型按钮; "

            # 尝试点击模型按钮
            for btn in model_btns[:2]:
                text = await btn.text_content()
                if text:
                    await btn.click()
                    result["details"] += f"点击 {text.strip()} [OK]; "
                    await asyncio.sleep(0.3)
        else:
            result["issues"].append(f"模型按钮数量不足: {len(model_btns)}")

        await self.take_screenshot("05_model_selection")
        result["status"] = "pass" if not result["issues"] else "warning"
        self.results.append(result)
        return result

    async def test_bargains_page(self) -> dict:
        """测试捡漏页面"""
        result = {"name": "捡漏页面测试", "status": "pending", "details": "", "issues": []}

        try:
            await self.page.goto("http://localhost:5173/bargains", timeout=15000)
            await asyncio.sleep(2)

            page_content = await self.page.content()
            if "捡漏" in page_content:
                result["details"] += "捡漏页面加载成功; "
            else:
                result["issues"].append("页面内容不包含'捡漏'")

            await self.take_screenshot("06_bargains_page")

        except Exception as e:
            result["issues"].append(f"访问失败: {str(e)[:100]}")

        if result["issues"]:
            result["status"] = "warning"
        else:
            result["status"] = "pass"

        self.results.append(result)
        return result

    async def test_history_page(self) -> dict:
        """测试历史页面"""
        result = {"name": "历史页面测试", "status": "pending", "details": "", "issues": []}

        try:
            await self.page.goto("http://localhost:5173/history", timeout=15000)
            await asyncio.sleep(2)

            page_content = await self.page.content()
            if "历史" in page_content or "history" in page_content.lower():
                result["details"] += "历史页面加载成功; "
            else:
                result["issues"].append("历史页面内容不正确")

            await self.take_screenshot("07_history_page")

        except Exception as e:
            result["issues"].append(f"访问失败: {str(e)[:100]}")

        if result["issues"]:
            result["status"] = "warning"
        else:
            result["status"] = "pass"

        self.results.append(result)
        return result

    async def test_xd_card_search(self) -> dict:
        """测试 XD 卡搜索"""
        result = {"name": "XD卡搜索测试", "status": "pending", "details": "", "issues": []}

        await self.page.goto("http://localhost:5173", timeout=15000)
        await asyncio.sleep(2)

        # 测试 XD 卡相关关键词
        xd_keywords = ["XD卡", "XD卡 2G", "富士 XD卡", "奥林巴斯 XD卡", "SM卡", "xD卡"]

        search_input = await self.page.wait_for_selector("input.search-input", timeout=5000)
        if not search_input:
            result["issues"].append("搜索框未找到")
            result["status"] = "fail"
            self.results.append(result)
            return result

        successful_inputs = 0
        for keyword in xd_keywords:
            await search_input.fill(keyword)
            await asyncio.sleep(0.3)

            value = await search_input.input_value()
            if value == keyword:
                successful_inputs += 1
                result["details"] += f"'{keyword}' [OK]; "
            else:
                result["issues"].append(f"'{keyword}' 输入失败")

        result["details"] += f"成功输入 {successful_inputs}/{len(xd_keywords)} 个关键词"

        # 检查是否有关键词建议
        suggestions = await self.page.query_selector_all("[class*='suggest'], [class*='dropdown'], .search-box")
        if suggestions:
            result["details"] += f", 找到 {len(suggestions)} 个建议元素"

        await self.take_screenshot("08_xd_card_search")
        result["status"] = "pass"
        self.results.append(result)
        return result

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("开始自动化测试 - 估二手应用")
        print("=" * 60)

        tests = [
            ("前端服务访问", self.test_frontend_service),
            ("后端API连接", self.test_backend_api),
            ("首页元素检查", self.test_homepage_elements),
            ("估价流程测试", self.test_valuation_flow),
            ("模型选择功能", self.test_model_selection),
            ("捡漏页面测试", self.test_bargains_page),
            ("历史页面测试", self.test_history_page),
            ("XD卡搜索测试", self.test_xd_card_search),
        ]

        for i, (name, test_func) in enumerate(tests, 1):
            print(f"\n[{i}/{len(tests)}] {name}...")
            try:
                await test_func()
            except Exception as e:
                print(f"  测试异常: {e}")
                self.results.append({
                    "name": name,
                    "status": "fail",
                    "details": str(e),
                    "issues": [f"测试异常: {str(e)[:100]}"]
                })

        self.save_results()

    def save_results(self):
        """保存测试结果"""
        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["status"] == "pass"),
            "failed": sum(1 for r in self.results if r["status"] == "fail"),
            "warnings": sum(1 for r in self.results if r["status"] == "warning"),
            "results": self.results,
            "console_errors": self.console_errors
        }

        report_path = TEST_RESULTS_PATH / f"test_report_{int(time.time())}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 使用 ASCII 字符打印结果
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"总测试数: {summary['total']}")
        print(f"通过: {summary['passed']}")
        print(f"失败: {summary['failed']}")
        print(f"警告: {summary['warnings']}")
        print(f"\n详细报告: {report_path}")
        print(f"截图目录: {self.screenshot_dir}")
        print(f"控制台错误数: {len(self.console_errors)}")

        for r in self.results:
            status_icon = "[PASS]" if r["status"] == "pass" else ("[WARN]" if r["status"] == "warning" else "[FAIL]")
            print(f"\n{status_icon} {r['name']}: {r['status']}")
            if r.get("details"):
                print(f"  详情: {r['details']}")
            if r.get("issues"):
                print(f"  问题: {r['issues']}")

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

async def main():
    runner = TestRunner()
    try:
        await runner.init()
        await runner.run_all_tests()
    finally:
        await runner.close()

if __name__ == "__main__":
    asyncio.run(main())
