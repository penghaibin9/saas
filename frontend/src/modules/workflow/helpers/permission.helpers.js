/**
 * 统一权限 helper —— 权限点匹配/页面·按钮·菜单判断/数据范围解析。
 * 权限点格式：module.resource.action，支持通配 module.*、module.resource.*。
 */
import { DATA_SCOPE, DATA_SCOPE_LABELS } from '../constants/workflow.constants'

/** 规范化权限点：小写、去空格 */
export function normalizePermissionKey(key) {
  return String(key || '').trim().toLowerCase()
}

/**
 * 权限匹配（支持通配符持有项）。
 * matchPermission('internship.report.review', ['internship.*']) === true
 */
export function matchPermission(permissionKey, permissions = []) {
  const target = normalizePermissionKey(permissionKey)
  if (!target) return false
  return permissions.some((held) => {
    const h = normalizePermissionKey(held)
    if (h === target) return true
    if (h.endsWith('.*')) return target.startsWith(h.slice(0, -1))
    return false
  })
}

export function canAccessPage(permissionKey, context) {
  return matchPermission(permissionKey, context?.permissions || [])
}

export function canClickButton(permissionKey, context) {
  const pool = [...(context?.buttonPermissions || []), ...(context?.permissions || [])]
  return matchPermission(permissionKey, pool)
}

export function canViewMenu(permissionKey, context) {
  const pool = [...(context?.menuPermissions || []), ...(context?.permissions || [])]
  return matchPermission(permissionKey, pool)
}

/** 解析当前数据范围 → { scope, label } */
export function resolveDataScope(context) {
  const scope = context?.dataScope || DATA_SCOPE.SELF
  return { scope, label: DATA_SCOPE_LABELS[scope] || scope }
}
