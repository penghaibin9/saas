/**
 * security error helper — 安全错误的统一语义与文案（不暴露堆栈/内部信息）。
 */
import { SECURITY_HTTP_STATUS, SECURITY_ERROR_ROUTES } from '../constants/security.constants'

const SAFE_MESSAGES = Object.freeze({
  401: '登录状态已失效，请重新登录',
  403: '当前账号无权访问该资源',
  419: '会话已超时或请求校验失败，请重新登录后重试',
  500: '服务暂时不可用，请稍后重试'
})

/** 状态码 → 用户可见安全文案（未知码归入 500 文案） */
export function getSafeMessage(status) {
  return SAFE_MESSAGES[status] || SAFE_MESSAGES[500]
}

/** 状态码 → 错误页路由 */
export function getSecurityErrorRoute(status) {
  return SECURITY_ERROR_ROUTES[status] || SECURITY_ERROR_ROUTES[500]
}

/** 是否安全相关状态码 */
export function isSecurityStatus(status) {
  return Object.values(SECURITY_HTTP_STATUS).includes(Number(status))
}

/**
 * 清理错误信息：剥掉堆栈、内部路径、SQL/异常类名等痕迹，仅保留安全文案。
 * 原始信息不回显给用户（真实阶段应连同 requestId 上报审计）。
 */
export function sanitizeErrorMessage(error, fallbackStatus = 500) {
  const status = Number(error?.status || error?.code) || fallbackStatus
  return { status, message: getSafeMessage(status) }
}
