import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { academicSessionPlugin } from '@/stores/sessionAcademicPlugin'

// uni-app + Vue3 标准入口。仅本小程序工程使用。
export function createApp() {
  const app = createSSRApp(App)
  const pinia = createPinia()
  pinia.use(academicSessionPlugin)
  app.use(pinia)
  return { app }
}
