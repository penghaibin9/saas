/**
 * 路由守卫：
 * 1) 私有页先用 HttpOnly refresh cookie 恢复内存 accessToken
 * 2) 未登录 → /login
 * 3) mustChangePassword → 只能进入 /force-password-change
 * 4) 已登录再加载 portal-config（一次）
 * 5) 门户总开关关闭 → 未开通页 not-enabled
 * 6) 访问某模块但模块未开通 → module-disabled
 * 非 STUDENT 无法登录（session.login 已拦截），此处只做业务门禁。
 */
import { usePortalConfigStore } from '../stores/portalConfig'
import { useSessionStore } from '../stores/session'
import { getToken, request } from '../services/request'
import { moduleByPath } from './moduleRegistry'

export async function guard(to, from, next) {
  if (to.meta?.public) return next()

  const session = useSessionStore()
  // accessToken 只驻留内存，F5/新标签页不会有 token；先让统一请求层使用 HttpOnly refresh
  // cookie 静默恢复，再做“未登录”判断。恢复失败才真正回登录页。
  if (!session.isLoggedIn && !session.ready) {
    try {
      const me = await request('/auth/me')
      session.token = getToken()
      session.user = me?.user || me || null
      session.mustChangePassword = !!(session.mustChangePassword || session.user?.mustChangePassword)
    } catch {
      session.token = ''
      session.user = null
    } finally {
      session.ready = true
    }
  }
  if (!session.isLoggedIn) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  const forceRoute = to.name === 'force-password-change'
  // 强制改密状态会单独持久化；真正不可绕过的授权仍由后端统一门禁负责。
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