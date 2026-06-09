/**
 * 刷新闲鱼登录态 — 使用全局 playwright
 * node refresh_xianyu_login.js
 */
const path = require('path');
// 全局安装路径
const pw = require('C:/Users/QQ276/AppData/Roaming/npm/node_modules/playwright');
const { chromium } = pw;
const OUTPUT = path.join(__dirname, 'xianyu_storage_state.json');

(async () => {
  const browser = await chromium.launch({
    headless: false,
    executablePath: 'C:/Users/QQ276/AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  console.log('打开闲鱼登录页...');
  await page.goto('https://www.goofish.com', { waitUntil: 'domcontentloaded' });
  console.log('');
  console.log('用闲鱼 APP 扫码登录，然后回终端按 Enter');

  await new Promise(r => process.stdin.once('data', r));

  await context.storageState({ path: OUTPUT });
  console.log('OK 已保存: ' + OUTPUT);
  await browser.close();
})();
