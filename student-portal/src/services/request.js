/**
 * 学生 PC 门户 · 统一请求层。
 * - token 独立 key：sp_token_v1（不碰 miniapp / frontend 管理端的 token）。
 * - API base 可配置：VITE_API_BASE_URL（源，勿带 /api），默认开发 localhost:8000 / 生产同源。
 * - 绝不调用 /auth/mock-login，绝不免密。
 */
const TOKEN_KEY = 'sp_token_v1'
const REFRESH_KEY = 'sp_refresh_v1'
const API_PREFIX = '/api/v1'

const API_BASE = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return '' // 生产同源：/api/v1 由 Nginx 反代
})()

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}
export function setToken(t) {
  try { localStorage.setItem(TOKEN_KEY, t || '') } catch { /* ignore */ }
}
export function setRefreshToken(t) {
  try { localStorage.setItem(REFRESH_KEY, t || '') } catch { /* ignore */ }
}
export function clearSession() {
  try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(REFRESH_KEY) } catch { /* ignore */ }
}

export async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
      method, headers, body: body ? JSON.stringify(body) : undefined
    })
  } catch (netErr) {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  let payload = null
  try { payload = await res.json() } catch { payload = null }
  if (res.status === 401) { clearSession(); const e = new Error('登录已失效，请重新登录'); e.status = 401; throw e }
  if (!payload || typeof payload.code !== 'number') {
    const e = new Error(`响应结构异常（HTTP ${res.status}）`); e.status = res.status; throw e
  }
  if (payload.code !== 0) {
    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e
  }
  return payload.data
}
