import { createRouter, createWebHistory } from 'vue-router'
import { pinia } from '../stores'
import { useSessionStore } from '../stores/session'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', meta: { public: true }, component: () => import('../views/LoginView.vue') },
    { path: '/', redirect: '/internship' },
    { path: '/internship', name: 'internship', component: () => import('../views/internship/InternshipView.vue') },
    // 选岗独立页尚未把所有旧门户展示组件抽齐前，先回到同一权威申请工作区，避免死路。
    { path: '/internship/selection', redirect: { path: '/internship', query: { view: 'application' } } },
    { path: '/:pathMatch(.*)*', redirect: '/internship' }
  ]
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const session = useSessionStore(pinia)
  await session.restore()
  if (!session.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
