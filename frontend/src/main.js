// 设计令牌必须最先引入，所有组件样式依赖其中的 CSS 变量
import './styles/tokens.css'
// Element Plus 主题变量对齐（仅日期选择器使用 el 组件）
import './styles/element-theme.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
