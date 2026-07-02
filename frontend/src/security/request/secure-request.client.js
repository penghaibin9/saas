/**
 * secure request client — 统一安全请求封装。
 * 侦察结论：工程无现有 http client（仅 services/mock 的 Promise mock），故按规则新增本文件；
 * 不替换现有 provider，不重构 Dashboard——业务 provider 接真实后端时按需接入本 client。
 * 能力：requestId 自动附加、Authorization 预留、CSRF 预留、401/403/419/500 统一处理、敏感错误清理。
 * 当前不接真实 API：默认 baseFetch 仍是 window.fetch，但本阶段无任何调用方发起真实请求。
 */
import { REQUEST_ID_HEADER } from '../constants/security.constants'
import { attachCsrfHeader } from '../helpers/csrf.helper'
import { sanitizeErrorMessage, getSecurityErrorRoute, isSecurityStatus } from '../helpers/security-error.helper'
import { getAuthContext, refreshLastActive, clearAuthContext } from '../auth/auth.context'

let seq = 0

/** 生成链路追踪 requestId */
export function createRequestId() {
  seq = (seq + 1) % 10000
  return `fe-${Date.now().toString(36)}-${seq.toString(36)}-${Math.random().toString(36).slice(2, 6)}`
}

/**
 * 统一安全错误处理：
 * 401 → 清空 authContext，跳 /security/401
 * 403 → 跳 /security/403；419 → /security/419；500 及未知 → /security/500
 * router 由调用方注入（避免本模块反向依赖 router 实例）。
 */
export function handleSecurityError(status, { router = null, requestId = '' } = {}) {
  const { message } = sanitizeErrorMessage({ status })
  if (Number(status) === 401) clearAuthContext()
  const route = getSecurityErrorRoute(status)
  if (router && isSecurityStatus(status)) {
    router.push({ path: route, query: requestId ? { rid: requestId } : {} })
  }
  return { status: Number(status), message, route, requestId }
}

/** 清理错误信息（re-export，方便统一从 client 引） */
export { sanitizeErrorMessage }

/**
 * secureRequest —— 统一请求入口。
 * @param {string} url
 * @param {object} options { method, params, body, headers, router }
 * @returns {Promise<{code,message,data,timestamp,requestId}>} 兼容全站统一响应结构
 */
export async function secureRequest(url, options = {}) {
  const method = String(options.method || 'GET').toUpperCase()
  const requestId = createRequestId()

  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  headers[REQUEST_ID_HEADER] = requestId
  // Authorization 预留：真实认证后端接入后由会话服务提供 token
  const auth = getAuthContext()
  if (auth.userId) headers.Authorization = `Bearer mock-${auth.userId}`
  attachCsrfHeader(headers, method)

  const qs = options.params
    ? '?' +
      Object.entries(options.params)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&')
    : ''

  try {
    const res = await fetch(`${url}${qs}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: options.body ? JSON.stringify(options.body) : undefined
    })
    if (!res.ok) {
      const handled = handleSecurityError(res.status, { router: options.router, requestId })
      return { code: handled.status, message: handled.message, data: null, timestamp: Date.now(), requestId }
    }
    refreshLastActive()
    const payload = await res.json().catch(() => null)
    // 兼容统一响应结构；后端未包裹时兜底包裹
    if (payload && typeof payload.code === 'number') {
      return { requestId, ...payload }
    }
    return { code: 0, message: 'ok', data: payload, timestamp: Date.now(), requestId }
  } catch {
    // 网络层异常：不外泄原始 message
    const handled = handleSecurityError(500, { router: options.router, requestId })
    return { code: 500, message: handled.message, data: null, timestamp: Date.now(), requestId }
  }
}
