/**
 * route guard — 路由级安全校验（本阶段不注册全局 beforeEach，仅提供统一入口；P8 实装）。
 * 支持 route.meta：{ public, requiresAuth, permissionKey, allowedRoles, moduleCode }
 * 失败分流：未登录/会话超时 → 401/419；无权限 → 403；readonly/noLicense 由页面 StateBlock 承担展示。
 * 复用 workflow permissionContext 与 workflow.guards.checkRoutePermission，不重写权限系统。
 */
import { isAuthenticated, isSessionExpired } from '../auth/auth.context'
import { getCurrentPermissionContext } from './menu.guard'
import { checkRoutePermission } from '@/modules/workflow/guards/workflow.guards'
import { hasRole } from '@/modules/workflow/context/permission.context'
import { getSecurityErrorRoute } from '../helpers/security-error.helper'

/** 提取路由所需权限点 */
export function getRouteRequiredPermission(route) {
  return route?.meta?.permissionKey || ''
}

/** 提取路由安全元数据（缺省值收敛于此，页面/守卫不再各自解释） */
export function getRouteSecurityMeta(route) {
  const meta = route?.meta || {}
  return {
    isPublic: meta.public === true,
    requiresAuth: meta.requiresAuth !== false && meta.public !== true, // 默认需要登录
    permissionKey: meta.permissionKey || '',
    allowedRoles: Array.isArray(meta.allowedRoles) ? meta.allowedRoles : [],
    moduleCode: meta.moduleCode || ''
  }
}

/**
 * 路由访问综合判定。
 * @returns {{ allowed:boolean, failure:''|'UNAUTHENTICATED'|'SESSION_EXPIRED'|'FORBIDDEN', reason:string }}
 */
export function checkRouteAccess(route) {
  const meta = getRouteSecurityMeta(route)
  if (meta.isPublic) return { allowed: true, failure: '', reason: '' }

  if (meta.requiresAuth) {
    if (isSessionExpired()) return { allowed: false, failure: 'SESSION_EXPIRED', reason: '会话已超时' }
    if (!isAuthenticated()) return { allowed: false, failure: 'UNAUTHENTICATED', reason: '未登录' }
  }

  if (meta.allowedRoles.length && !meta.allowedRoles.some((r) => hasRole(r))) {
    return { allowed: false, failure: 'FORBIDDEN', reason: '角色不允许访问该路由' }
  }

  if (meta.permissionKey) {
    const ctx = getCurrentPermissionContext()
    const res = checkRoutePermission({ permissionKey: meta.permissionKey }, ctx)
    if (!res.allowed) return { allowed: false, failure: 'FORBIDDEN', reason: res.reason }
  }

  return { allowed: true, failure: '', reason: '' }
}

/** 失败 → 跳转目标（供未来 beforeEach：return resolveRouteFailure(check).redirect） */
export function resolveRouteFailure(checkResult) {
  const map = {
    UNAUTHENTICATED: getSecurityErrorRoute(401),
    SESSION_EXPIRED: getSecurityErrorRoute(419),
    FORBIDDEN: getSecurityErrorRoute(403)
  }
  return {
    redirect: map[checkResult?.failure] || getSecurityErrorRoute(500),
    reason: checkResult?.reason || ''
  }
}
