/**
 * permissionContext —— 全系统统一权限上下文（当前纯前端 mock）。
 * P8 / 真实权限阶段：仅替换 loadPermissionContext 的数据来源，判断函数签名不变。
 * 与 licenseContext 为预留关系（本次不接真实授权中心）：licenseContext 负责"模块买没买/到没到期"，
 * permissionContext 负责"角色能不能做"；生效优先级见 03 开关模型（license 在前，permission 在后）。
 * 页面禁止散写权限判断，必须使用本文件导出的函数。
 */
import { reactive, readonly } from 'vue'
import { getPermissionContext as fetchContext } from '../provider/workflow.provider'
import {
  matchPermission,
  canAccessPage as _canAccessPage,
  canClickButton as _canClickButton,
  canViewMenu as _canViewMenu,
  resolveDataScope
} from '../helpers/permission.helpers'

const state = reactive({
  loaded: false,
  loading: false,
  context: null
})

/** 加载（幂等）。页面/路由守卫入口统一调用。 */
export async function loadPermissionContext(force = false) {
  if (state.loaded && !force) return state.context
  if (state.loading) return state.context
  state.loading = true
  try {
    const res = await fetchContext()
    if (res.code === 0) {
      state.context = res.data
      state.loaded = true
    }
  } finally {
    state.loading = false
  }
  return state.context
}

/** 同步获取当前上下文（未加载返回 null；只读引用） */
export function getPermissionContext() {
  return state.context ? readonly(state.context) : null
}

export function canAccessPage(permissionKey) {
  return _canAccessPage(permissionKey, state.context)
}

export function canClickButton(permissionKey) {
  return _canClickButton(permissionKey, state.context)
}

export function canViewMenu(permissionKey) {
  return _canViewMenu(permissionKey, state.context)
}

export function getDataScope() {
  return resolveDataScope(state.context)
}

export function hasRole(roleCode) {
  return (state.context?.roleCodes || []).includes(roleCode)
}

export function hasAnyPermission(permissionKeys = []) {
  return permissionKeys.some((k) => matchPermission(k, state.context?.permissions || []))
}

/** 菜单过滤：menu.permissionKey 缺省视为公开 */
export function filterMenusByPermission(menus = []) {
  return menus.filter((m) => !m.permissionKey || canViewMenu(m.permissionKey))
}

/** 操作按钮过滤：action.permissionKey 缺省视为公开 */
export function filterActionsByPermission(actions = []) {
  return actions.filter((a) => !a.permissionKey || canClickButton(a.permissionKey))
}
