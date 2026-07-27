/**
 * 学生 PC 门户 · 统一请求层。
 * - token 独立 key：sp_token_v1（不碰 miniapp / frontend 管理端的 token）。
 * - API base 可配置：VITE_API_BASE_URL（源，勿带 /api），默认开发 localhost:8000 / 生产同源。
 * - 401 单飞刷新并重试一次；刷新失败才清会话，避免长表单因 access token 到期直接丢失。
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
export function getRefreshToken() {
  try { return localStorage.getItem(REFRESH_KEY) || '' } catch { return '' }
}
export function setRefreshToken(t) {
  try { localStorage.setItem(REFRESH_KEY, t || '') } catch { /* ignore */ }
}
export function clearSession() {
  try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(REFRESH_KEY) } catch { /* ignore */ }
}

function withQuery(path, params) {
  const entries = Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== '')
  if (!entries.length) return path
  const query = new URLSearchParams()
  for (const [key, value] of entries) {
    if (Array.isArray(value)) value.forEach((item) => query.append(key, String(item)))
    else query.append(key, String(value))
  }
  return `${path}${path.includes('?') ? '&' : '?'}${query.toString()}`
}

function authError(message = '登录已失效，请重新登录') {
  const e = new Error(message)
  e.status = 401
  e.code = 401001
  e.biz = true
  return e
}

async function responseJson(res) {
  try { return await res.json() } catch { return null }
}

let refreshing = null
async function refreshOnce() {
  if (refreshing) return refreshing
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    clearSession()
    throw authError()
  }
  refreshing = (async () => {
    let res
    try {
      res = await fetch(`${API_BASE}${API_PREFIX}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken })
      })
    } catch {
      const e = new Error('网络不可达，请检查后端服务')
      e.network = true
      throw e
    }
    const payload = await responseJson(res)
    if (!payload || typeof payload.code !== 'number' || res.status === 401 || payload.code !== 0) {
      throw authError((payload && payload.message) || '登录已失效，请重新登录')
    }
    const data = payload.data || {}
    if (!data.accessToken) throw authError()
    setToken(data.accessToken)
    setRefreshToken(data.refreshToken || refreshToken)
    return data.accessToken
  })()
    .catch((e) => {
      clearSession()
      throw e
    })
    .finally(() => { refreshing = null })
  return refreshing
}

function isUnauthorized(res, payload) {
  return res.status === 401 || (payload && payload.code === 401001)
}

export async function request(path, {
  method = 'GET', body, auth = true, params, query, _retried = false
} = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  const requestPath = withQuery(path, params || query)
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${requestPath}`, {
      method, headers, body: body ? JSON.stringify(body) : undefined
    })
  } catch {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  const payload = await responseJson(res)
  if (isUnauthorized(res, payload)) {
    if (auth && !_retried && !path.startsWith('/auth/')) {
      await refreshOnce()
      return request(path, { method, body, auth, params, query, _retried: true })
    }
    clearSession()
    throw authError((payload && payload.message) || undefined)
  }
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
export async function uploadFile(path, file, { auth = true, _retried = false } = {}) {
  const headers = {}
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`
  const form = new FormData()
  form.append('file', file)
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { method: 'POST', headers, body: form })
  } catch {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  const payload = await responseJson(res)
  if (isUnauthorized(res, payload)) {
    if (auth && !_retried) {
      await refreshOnce()
      return uploadFile(path, file, { auth, _retried: true })
    }
    clearSession()
    throw authError((payload && payload.message) || undefined)
  }
  if (!payload || typeof payload.code !== 'number') {
    const e = new Error(`响应结构异常（HTTP ${res.status}）`); e.status = res.status; throw e
  }
  if (payload.code !== 0) {
    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e
  }
  return payload.data
}

/** 下载受业务关系保护的文件；以 Bearer token 取回 blob，避免把令牌拼进 URL。 */
export async function downloadFile(path, fallbackName = '毕业设计材料', _retried = false) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(`${API_BASE}${API_PREFIX}${path}`, { headers })
  } catch {
    const e = new Error('网络不可达，请检查后端服务'); e.network = true; throw e
  }
  if (res.status === 401) {
    if (!_retried) {
      await refreshOnce()
      return downloadFile(path, fallbackName, true)
    }
    clearSession()
    throw authError()
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
