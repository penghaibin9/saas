import { createRouter, createWebHistory } from 'vue-router'
import internshipRoutes from '@/modules/internship/routes'
import { request } from '@/services/http/client'
import { checkRouteAccess } from '@/security/guards/route.guard'
import { ensurePermissionPatterns, getRbacLoadFailed } from '@/security/permissionGate'

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
    {
      path: '/security/:status(401|403|419|500)',
      name: 'standalone-security-error',
      component: () => import('@/views/auth/StandaloneSecurityErrorView.vue'),
      meta: { public: true, title: '访问受限' }
    },
    { path: '/:pathMatch(.*)*', redirect: '/admin/internship' }
  ]
})

router.beforeEach(async (to) => {
  if (to.meta?.public === true) return true

  // Permission bootstrap also exercises browser-refresh. A page refresh therefore restores
  // the HttpOnly staff session before evaluating route permissions; an expired/missing cookie
  // falls through to UNAUTHENTICATED instead of briefly mounting the admin workspace.
  await ensurePermissionPatterns(request)

  const result = checkRouteAccess(to)
  if (result.allowed) return true

  const redirect = String(to.fullPath || '/admin/internship')
  if (result.failure === 'UNAUTHENTICATED' || result.failure === 'SESSION_EXPIRED') {
    return {
      path: '/login',
      query: {
        redirect,
        reason: result.failure === 'SESSION_EXPIRED' ? 'session-expired' : 'login-required'
      }
    }
  }

  if (getRbacLoadFailed()) {
    return {
      path: '/security/500',
      query: { from: redirect, reason: 'permission-service' }
    }
  }

  return {
    path: '/security/403',
    query: { from: redirect, reason: result.reason || 'forbidden' }
  }
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · 跃科岗位实习管理平台` : '跃科岗位实习管理平台'
})

export default router
