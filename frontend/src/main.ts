// 引入 Vue 应用创建函数和路由相关函数
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
// 引入根组件 App.vue
import App from './App.vue'
// 引入三个页面视图组件
import HomeView from '@/views/HomeView.vue'
import HistoryView from '@/views/HistoryView.vue'
import BargainView from '@/views/BargainView.vue'
// 引入全局样式文件
import './style.css'

// 创建 Vue Router 实例，配置路由规则
// 使用 HTML5 History 模式（URL 中不带 #）
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },           // 估价首页
    { path: '/history', component: HistoryView }, // 估价历史记录页
    { path: '/bargains', component: BargainView }, // 捡漏提醒页
  ],
})

// 创建 Vue 应用实例，注册路由并挂载到 #app 节点
const app = createApp(App)
app.use(router)
app.mount('#app')