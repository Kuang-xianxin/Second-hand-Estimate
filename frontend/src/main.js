/**
 * 主入口文件
 * - 创建 Vue 应用实例
 * - 配置 Vue Router 路由（支持 history 模式的 URL）
 * - 注册路由组件并挂载到 #app 元素上
 */

// 从 vue 包中导入 createApp 函数，用于创建应用实例
import { createApp } from 'vue'

// 从 vue-router 包中导入路由相关函数
// createRouter: 创建路由实例
// createWebHistory: 使用 HTML5 History API（不带 # 的 URL）
import { createRouter, createWebHistory } from 'vue-router'

// 导入根组件 App.vue
import App from './App.vue'

// 导入页面组件（路由对应的视图）
import HomeView from './views/HomeView.vue'     // 估价主页
import HistoryView from './views/HistoryView.vue' // 历史记录页
import BargainView from './views/BargainView.vue' // 捡漏提醒页

// 导入全局样式
import './style.css'

/**
 * 配置 Vue Router 路由表
 * - 路径 '/' -> 估价主页
 * - 路径 '/history' -> 历史记录页
 * - 路径 '/bargains' -> 捡漏提醒页
 */
const router = createRouter({
  // 使用 HTML5 History 模式，URL 看起来像普通路径而不是 hash
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/history', component: HistoryView },
    { path: '/bargains', component: BargainView },
  ]
})

// 创建 Vue 应用实例
const app = createApp(App)

// 将路由实例注册到应用中，使所有组件都能访问 $router
app.use(router)

// 将应用挂载到 HTML 中的 #app 元素上
app.mount('#app')
