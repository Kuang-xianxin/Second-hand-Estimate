"""
刷新闲鱼登录态 — Windows 上运行
打开浏览器 → 扫码登录 → 自动保存 storage state
"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT = Path(r"D:\my progect\估二手\xianyu_storage_state.json")


async def main():
    async with async_playwright() as p:
        # 用系统自带 Chromium（保留已有登录态）
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print("打开闲鱼登录页...")
        await page.goto("https://www.goofish.com", wait_until="domcontentloaded")
        print("请在浏览器中扫码登录闲鱼")
        print("登录成功后回到终端按 Enter...")

        # 等待用户登录
        await asyncio.get_event_loop().run_in_executor(None, input)

        # 保存 storage state
        await context.storage_state(path=str(OUTPUT))
        print(f"✅ 登录态已保存到: {OUTPUT}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
