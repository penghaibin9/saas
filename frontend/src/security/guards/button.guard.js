/**
 * button guard — 按钮级安全控制（可见 / 可用 / 禁用原因三分离）。
 * 可见性由权限决定；可用性叠加 readonly（模块到期）与会话状态。
 */
import { canClickSecurityButton } from './menu.guard'
import { isAuthenticated } from '../auth/auth.context'

/** 是否渲染按钮（无权限 → 不渲染，遵循"未授权隐藏"拍板） */
export function canShowButton(permissionKey) {
  if (!permissionKey) return true
  return canClickSecurityButton(permissionKey)
}

/**
 * 是否可点击。
 * @param {object} opt { permissionKey, readonly, requireAuth }
 */
export function canEnableButton(opt = {}) {
  if (opt.readonly) return false
  if (opt.requireAuth !== false && !isAuthenticated()) return false
  if (opt.permissionKey && !canClickSecurityButton(opt.permissionKey)) return false
  return true
}

/** 禁用原因（悬浮提示用；可点击时返回空串） */
export function getDisabledReason(opt = {}) {
  if (opt.readonly) return '模块已到期只读，写操作被禁用'
  if (opt.requireAuth !== false && !isAuthenticated()) return '登录状态已失效，请重新登录'
  if (opt.permissionKey && !canClickSecurityButton(opt.permissionKey)) {
    return '当前账号无此操作权限'
  }
  return ''
}
