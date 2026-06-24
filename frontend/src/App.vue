<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getBargains } from '@/api'

// 未读捡漏提醒数量（显示在导航栏徽标上）
const unreadCount = ref(0)
// 主题状态：true=深色模式，false=浅色模式
const isDark = ref(true)

// 切换深色/浅色主题，更新 body class 并保存偏好到 localStorage
function toggleTheme() {
  isDark.value = !isDark.value
  document.body.classList.toggle('light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

// 从后端加载未读捡漏提醒数量，用于导航栏 Badge 显示
async function loadUnread() {
  try {
    const data = await getBargains(true)
    unreadCount.value = data.length
  } catch {
    // ignore
  }
}

// 组件挂载时：恢复保存的主题偏好，并加载未读数量
onMounted(() => {
  const saved = localStorage.getItem('theme')
  if (saved === 'light') {
    isDark.value = false
    document.body.classList.add('light')
  }
  loadUnread()
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
