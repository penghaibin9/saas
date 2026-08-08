const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const API_PREFIX = import.meta.env.VITE_API_PREFIX || '/api/v1'
const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_REQUEST_TIMEOUT_MS || 15000)
const TOKEN_KEY = 'saas_access_token'
const REFRESH_KEY = 'saas_refresh_token'
const OFFLINE_COOLDOWN_MS = 5000

const state = {
  token: '',
  refreshToken: '',
  offlineUntil: 0,
  notified: false
}

function _load(key) {
  try { return localStorage.getItem(key) || '' } catch { return '' }
}
function _save(key, value) {
  try {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
  } catch { /* ignore */ }
}

state.token = _load(TOKEN_KEY)
state.refreshToken = _load(REFRESH_KEY)

function isWriteMethod(method = 'GET') {
  return !['GET', 'HEAD', 'OPTIONS'].includes(String(method).toUpperCase())
}

function canUseMockFallback() {
  const configured = String(import.meta.env.VITE_USE_MOCK || '').toLowerCase() === 'true'
  const isProd = !!import.meta.env.PROD
  return configured && !isProd
}

function isBackendOffline() {
  return Date.now() < state.offlineUntil
}

function clearOfflineState() {
  state.offlineUntil = 0
  state.notified = false
}

function throwOfflineSkip(method) {
  const e = new Error(`后端暂不可达，跳过 ${method} 请求`)
  e.offlineSkip = true
  throw e
}

function markOffline() {
  state.offlineUntil = Date.now() + OFFLINE_COOLDOWN_MS
  if (!state.notified) {
    state.notified = true
    try {
      // 保留开发环境提示；生产环境 canUseMockFallback=false，不会进入此分支的 mock 语义。
      console.info('后端服务暂不可达')
    } catch {
      /* ignore */
    }
  }
}

async function rawRequest(path, {
  method = 'GET', params, body, auth = true, forceProbe = false, headers: extraHeaders = {}
} = {}) {
  const methodUp = String(method || 'GET').toUpperCase()
  if (!forceProbe && isBackendOffline() && canUseMockFallback() && !isWriteMethod(methodUp)) {
    throwOfflineSkip(methodUp)
  }
  const qs = params
    ? '?' + Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&')
    : ''
  const headers = { 'Content-Type': 'application/json', ...(extraHeaders || {}) }
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const res = await fetch(`${API_BASE_URL}${API_PREFIX}${path}${qs}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    })
    const payload = await res.json().catch(() => null)
    if (!payload || typeof payload.code !== 'number') {
      throw new Error(`响应结构异常（HTTP ${res.status}）`)
    }
    if (payload.code !== 0) {
      const err = new Error(payload.message || `业务错误 ${payload.code}`)
      err.biz = true
      err.code = payload.code
      err.bizCode = payload.bizCode
      err.details = payload.details
      err.traceId = payload.traceId
      throw err
    }
    clearOfflineState()
    return payload.data
  } catch (e) {
    if (e.offlineSkip) throw e
    if (!e.biz) {
      markOffline()
      if (!canUseMockFallback() || isWriteMethod(method)) {
        e.biz = true
        e.code = isWriteMethod(method) ? 503002 : 503001
        e.message = isWriteMethod(method)
          ? '真实接口不可用，写操作禁止 mock 成功'
          : '真实接口不可用，生产环境已禁用 mock fallback'
      }
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

async function ensureToken() {
  if (state.token) return
  const err = new Error('未登录，请先登录')
  err.biz = true
  err.code = 401001
  throw err
}

function _holdTokens(accessToken, refreshToken) {
  state.token = accessToken || ''
  if (refreshToken !== undefined) state.refreshToken = refreshToken || ''
  _save(TOKEN_KEY, state.token)
  _save(REFRESH_KEY, state.refreshToken)
  clearOfflineState()
}

function _redirectToLogin() {
  _holdTokens('', '')
  try {
    if (!window.location.hash.startsWith('#/login') && window.location.pathname !== '/login') {
      const back = encodeURIComponent(window.location.pathname + window.location.search)
      window.location.assign(`/login?redirect=${back}`)
    }
  } catch { /* 非浏览器环境忽略 */ }
}

let refreshPromise = null
async function tryRefresh() {
  if (!state.refreshToken) return false
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    try {
      const d = await rawRequest('/auth/refresh', {
        method: 'POST', auth: false, forceProbe: true,
        body: { refreshToken: state.refreshToken }
      })
      _holdTokens(d.accessToken, d.refreshToken || '')
      return true
    } catch {
      _holdTokens('', '')
      return false
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

export function setToken(token) {
  state.token = token || ''
  _save(TOKEN_KEY, state.token)
}

export function setRefreshToken(token) {
  state.refreshToken = token || ''
  _save(REFRESH_KEY, state.refreshToken)
}

export function applyAuthSession(accessToken, refreshToken) {
  _holdTokens(accessToken || '', refreshToken)
}

export function clearAuthSession() {
  _holdTokens('', '')
}

export function getToken() { return state.token }
export function getRefreshToken() { return state.refreshToken }
export function backendOffline() { return isBackendOffline() }
export function mockFallbackEnabled() { return canUseMockFallback() }

export function currentUserFromToken() {
  if (!state.token) return null
  try {
    const parts = state.token.split('.')
    if (parts.length < 2) return null
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(b64).split('').map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join('')
    )
    const p = JSON.parse(json)
    return {
      userId: p.userId,
      loginName: p.loginName,
      realName: p.realName,
      userType: p.userType,
      currentRoleCode: p.currentRoleCode,
      activeContextId: p.activeContextId || '',
      tenantId: p.tenantId,
      tenantName: p.tenantName
    }
  } catch {
    return null
  }
}

export async function fetchMyAuthContexts() {
  const me = await request('/auth/me')
  return {
    activeContextId: (me && me.activeContextId) || '',
    contexts: Array.isArray(me && me.contexts) ? me.contexts : [],
    currentRole: (me && me.currentRole) || {}
  }
}

export async function switchAuthContext(contextId, clientType = 'PC') {
  const data = await request('/auth/switch-role', {
    method: 'POST', body: { contextId, clientType }
  })
  if (data && data.accessToken) {
    applyAuthSession(
      data.accessToken,
      Object.prototype.hasOwnProperty.call(data, 'refreshToken') ? (data.refreshToken || '') : undefined
    )
  }
  return data
}

export function isPlatformSuperAdmin() {
  const u = currentUserFromToken()
  return !!u && (u.currentRoleCode === 'PLATFORM_SUPER_ADMIN' || u.userType === 'PLATFORM_SUPER_ADMIN')
}

export async function issueLoginCaptcha(payload) {
  return rawRequest('/auth/captcha', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

export async function loginWithPassword(loginName, password, tenantCode = '', challenge = {}) {
  clearOfflineState()
  const data = await rawRequest('/auth/login', {
    method: 'POST', auth: false, forceProbe: true,
    body: {
      loginName, password, tenantCode: tenantCode || undefined,
      clientType: challenge.clientType || 'PC', captchaId: challenge.captchaId || undefined,
      captchaCode: challenge.captchaCode || undefined, clientNonce: challenge.clientNonce || undefined
    }
  })
  _holdTokens(data.accessToken, data.refreshToken || '')
  return data
}

export async function request(path, options = {}) {
  await ensureToken()
  try {
    return await rawRequest(path, options)
  } catch (e) {
    if (e.biz && e.code === 401001) {
      if (await tryRefresh()) return rawRequest(path, options)
      _redirectToLogin()
    }
    throw e
  }
}

export async function logoutRemote() {
  try { await rawRequest('/auth/logout', { method: 'POST' }) } catch { /* 离线登出静默 */ }
  clearAuthSession()
}

export async function requestUpload(path, file, fieldName = 'file') {
  await ensureToken()
  const fd = new FormData()
  fd.append(fieldName, file)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 15000)
  try {
    const res = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      method: 'POST',
      headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
      body: fd,
      signal: controller.signal
    })
    const payload = await res.json().catch(() => null)
    if (!payload || typeof payload.code !== 'number') throw new Error(`响应结构异常（HTTP ${res.status}）`)
    if (payload.code !== 0) {
      const err = new Error(payload.message || `业务错误 ${payload.code}`)
      err.biz = true
      err.code = payload.code
      err.bizCode = payload.bizCode
      err.details = payload.details
      err.traceId = payload.traceId
      throw err
    }
    return payload.data
  } finally {
    clearTimeout(timer)
  }
}

export async function requestBlob(path, options = {}) {
  await ensureToken()
  const params = options.params
  const qs = params
    ? '?' + Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
    : ''
  const headers = { ...(options.headers || {}) }
  if (state.token) headers.Authorization = `Bearer ${state.token}`
  const res = await fetch(`${API_BASE_URL}${API_PREFIX}${path}${qs}`, {
    method: options.method || 'GET', headers
  })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    const err = new Error(payload?.message || `下载失败（HTTP ${res.status}）`)
    err.biz = true
    err.code = payload?.code || res.status
    err.bizCode = payload?.bizCode
    throw err
  }
  return res.blob()
}
