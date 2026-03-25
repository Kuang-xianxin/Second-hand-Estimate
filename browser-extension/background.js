const BACKEND_URL = 'http://localhost:8000/api/sync-cookie';
const GOOFISH_DOMAIN = '.goofish.com';
const SYNC_INTERVAL_MINUTES = 5;

async function getCookieString() {
  const cookies = await chrome.cookies.getAll({ domain: GOOFISH_DOMAIN });
  if (!cookies || cookies.length === 0) return null;
  return cookies.map(c => `${c.name}=${c.value}`).join('; ');
}

async function syncCookie() {
  const cookieStr = await getCookieString();
  if (!cookieStr) {
    console.log('[估二手] 未找到闲鱼 Cookie');
    return;
  }
  try {
    const resp = await fetch(BACKEND_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookie: cookieStr })
    });
    if (resp.ok) {
      console.log('[估二手] Cookie 同步成功');
      await chrome.storage.local.set({
        lastSync: new Date().toLocaleString('zh-CN'),
        status: 'ok'
      });
    } else {
      console.warn('[估二手] Cookie 同步失败:', resp.status);
      await chrome.storage.local.set({ status: 'error' });
    }
  } catch (e) {
    console.warn('[估二手] 连接后端失败（后端未启动？）:', e.message);
    await chrome.storage.local.set({ status: 'offline' });
  }
}

// 监听 Cookie 变化，实时同步
chrome.cookies.onChanged.addListener(async (changeInfo) => {
  const cookie = changeInfo.cookie;
  if (cookie.domain.includes('goofish.com') || cookie.domain.includes('taobao.com')) {
    await syncCookie();
  }
});

// 定时同步（每5分钟）
chrome.alarms.create('sync-cookie', { periodInMinutes: SYNC_INTERVAL_MINUTES });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'sync-cookie') {
    await syncCookie();
  }
});

// 启动时立即同步一次
chrome.runtime.onInstalled.addListener(syncCookie);
chrome.runtime.onStartup.addListener(syncCookie);
