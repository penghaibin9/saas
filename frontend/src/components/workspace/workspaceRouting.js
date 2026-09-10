import { findActiveInPlan, NAV_PLAN, navRefMatches } from '../../config/navPlan.js'
import { resolveWorkspacePageId } from './teacherWorkspace.js'
import { academicObjectParentPath } from '../../modules/academicAffairs/config/academicNavigation.js'

export function usesAcademicWorkspace(path, fullPath = path) {
  return /^\/admin\/academic-affairs(?:\/|$)/.test(path)
    || findActiveInPlan(path, fullPath).groupKey === 'academic-affairs'
}

export function activeWorkspacePage(pages, route, activeModule) {
  const entry = route.query?._workspace
  const explicitId = resolveWorkspacePageId(entry, pages.filter(page => workspacePageMatches(route.fullPath, page.path)))
  const explicit = pages.find(page => page.id === explicitId && workspacePageMatches(route.fullPath, page.path))
  if (explicit) return explicit
  const matches = pages.filter(page => workspacePageMatches(route.fullPath, page.path))
  matches.sort((a, b) => (b.path.includes('?') ? 10000 : 0) + b.path.length - (a.path.includes('?') ? 10000 : 0) - a.path.length)
  return matches.find(page => page.moduleKey === activeModule) || matches[0]
}

export function workspacePageMatches(current, candidate) {
  if (!candidate) return false
  const route = new URL(current, 'http://workspace.local')
  const page = new URL(candidate, 'http://workspace.local')
  const objectParent = academicObjectParentPath(route.pathname, route.searchParams)
  if (objectParent) return page.pathname + page.search === objectParent
  if (page.search) return route.pathname === page.pathname && [...page.searchParams].every(([key, value]) => route.searchParams.get(key) === value)
  return navRefMatches(route.pathname, page.pathname)
}

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
  const entry = new URL(fullPath, 'http://workspace.local').searchParams.get('_workspace')
  if (entry) {
    for (const group of NAV_PLAN) for (const mod of group.children || []) {
      const leaf = mod.children?.find(item => (group.key !== 'academic-affairs' || !item.hidden) && (
        `${mod.key}:${item.label}` === entry || (group.key === 'academic-affairs' &&
          (item.leafId === entry || item.legacyWorkspaceIds?.includes(entry)))
      ) && workspacePageMatches(fullPath, item.path))
      if (leaf) return { groupKey: group.key, modKey: mod.key, leafKey: leaf.label }
    }
  }
  // Academic object/filter parameters extend a menu URL; they do not change its owner.
  // Reuse the same subset matching as activeWorkspacePage without changing other centers.
  if (/^\/admin\/academic-affairs(?:\/|$)/.test(path)) {
    const group = NAV_PLAN.find(item => item.key === 'academic-affairs')
    const matches = (group?.children || []).flatMap(mod => (mod.children || [])
      .filter(leaf => !leaf.hidden && workspacePageMatches(fullPath, leaf.path))
      .map(leaf => ({ mod, leaf })))
    matches.sort((a, b) => (b.leaf.path.includes('?') ? 10000 : 0) + b.leaf.path.length
      - (a.leaf.path.includes('?') ? 10000 : 0) - a.leaf.path.length)
    if (matches.length) return { groupKey: group.key, modKey: matches[0].mod.key, leafKey: matches[0].leaf.label }
  }
  const owner = findActiveInPlan(path, fullPath)
  if (owner.modKey) return owner
  const fallback = [
    [/^\/admin\/student(?:\/|$)/, 'sa-profile', '学生列表'],
    [/^\/admin\/student-affairs\/dorm(?:\/|$)/, 'sa-dorm', '宿舍驾驶舱']
  ].find(([pattern]) => pattern.test(path))
  return fallback ? { groupKey: 'student-affairs', modKey: fallback[1], leafKey: fallback[2] } : owner
}
