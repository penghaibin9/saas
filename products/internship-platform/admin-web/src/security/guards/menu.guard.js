import { getPermissionPatterns } from '../permissionGate'
import { matchPermission } from '@/config/navPlan'

export function getCurrentPermissionContext() {
  return { permissionPatterns: getPermissionPatterns() || [] }
}

export function canAccessSecurityPage(permissionKey) {
  if (!permissionKey) return true
  const patterns = getPermissionPatterns()
  return Array.isArray(patterns) && matchPermission(patterns, permissionKey)
}

export function canClickSecurityButton(permissionKey) {
  return canAccessSecurityPage(permissionKey)
}

export function resolveSecurityDataScope() {
  return { scope: 'AUTHORIZED', label: '当前授权范围' }
}

export function canShowMenu(menuItem = {}) {
  if (!menuItem.permissionKey) return true
  return canAccessSecurityPage(menuItem.permissionKey)
}

export function filterMenusBySecurity(menus = []) {
  return menus
    .filter(canShowMenu)
    .map((item) => Array.isArray(item.children)
      ? { ...item, children: filterMenusBySecurity(item.children) }
      : item)
    .filter((item) => !Array.isArray(item.children) || item.children.length > 0)
}
