import { createRouter, createWebHistory } from 'vue-router'
import { guard } from '../platform/permissionGuard'

const routes = [
  { path: '/login', name: 'login', meta: { public: true }, component: () => import('../views/login/LoginView.vue') },
  {
    path: '/portal',
    component: () => import('../layouts/PortalLayout.vue'),
    children: [
      { path: '', redirect: '/portal/home' },
      { path: 'home', name: 'home', component: () => import('../views/home/HomeView.vue') },
      { path: 'not-enabled', name: 'not-enabled', component: () => import('../components/NotEnabledView.vue') },
      { path: 'module-disabled/:module', name: 'module-disabled', component: () => import('../components/ModuleDisabledView.vue') },
      { path: ':module', name: 'module', component: () => import('../views/template/ModuleTemplateView.vue') }
    ]
  },
  { path: '/', redirect: '/portal/home' },
  { path: '/:pathMatch(.*)*', redirect: '/portal/home' }
]

// history base 取自 Vite base（默认 /portal/，可 VITE_BASE 覆盖），刷新子路由不 404（配合 nginx try_files）
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(guard)

export default router
