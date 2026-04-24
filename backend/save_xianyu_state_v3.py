"""
闲鱼登录态保存脚本 v3 — 改进版：重试加载 + 等待登录跳转 + 延长 cookie 写入时间。
运行: cd backend && python save_xianyu_state_v3.py
"""
import json
import pathlib
import time
import sys
from playwright.sync_api import sync_playwright

BASE_DIR = pathlib.Path(__file__).resolve().parent
STORAGE_STATE_FILE = BASE_DIR / "xianyu_storage_state.json"


def wait_for_login_and_save(browser, context):
    """等待用户登录完成后保存 storage_state。返回 (cookies_count, origins_count)。"""
    page = context.new_page()

    # 重试加载闲鱼首页
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        print(f"\n正在打开闲鱼... (尝试 {attempt}/{max_retries})")
        try:
            page.goto('https://www.goofish.com/', wait_until='domcontentloaded', timeout=30000)
            print(f"  页面加载成功，当前 URL: {page.url[:80]}")
            break
        except Exception as e:
            print(f"  加载失败: {e}")
            if attempt == max_retries:
                print("  重试次数用尽，继续尝试...")
                # 仍然继续，等待用户操作
            time.sleep(2)

    print("\n" + "=" * 60)
    print("请在浏览器中完成登录：")
    print("  - 如果还没登录：用手机扫码或账号密码登录")
    print("  - 如果已登录：直接跳到下一步")
    print("  - 登录成功的标志：页面显示你的账号名或能看到商品列表")
    print("=" * 60)

    # 等待 URL 稳定且不再包含登录相关路径
    max_wait = 300  # 5 分钟超时
    start = time.time()
    last_url = page.url
    login_detected_at = None
    redirect_complete = False

    while time.time() - start < max_wait:
        page.wait_for_timeout(2000)
        current_url = page.url

        # 登录成功后 URL 会从 passport.goofish.com 跳回 www.goofish.com
        on_passport = 'passport' in current_url or 'login' in current_url.lower()
        on_goofish = 'goofish.com' in current_url and not on_passport

        if on_passport:
            if current_url != last_url:
                print(f"  [登录中] URL: {current_url[:60]}")
            last_url = current_url
            login_detected_at = None  # 重置
        elif on_goofish:
            if not redirect_complete:
                if login_detected_at is None:
                    login_detected_at = time.time()
                    print(f"\n检测到登录跳转完成！URL: {current_url[:60]}")
                    print("等待 10 秒让闲鱼服务器写入所有 cookies...")
                elapsed = time.time() - login_detected_at
                remaining = max(0, 10 - elapsed)
                if remaining > 0:
                    print(f"  等待中... ({remaining:.0f}s remaining)")
                    time.sleep(min(remaining, 2))
                else:
                    redirect_complete = True
                    print("等待完成，准备保存登录态...")
                    break

        last_url = current_url

    # 额外等待 5 秒确保所有 cookie 都写入
    print("额外等待 5 秒确保 cookie 完整...")
    time.sleep(5)

    # 获取并打印 cookies
    all_cookies = context.cookies()
    print(f"\n当前 BrowserContext 中共有 {len(all_cookies)} 个 cookies:")
    for c in all_cookies:
        ho = " [HttpOnly]" if c.get('httpOnly') else ""
        val_preview = c['value'][:25] + "..." if len(c['value']) > 25 else c['value']
        print(f"  {c['name']}={val_preview}{ho}")

    # 保存 storage_state
    context.storage_state(path=str(STORAGE_STATE_FILE))
    print(f"\n已保存 storage_state 到: {STORAGE_STATE_FILE}")

    # 验证
    saved = json.loads(STORAGE_STATE_FILE.read_text(encoding='utf-8'))
    saved_cookies = saved.get('cookies', [])
    saved_origins = saved.get('origins', [])
    print(f"验证：cookies count = {len(saved_cookies)}, origins count = {len(saved_origins)}")

    return len(saved_cookies), len(saved_origins)


def main():
    print("=" * 60)
    print("闲鱼登录态保存脚本 v3")
    print("=" * 60)

    # 检查是否已有有效登录态
    if STORAGE_STATE_FILE.exists():
        try:
            existing = json.loads(STORAGE_STATE_FILE.read_text(encoding='utf-8'))
            if existing.get('cookies'):
                print(f"\n发现已保存的登录态 ({len(existing.get('cookies', []))} cookies)")
                confirm = input("是否要重新登录？(y/n, 默认 n): ").strip().lower()
                if confirm != 'y':
                    print("保留现有登录态，退出。")
                    return
        except Exception:
            pass

    print("\n打开浏览器中...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--no-first-run', '--disable-blink-features=AutomationControlled'],
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
        )

        cookies_count, origins_count = wait_for_login_and_save(browser, context)

        browser.close()

    print("\n" + "=" * 60)
    if cookies_count > 0:
        print("SUCCESS: 登录态已保存！cookies 不为空！")
        print("现在可以运行 python main.py 测试爬虫了。")
    else:
        print("WARNING: cookies 为空")
        print("可能原因：")
        print("  1. 闲鱼 cookie 为 HttpOnly，无法通过 storage_state 保存")
        print("  2. 请改用 export_xianyu_cookies.py 从 DevTools 手动导出 cookie")
    print("=" * 60)


if __name__ == '__main__':
    main()
