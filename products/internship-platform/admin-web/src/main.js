import './styles/tokens.css'
import './styles/element-theme.css'
import './styles/standalone.css'
import './styles/module-page.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { toast } from './utils/toast'

const app = createApp(App)
app.config.globalProperties.$message = toast
app.use(createPinia())
app.use(router)
app.mount('#app')
