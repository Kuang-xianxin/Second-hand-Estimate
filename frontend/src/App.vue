/**
 * App.vue - 应用根组件
 * 
 * 本组件负责：
 * - 顶部导航栏的渲染
 * - 主题切换（深色/浅色模式）
 * - 未读捡漏数量的显示
 * - 路由视图的渲染（显示当前路径对应的页面）
 * 
 * 使用技术：
 * - Vue 3 Composition API（script setup 语法糖）
 * - Vue Router（路由导航）
 * - CSS 变量（主题样式）
 */

<template>
  <!-- 应用外壳容器 - flex 纵向布局 -->
  <div class="app-shell">
    
    <!-- 顶部导航栏 - 固定在顶部 -->
    <nav class="navbar">
      <!-- 左侧：品牌标识 -->
      <div class="nav-brand">
        <span class="brand-icon">估</span>
        <span class="brand-name">估二手</span>
      </div>
      
      <!-- 右侧：导航链接和主题切换 -->
      <div class="nav-actions">
        <!-- 导航链接组 -->
        <div class="nav-links">
          <!-- router-link: Vue Router 提供的链接组件，会自动处理路由跳转 -->
          <!-- active-class: 当路径匹配时添加的 CSS 类名 -->
          <router-link to="/" class="nav-link" active-class="active">估价</router-link>
          
          <!-- 捡漏页面链接 - 带有未读数量徽章 -->
          <router-link to="/bargains" class="nav-link" active-class="active">
            捡漏
            <!-- v-if: 条件渲染，未读数大于0时才显示徽章 -->
            <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
          </router-link>
          
          <!-- 历史记录链接 -->
          <router-link to="/history" class="nav-link" active-class="active">记录</router-link>
        </div>
        
        <!-- 主题切换按钮 - 点击切换深色/浅色模式 -->
        <!-- @click: Vue 的事件绑定语法，相当于 onclick -->
        <!-- :title: 绑定属性，鼠标悬停时显示提示文字 -->
        <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换日间模式' : '切换夜间模式'">
          <!-- 根据 isDark 状态显示不同图标 -->
          <span class="theme-icon">{{ isDark ? '🌙' : '☀️' }}</span>
        </button>
      </div>
    </nav>
    
    <!-- 主内容区域 - 显示当前路由对应的页面 -->
    <main class="main-content">
      <!-- router-view: Vue Router 提供的占位组件，用于渲染匹配的路由组件 -->
      <!-- v-slot: 获取渲染的组件实例 -->
      <!-- keep-alive: 缓存组件状态，避免重复创建销毁 -->
      <router-view v-slot="{ Component }">
        <keep-alive include="HomeView">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup>
/**
 * <script setup> 是 Vue 3 的语法糖
 * - 所有变量和函数直接在模板中使用，无需返回
 * - 导入的组件自动注册
 */

// 从 vue 中导入响应式 API
import { ref, onMounted, computed } from 'vue'

// 导入 API 函数 - 用于与后端通信
import { getBargains } from '@/api/index.js'

// ref(): 创建响应式变量（基本类型）
// unreadCount: 未读捡漏数量
const unreadCount = ref(0)

// isDark: 是否为深色模式（true=深色，false=浅色）
const isDark = ref(true)

/**
 * toggleTheme - 切换主题
 * 
 * 工作原理：
 * 1. 取反 isDark 状态
 * 2. 在 body 元素上切换 'light' 类名
 * 3. 将主题偏好保存到 localStorage（下次访问时恢复）
 */
function toggleTheme() {
  // .value 是访问 ref 创建的响应式变量的方式
  isDark.value = !isDark.value
  // classList.toggle: 切换 CSS 类，第二个参数为 true 时添加，为 false 时移除
  document.body.classList.toggle('light', !isDark.value)
  // localStorage: 浏览器的本地存储，可持久化保存数据
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

/**
 * loadUnread - 加载未读捡漏数量
 * 
 * 从后端 API 获取未读的捡漏提醒数量
 * 用于在导航栏显示红色徽章
 */
async function loadUnread() {
  try {
    // 调用 API 获取捡漏数据（unreadOnly=true 表示只看未读）
    const data = await getBargains(true)
    // 更新未读数量
    unreadCount.value = data.length
  } catch {
    // 静默处理错误，不影响用户体验
  }
}

/**
 * onMounted - 生命周期钩子
 * 
 * 相当于 Vue 2 的 mounted 钩子
 * 在组件首次挂载到 DOM 后执行
 * 
 * 这里用于：
 * 1. 恢复用户的主题偏好
 * 2. 加载未读数量
 */
onMounted(() => {
  // 从 localStorage 读取保存的主题设置
  const saved = localStorage.getItem('theme')
  if (saved === 'light') {
    // 如果之前是浅色模式，恢复设置
    isDark.value = false
    document.body.classList.add('light')
  }
  // 加载未读捡漏数量
  loadUnread()
})
</script>

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
