async function updateUI() {
  const data = await chrome.storage.local.get(['lastSync', 'status']);
  const statusEl = document.getElementById('status-text');
  const lastSyncEl = document.getElementById('last-sync');

  const statusMap = {
    ok: '<span class="dot ok"></span>已连接',
    error: '<span class="dot error"></span>同步失败',
    offline: '<span class="dot offline"></span>后端未启动'
  };
  statusEl.innerHTML = statusMap[data.status] || '<span class="dot offline"></span>未知';
  lastSyncEl.textContent = data.lastSync || '-';
}

document.getElementById('sync-btn').addEventListener('click', async () => {
  const btn = document.getElementById('sync-btn');
  btn.textContent = '同步中...';
  btn.disabled = true;
  await chrome.runtime.sendMessage({ action: 'syncNow' });
  setTimeout(async () => {
    await updateUI();
    btn.textContent = '立即同步 Cookie';
    btn.disabled = false;
  }, 1500);
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === 'syncNow') {
    chrome.runtime.sendMessage({ action: 'syncNow' });
  }
});

updateUI();
setInterval(updateUI, 2000);
