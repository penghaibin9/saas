import { findActiveInPlan } from '../../config/navPlan.js'

// 学工导航跨越多个历史路由目录；详情/编辑页也继承所属业务的新壳。
export function usesStudentAffairsWorkspace(path, fullPath = path) {
  const pathname = String(path || '').split(/[?#]/)[0]
  return /^\/admin\/(student-affairs|student|orientation|campus-service)(?:\/|$)/.test(pathname)
    || findActiveInPlan(pathname, fullPath).groupKey === 'student-affairs'
}

// 只用真实登录身份维度保存外观。模块自己的 ctxKey 用于各自权限缓存，不适合作为共享外壳的偏好键。
export function workspaceIdentity(claims, context) {
  if (claims?.tenantId != null && claims?.userId != null && claims?.currentRoleCode) {
    return 'identity-v2:' + JSON.stringify([String(claims.tenantId), String(claims.userId), String(claims.currentRoleCode), String(claims.activeContextId || '')])
  }
  return context?.ctxKey || ''
}

export function workspaceRouteOwner(path, fullPath = path) {
  const owner = findActiveInPlan(path, fullPath)
  if (owner.modKey) return owner
  const fallback = [
    [/^\/admin\/student(?:\/|$)/, 'sa-profile', '学生列表'],
    [/^\/admin\/student-affairs\/dorm(?:\/|$)/, 'sa-dorm', '宿舍驾驶舱']
  ].find(([pattern]) => pattern.test(path))
  return fallback ? { groupKey: 'student-affairs', modKey: fallback[1], leafKey: fallback[2] } : owner
}
