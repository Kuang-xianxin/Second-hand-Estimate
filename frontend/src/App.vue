<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getBargains, getCrawlProgress, getCacheStatus, getAuthToken } from '@/api'
import type { CrawlProgress, CacheStatus } from '@/types'

// 未读捡漏提醒数量（显示在导航栏徽标上）
const unreadCount = ref(0)
// 主题状态：true=深色模式，false=浅色模式
const isDark = ref(true)

// 登录状态
const loggedIn = ref(false)
function checkLogin() {
  loggedIn.value = !!getAuthToken()
}

// 爬取进度状态
const crawlProgress = ref<CrawlProgress | null>(null)
const cacheStatus = ref<CacheStatus | null>(null)
let crawlTimer: ReturnType<typeof setInterval> | null = null

// 爬取状态标签
const crawlLabel = ref('')
const crawlPercent = ref(0)

function toggleTheme() {
  isDark.value = !isDark.value
  document.body.classList.toggle('light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

async function loadUnread() {
  try {
    const data = await getBargains(true)
    unreadCount.value = data.length
  } catch {
    // ignore
  }
}

async function loadCrawlStatus() {
  try {
    const [progress, status] = await Promise.all([
      getCrawlProgress(),
      getCacheStatus(),
    ])
    crawlProgress.value = progress
    cacheStatus.value = status

    // 计算爬取状态标签
    if (progress) {
      const stage = progress.stage || ''
      crawlPercent.value = progress.total > 0 ? Math.min(100, Math.round((progress.done / progress.total) * 100)) : 0
      if (stage.includes('完成') || stage.includes('completed')) {
        crawlLabel.value = '爬取完成'
      } else if (stage.includes('失败') || stage.includes('failed')) {
        crawlLabel.value = '爬取出错'
      } else if (stage.includes('空闲') || stage.includes('idle')) {
        crawlLabel.value = ''
      } else {
        crawlLabel.value = `${stage} ${crawlPercent.value}%`
      }
    } else {
      crawlLabel.value = ''
    }
  } catch {
    crawlLabel.value = ''
  }
}

onMounted(() => {
  const saved = localStorage.getItem('theme')
  if (saved === 'light') {
    isDark.value = false
    document.body.classList.add('light')
  }
  checkLogin()
  if (loggedIn.value) {
    loadUnread()
    loadCrawlStatus()
    crawlTimer = setInterval(loadCrawlStatus, 5000)
  }
})

onUnmounted(() => {
  if (crawlTimer) {
    clearInterval(crawlTimer)
    crawlTimer = null
  }
})
</script>

<template>
  <div class="app-shell">
    <nav class="navbar">
      <div class="nav-brand">
        <span class="brand-icon">估</span>
        <span class="brand-name">估二手</span>
      </div>
      <div class="nav-actions">
        <div class="nav-links">
          <router-link to="/" class="nav-link" active-class="active">估价</router-link>
          <router-link to="/bargains" class="nav-link" active-class="active">
            捡漏
            <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
          </router-link>
          <router-link to="/history" class="nav-link" active-class="active">记录</router-link>
        </div>
        <!-- 后台爬取状态指示器 -->
        <div v-if="crawlLabel" class="crawl-indicator" :title="'后台任务：' + crawlLabel">
          <div class="crawl-dot"></div>
          <span class="crawl-label">{{ crawlLabel }}</span>
        </div>
        <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换日间模式' : '切换夜间模式'">
          <span class="theme-icon">{{ isDark ? '🌙' : '☀️' }}</span>
        </button>
      </div>
    </nav>

    <div class="disclaimer-bar">
      <span>
        本网站数据来源于公开的闲鱼平台，仅供个人学习与估价参考，不构成任何交易承诺。
        请遵守闲鱼平台服务条款，合理使用。
      </span>
    </div>

    <main class="main-content">
      <router-view v-slot="{ Component }">
        <keep-alive include="HomeView">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.navbar {
  height: 58px;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  width: 34px;
  height: 34px;
  background: var(--accent);
  color: #0e0e10;
  font-weight: 700;
  font-size: 18px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--accent);
}

.nav-links {
  display: flex;
  gap: 6px;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.theme-toggle {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 16px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.theme-toggle:hover {
  background: var(--accent);
  border-color: var(--accent);
}

.theme-toggle:hover .theme-icon {
  filter: brightness(0);
}

.nav-link {
  padding: 6px 18px;
  border-radius: 6px;
  font-size: 14px;
  color: var(--text2);
  transition: all 0.2s;
  position: relative;
  text-decoration: none;
}

.nav-link:hover {
  color: var(--text);
  background: var(--bg3);
}

.nav-link.active {
  color: var(--accent);
  background: rgba(232, 197, 71, 0.1);
}

.badge {
  position: absolute;
  top: 2px;
  right: 4px;
  background: var(--red);
  color: #fff;
  font-size: 10px;
  font-family: var(--font-mono);
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.crawl-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  background: rgba(232, 197, 71, 0.1);
  border: 1px solid rgba(232, 197, 71, 0.25);
  border-radius: 12px;
  padding: 3px 8px;
  cursor: default;
}

.crawl-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  animation: crawlPulse 1.5s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes crawlPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.crawl-label {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--accent);
  white-space: nowrap;
}

.disclaimer-bar {
  background: var(--disclaimer-bg);
  border-bottom: 1px solid var(--disclaimer-border);
  padding: 6px 32px;
  text-align: center;
  font-size: 11px;
  color: var(--disclaimer-text);
  letter-spacing: 0.3px;
}

.main-content {
  flex: 1;
  padding: 40px 32px;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
}

/* ========== 导航栏移动端响应式 ========== */
@media (max-width: 600px) {
  .navbar {
    height: auto;
    min-height: 52px;
    padding: 10px 16px;
    flex-wrap: wrap;
    gap: 8px;
  }

  .nav-brand {
    gap: 8px;
  }

  .brand-icon {
    width: 30px;
    height: 30px;
    font-size: 16px;
  }

  .brand-name {
    font-size: 18px;
    letter-spacing: 1px;
  }

  .nav-actions {
    gap: 8px;
  }

  .nav-link {
    padding: 5px 12px;
    font-size: 13px;
  }

  .theme-toggle {
    padding: 5px 8px;
    font-size: 14px;
    min-height: 36px;
    min-width: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .badge {
    top: 0;
    right: 0;
    width: 14px;
    height: 14px;
    font-size: 9px;
  }

  .crawl-indicator {
    padding: 2px 6px;
  }

  .crawl-label {
    font-size: 10px;
  }

  .disclaimer-bar {
    padding: 5px 16px;
    font-size: 10px;
  }

  .main-content {
    padding: 20px 16px;
  }
}

@media (max-width: 400px) {
  .brand-name {
    display: none;
  }
}
</style>
