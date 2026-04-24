"""
闲鱼登录态保存脚本 v2 — 等待登录跳转完成后保存 cookies。
运行: cd backend && python save_xianyu_state_v2.py
"""
import json
import pathlib
import time
from playwright.sync_api import sync_playwright

BASE_DIR = pathlib.Path(__file__).resolve().parent
STORAGE_STATE_FILE = BASE_DIR / "xianyu_storage_state.json"


def main():
    print("=" * 60)
    print("闲鱼登录态保存脚本 v2")
    print("=" * 60)
    print()
    print("本脚本会：")
    print("  1. 打开浏览器并导航到闲鱼")
    print("  2. 检测登录状态 — 若未登录则打开登录页")
    print("  3. 等待登录跳转完成后，再额外等待 5 秒让 cookies 写入")
    print("  4. 自动保存登录态到文件")
    print()
    print("请在浏览器中完成登录，不要关闭浏览器。")
    print("脚本会在检测到已登录后自动保存并退出。")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
        )

        # 先尝试加载现有状态，看是否已登录
        if STORAGE_STATE_FILE.exists():
            try:
                context.storage_state(path=str(STORAGE_STATE_FILE))
                page = context.new_page()
                page.goto('https://www.goofish.com/', timeout=15000)
                page.wait_for_timeout(2000)
                page_text = page.content()
                if '登录' not in page_text and 'login' not in page_text.lower():
                    print("检测：已存在登录态且有效！")
                    print("若需重新登录，请先删除 xianyu_storage_state.json 文件。")
                    browser.close()
                    return
                else:
                    print("检测：已存在登录态但可能已过期，将尝试刷新...")
                    page.close()
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                        viewport={'width': 1280, 'height': 800},
                    )
            except Exception as e:
                print(f"加载已有状态失败: {e}，将重新登录")

        page = context.new_page()

        # 拦截 cookie 设置请求，记录关键 cookie
        intercepted_cookies = {}

        def on_response(response):
            url = response.url
            # 闲鱼登录成功后会在这些域名设置 cookie
            if any(domain in url for domain in ['goofish.com', 'taobao.com', 'alicdn.com', 'alibaba.com']):
                try:
                    for set_cookie in response.headers.get_all('set-cookie') or []:
                        if '=' in set_cookie:
                            name = set_cookie.split('=')[0].strip()
                            if name not in intercepted_cookies:
                                intercepted_cookies[name] = set_cookie
                except Exception:
                    pass

        page.on('response', on_response)

        print("\n正在打开闲鱼...")
        try:
            page.goto('https://www.goofish.com/', wait_until='domcontentloaded', timeout=20000)
        except Exception as e:
            print(f"初始加载: {e}")

        page.wait_for_timeout(3000)

        # 检测是否在登录页
        page_text = page.content()
        is_login_page = any(x in page_text.lower() for x in ['登录', 'login', '请先登录', '扫码'])

        if is_login_page:
            print("检测到登录页，请在浏览器中完成登录...")
            print("（提示：使用二维码登录通常最可靠）")

            # 等待 URL 变化（登录成功后会跳转到 goofish.com）
            max_wait = 180
            start_time = time.time()
            last_url = page.url

            while time.time() - start_time < max_wait:
                page.wait_for_timeout(2000)
                current_url = page.url

                # 检测登录成功的标志：URL 不再是 passport.goofish.com
                if 'passport' not in current_url and 'login' not in current_url.lower():
                    # 再等 5 秒确保 cookie 写入
                    print(f"检测到登录跳转完成 (URL: {current_url[:60]})，等待 5 秒让 cookies 写入...")
                    page.wait_for_timeout(5000)
                    break

                if current_url != last_url:
                    print(f"  URL 变化: {last_url[:50]} -> {current_url[:50]}")
                    last_url = current_url

            else:
                print("等待登录超时，请手动在浏览器中完成登录后按 Enter...")

        else:
            print("检测到可能已登录，保存当前状态...")

        # 额外等待确保所有 cookie 写入
        print("等待 3 秒后保存登录态...")
        page.wait_for_timeout(3000)

        # 保存前打印所有拦截到的 cookie
        if intercepted_cookies:
            print(f"\n拦截到 {len(intercepted_cookies)} 个 cookie:")
            for name in list(intercepted_cookies.keys())[:10]:
                print(f"  {name}")
        else:
            print("\n未拦截到 set-cookie 响应（HttpOnly cookies 不会出现在这里）")

        # 获取最终 cookies
        final_cookies = context.cookies()
        print(f"\n当前 BrowserContext 中共有 {len(final_cookies)} 个 cookies")

        # 打印非 HttpOnly 的 cookies
        non_httponly = [c for c in final_cookies if not c.get('httpOnly', False)]
        if non_httponly:
            print(f"  其中 {len(non_httponly)} 个非 HttpOnly:")
            for c in non_httponly[:5]:
                print(f"    {c['name']}={c['value'][:20]}...")
        else:
            print("  所有 cookie 都是 HttpOnly（无法通过 storage_state 保存）")

        httponly = [c for c in final_cookies if c.get('httpOnly', False)]
        if httponly:
            print(f"  {len(httponly)} 个 HttpOnly cookie:")
            for c in httponly[:5]:
                print(f"    {c['name']} (httpOnly=True, value长度={len(c['value'])})")

        # 保存 storage_state
        context.storage_state(path=str(STORAGE_STATE_FILE))
        print(f"\n已保存 storage_state 到: {STORAGE_STATE_FILE}")

        # 验证保存结果
        saved = json.loads(STORAGE_STATE_FILE.read_text(encoding='utf-8'))
        print(f"验证：saved cookies count = {len(saved.get('cookies', []))}")
        print(f"验证：saved origins count = {len(saved.get('origins', []))}")

        browser.close()

        print("\n" + "=" * 60)
        if saved.get('cookies'):
            print("SUCCESS: 登录态已保存，cookies 不为空！")
            print("可以运行 python main.py 测试爬虫了。")
        else:
            print("WARNING: cookies 仍为空")
            print("原因：闲鱼登录 cookie 全部为 HttpOnly，storage_state 无法保存。")
            print("替代方案：使用 xianyu_cookies.txt 手动粘贴 cookie 字符串。")
        print("=" * 60)


if __name__ == '__main__':
    main()
