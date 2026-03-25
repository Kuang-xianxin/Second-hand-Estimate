import pathlib
from playwright.sync_api import sync_playwright

BASE_DIR = pathlib.Path(__file__).resolve().parent
STORAGE_STATE_FILE = BASE_DIR / "xianyu_storage_state.json"


def main():
    print("将打开浏览器，请在闲鱼里完成登录。")
    print("登录成功并确认能看到你的账号状态后，回到终端按 Enter 保存登录态。")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1440, 'height': 900},
        )
        page = context.new_page()
        page.goto('https://www.goofish.com/', wait_until='domcontentloaded', timeout=30000)
        input("登录完成后按 Enter 保存登录态...")
        context.storage_state(path=str(STORAGE_STATE_FILE))
        print(f"登录态已保存到: {STORAGE_STATE_FILE}")
        browser.close()


if __name__ == '__main__':
    main()
