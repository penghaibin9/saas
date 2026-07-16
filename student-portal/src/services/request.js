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

/**
 * 学生门户的文件上传：仅用于先上传、再把 fileId 交给具体业务接口的两步流程。
 * 不给调用方暴露后台接口，也不把文件内容混入普通 JSON 请求。
 */
export async function uploadFile(path, file, { auth = true } = {}) {
  const headers = {}
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  const form = new FormData()
  form.append('file', file)
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { method: 'POST', headers, body: form })
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

/** 下载受业务关系保护的文件；以 Bearer token 取回 blob，避免把令牌拼进 URL。 */
export async function downloadFile(path, fallbackName = '毕业设计材料') {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { headers })
  } catch (netErr) {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  if (!res.ok) {
    const e = new Error('材料下载失败或你已无权访问'); e.status = res.status; throw e
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fallbackName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
