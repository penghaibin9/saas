import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

export function createApp() {
  // #ifdef H5
  uni.setLocale('zh-Hans')
  // #endif
  const app = createSSRApp(App)
  app.use(createPinia())
  return { app }
}
