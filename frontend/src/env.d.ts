/// <reference types="vite/client" />

// Vue 单文件组件（.vue）类型声明， IDE 智能提示需要
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}