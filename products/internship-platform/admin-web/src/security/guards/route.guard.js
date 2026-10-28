import { isAuthenticated, isSessionExpired } from '../auth/auth.context'
import { canEnterRoute } from '../permissionGate'
import { getSecurityErrorRoute } from '../helpers/security-error.helper'

export function getRouteRequiredPermission(route) {
  return route?.meta?.permissionKey || ''
}

export function getRouteSecurityMeta(route) {
  const meta = route?.meta || {}
  return {
    isPublic: meta.public === true,
    requiresAuth: meta.requiresAuth !== false && meta.public !== true,
    permissionKey: meta.permissionKey || '',
    permissionAny: Array.isArray(meta.permissionAny) ? meta.permissionAny.filter(Boolean) : [],
    allowedRoles: Array.isArray(meta.allowedRoles) ? meta.allowedRoles : [],
    moduleCode: meta.moduleCode || ''
  }
}

export function checkRouteAccess(route) {
  const meta = getRouteSecurityMeta(route)
  if (meta.isPublic) return { allowed: true, failure: '', reason: '' }
  if (meta.requiresAuth) {
    if (isSessionExpired()) return { allowed: false, failure: 'SESSION_EXPIRED', reason: '会话已超时' }
    if (!isAuthenticated()) return { allowed: false, failure: 'UNAUTHENTICATED', reason: '未登录' }
  }
  const allowed = canEnterRoute(meta)
  return allowed
    ? { allowed: true, failure: '', reason: '' }
    : { allowed: false, failure: 'FORBIDDEN', reason: '当前身份缺少页面所需权限' }
}

export function resolveRouteFailure(checkResult) {
  const map = {
    UNAUTHENTICATED: getSecurityErrorRoute(401),
    SESSION_EXPIRED: getSecurityErrorRoute(419),
    FORBIDDEN: getSecurityErrorRoute(403)
  }
  return { redirect: map[checkResult?.failure] || getSecurityErrorRoute(500), reason: checkResult?.reason || '' }
}
