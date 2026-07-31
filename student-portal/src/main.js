import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { installAcademicRoutes } from './router/academicRoutes'
import { installStudentPortalPerformanceGuards } from './services/installPerformanceGuards'
import { installVisibleEnumLocalization } from './services/visibleEnumLocalization'
import './services/affairsAllowedActions'
import './styles.css'

installAcademicRoutes(router)
installStudentPortalPerformanceGuards()
const app = createApp(App).use(createPinia()).use(router)
app.mount('#app')
// 只转换已经渲染到页面的文本节点，不改变接口值、表单值和状态判断。
installVisibleEnumLocalization(document.getElementById('app'))
