// 设计令牌必须最先引入，所有组件样式依赖其中的 CSS 变量
import './styles/tokens.css'
// Element Plus 主题变量对齐（仅日期选择器使用 el 组件）
import './styles/element-theme.css'
// PC 管理端高对比视觉皮肤：只覆盖外观，不改变菜单、路由与业务结构。
import './styles/high-contrast-skin.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { toast } from './utils/toast'

// 任何失效书签、旧链接或未知 URL 都回到工作台，避免生产环境出现空白路由页。
if (!router.hasRoute('unknown-route-fallback')) {
  router.addRoute({
    path: '/:pathMatch(.*)*',
    name: 'unknown-route-fallback',
    redirect: '/workbench'
  })
}

const app = createApp(App)
// 统一轻提示兼容门面：业务页可使用 this.$message.success/error/warning/info，
// 实际仍由全局 AppToast 渲染，不引入第二套通知组件。
app.config.globalProperties.$message = toast
app.use(createPinia())
app.use(router)
app.mount('#app')
