// #ifdef H5
import './services/h5BrowserAuthInstaller'
// #endif
import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { academicSessionPlugin } from '@/stores/sessionAcademicPlugin'
// #ifdef H5
import { installH5InAppDialogs } from '@/services/h5InAppDialogInstaller'
// #endif
// V3 S1.5 Bootstrap De-hoist：学生/教师高频接口适配不再全局静态安装，
// 改由对应分包页面首次进入时调用 ensureStudentPerformanceApi/ensureTeacherPerformanceApi。

// uni-app + Vue3 标准入口。仅本小程序工程使用。
export function createApp() {
  // #ifdef H5
  installH5InAppDialogs()
  // #endif
  const app = createSSRApp(App)
  const pinia = createPinia()
  pinia.use(academicSessionPlugin)
  app.use(pinia)
  return { app }
}
