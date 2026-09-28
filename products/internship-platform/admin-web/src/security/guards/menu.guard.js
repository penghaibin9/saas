/**
 * menu guard — 菜单级安全过滤。
 * 复用 workflow permissionContext（不复制权限逻辑），叠加安全侧封装：
 * getCurrentPermissionContext / canAccessSecurityPage / canClickSecurityButton / resolveSecurityDataScope。
 */
import {
  getPermissionContext,
  canAccessPage,
  canClickButton,
  canViewMenu,
  getDataScope,
  filterMenusByPermission
} from '@/modules/workflow/context/permission.context'

/** 当前 permissionContext（直通 workflow，安全域统一入口） */
export function getCurrentPermissionContext() {
  return getPermissionContext()
}

/** 安全封装：页面/按钮/数据范围（保持 workflow 单一实现） */
export function canAccessSecurityPage(permissionKey) {
  return canAccessPage(permissionKey)
}

export function canClickSecurityButton(permissionKey) {
  return canClickButton(permissionKey)
}

export function resolveSecurityDataScope() {
  return getDataScope()
}

/** 单菜单可见性：permissionKey 缺省视为公开 */
export function canShowMenu(menuItem = {}) {
  if (!menuItem.permissionKey) return true
  return canViewMenu(menuItem.permissionKey)
}

/**
 * 菜单树过滤（支持 children 递归）；空 children 的分组节点一并剔除。
 */
export function filterMenusBySecurity(menus = []) {
  return filterMenusByPermission(menus)
    .map((m) => {
      if (!Array.isArray(m.children)) return m
      const children = filterMenusBySecurity(m.children)
      return { ...m, children }
    })
    .filter((m) => !Array.isArray(m.children) || m.children.length > 0)
}
