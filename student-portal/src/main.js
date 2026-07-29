import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { installAcademicRoutes } from './router/academicRoutes'
import './services/affairsAllowedActions'
import './styles.css'

installAcademicRoutes(router)
createApp(App).use(createPinia()).use(router).mount('#app')
