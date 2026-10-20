/**
 * session helper — 会话超时策略工具（总册 §4）。
 * PC 30 分钟无操作超时；移动端预留 7 天；并发 3 会话仅前端预留（真实控制在后端会话服务）。
 */
import { SESSION_POLICY } from '../constants/security.constants'
import { getAuthContext, isSessionExpired as authSessionExpired } from './auth.context'

/** 按设备类型取超时时长（ms） */
export function getSessionTimeoutMs(device = 'pc-web') {
  return device === 'pc-web' ? SESSION_POLICY.PC_TIMEOUT_MS : SESSION_POLICY.MOBILE_TIMEOUT_MS
}

/** 会话是否过期（委托 authContext 的统一口径） */
export function isSessionExpired() {
  return authSessionExpired()
}

/** 剩余时间格式化：xx 分 xx 秒 / 已过期 */
export function formatSessionRemainTime() {
  const auth = getAuthContext()
  const remain = new Date(auth.sessionExpireAt).getTime() - Date.now()
  if (remain <= 0) return '已过期'
  const totalSec = Math.floor(remain / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  if (min >= 60) return `${Math.floor(min / 60)} 小时 ${min % 60} 分`
  return `${min} 分 ${sec} 秒`
}

/**
 * 会话临近超时提醒文案（剩余 < WARNING_BEFORE_MS 时返回提示，否则返回空串）。
 * 页面可轮询本函数决定是否弹出续期提醒。
 */
export function createSessionWarningMessage() {
  const auth = getAuthContext()
  const remain = new Date(auth.sessionExpireAt).getTime() - Date.now()
  if (remain <= 0) return '会话已超时，请重新登录。'
  if (remain <= SESSION_POLICY.WARNING_BEFORE_MS) {
    return `会话将在 ${formatSessionRemainTime()} 后超时，如需继续操作请保持活动或重新登录。`
  }
  return ''
}
