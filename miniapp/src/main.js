import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './services/affairsAllowedActions'

// uni-app + Vue3 标准入口。仅本小程序工程使用。
export function createApp() {
  const app = createSSRApp(App)
  app.use(createPinia())
  return { app }
}
