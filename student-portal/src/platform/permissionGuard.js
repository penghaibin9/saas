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

  // 模块门禁：毕业设计有专用工作台路由，也必须与通用模块页一样受配置开关控制。
  const modulePath = to.name === 'graduation-workbench' ? 'graduation' : (to.name === 'module' ? to.params.module : '')
  if (modulePath) {
    const m = moduleByPath(modulePath)
    if (!m || !cfg.isModuleEnabled(m.key)) {
      return next({ name: 'module-disabled', params: { module: modulePath } })
    }
  }
  return next()
}
