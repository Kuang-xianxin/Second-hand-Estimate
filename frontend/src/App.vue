<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getBargains } from './api'

const unreadCount = ref(0)
const isDark = ref(true)

function toggleTheme() {
  isDark.value = !isDark.value
  document.body.classList.toggle('light', !isDark.value)
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

.nav-link:hover { color: var(--text); background: var(--bg3); }
.nav-link.active { color: var(--accent); background: rgba(232,197,71,0.1); }

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

.main-content {
  flex: 1;
  padding: 40px 32px;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
}
</style>