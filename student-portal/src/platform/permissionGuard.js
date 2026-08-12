/**
 * 路由守卫：
 * 1) 未登录 → /login
 * 2) mustChangePassword → 只能进入 /force-password-change
 * 3) 已登录再加载 portal-config（一次）
 * 4) 门户总开关关闭 → 未开通页 not-enabled
 * 5) 访问某模块但模块未开通 → module-disabled
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

  const forceRoute = to.name === 'force-password-change'
  // 登录响应中的强制改密状态会单独持久化，因此刷新浏览器后即使 user 内存快照尚未恢复，
  // 也不能先进入 portal-config 或任何业务页面。真正不可绕过的授权仍由后端统一门禁负责。
  if (session.mustChangePassword || session.user?.mustChangePassword) {
    return forceRoute ? next() : next({ name: 'force-password-change' })
  }
  // 已完成强制改密后禁止继续停留在恢复页。
  if (forceRoute) return next({ name: 'home' })

  const cfg = usePortalConfigStore()
  if (!cfg.loaded) {
    await cfg.load()
  }

  // 总开关关闭 → 未开通页（未开通页本身允许访问）
  if (!cfg.enabled && to.name !== 'not-enabled') {
    return next({ name: 'not-enabled' })
  }

  // 模块门禁：专用工作台路由在自己的 meta.modulePath 上声明所属模块，通用模块页取 :module 参数；
  // 新增专用页面时只需在路由上写 meta，无须再改本守卫。
  const modulePath = to.meta?.modulePath || (to.name === 'module' ? to.params.module : '')
  if (modulePath) {
    const m = moduleByPath(modulePath)
    if (!m || !cfg.isModuleEnabled(m.key)) {
      return next({ name: 'module-disabled', params: { module: modulePath } })
    }
  }
  return next()
}