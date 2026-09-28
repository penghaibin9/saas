import { createRouter, createWebHistory } from 'vue-router'
import internshipRoutes from '@/modules/internship/routes'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/admin/internship' },
    {
      path: '/login',
      name: 'standalone-login',
      component: () => import('@/views/auth/StandaloneLoginView.vue'),
      meta: { public: true, title: '登录' }
    },
    internshipRoutes,
    { path: '/:pathMatch(.*)*', redirect: '/admin/internship' }
  ]
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · 跃科岗位实习管理平台` : '跃科岗位实习管理平台'
})

export default router
