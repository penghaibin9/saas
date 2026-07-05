/**
 * 路由守卫：
 * 1) 未登录 → /login
 * 2) 已登录先加载 portal-config（一次）
 * 3) 门户总开关关闭 → 未开通页 not-enabled
 * 4) 访问某模块但模块未开通 → module-disabled
 * 非 STUDENT 无法登录（session.login 已拦截），此处只做业务门禁。
 */
import { usePortalConfigStore } from '../stores/portalConfig'
import { useSessionStore } from '../stores/session'
import { moduleByPath } from './moduleRegistry'

export async function guard(to, from, next) {
  if (to.meta?.public) return next()

  const session = useSessionStore()
  if (!session.isLoggedIn) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  const cfg = usePortalConfigStore()
  if (!cfg.loaded) {
    await cfg.load()
  }

  // 总开关关闭 → 未开通页（未开通页本身允许访问）
  if (!cfg.enabled && to.name !== 'not-enabled') {
    return next({ name: 'not-enabled' })
  }

  // 模块门禁
  if (to.name === 'module') {
    const m = moduleByPath(to.params.module)
    if (!m || !cfg.isModuleEnabled(m.key)) {
      return next({ name: 'module-disabled', params: { module: to.params.module } })
    }
  }
  return next()
}
