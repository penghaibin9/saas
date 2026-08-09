import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { installAcademicRoutes } from './router/academicRoutes'
import { installStudentPortalPerformanceGuards } from './services/installPerformanceGuards'
import './styles.css'
import './styles/stage-d-v5-fixes.css'

installAcademicRoutes(router)
installStudentPortalPerformanceGuards()
createApp(App).use(createPinia()).use(router).mount('#app')
