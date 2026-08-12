/**
 * P2 · 统一请求客户端：解析后端统一响应 {code,bizCode,message,data,traceId,timestamp}。
 * 后端不可达时进入 15s 离线冷却（期间直接走 mock fallback，页面不白屏）。
 * P11：不再自动 mock-login——未登录必须经登录页（账号密码=真实库 / 演示账号=演示租户）。
 * SECURITY-P0：浏览器 refreshToken 只存在 HttpOnly+SameSite Cookie；accessToken 只驻留内存，
 * 禁止 localStorage/sessionStorage/IndexedDB 持久化。学校 PC / 平台 PC 使用独立 refresh Cookie，
 * 页面刷新后按当前 JWT（有 token 时）或当前路由（F5 时）选择对应 browser session 静默恢复。
 */
import { API_BASE_URL, API_PREFIX, allowMockFallback, realApiEnabled } from './config'
import { toast } from '@/utils/toast'
import { normalizeUiError } from '@/utils/presentationSafety'

const LEGACY_TOKEN_KEYS = ['gx_pc_token_v1', 'gx_pc_refresh_v1']
try { LEGACY_TOKEN_KEYS.forEach((key) => sessionStorage.removeItem(key)) } catch { /* ignore */ }
try { LEGACY_TOKEN_KEYS.forEach((key) => localStorage.removeItem(key)) } catch { /* ignore */ }

const state = { token: '', offlineUntil: 0, notified: false }

/** 开发态首次探测超时更短，避免后端未启动时每页白等 4s */
const REQUEST_TIMEOUT_MS =
  typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.DEV ? 2000 : 4000

/** 后端不可达后的冷却窗口（ms）；冷却内读请求跳过 fetch，直接让 mock fallback 接管 */
const OFFLINE_COOLDOWN_MS = 15000

export function isBackendOffline() {
  return Date.now() < state.offlineUntil
}

function clearOfflineState() {
  state.offlineUntil = 0
  state.notified = false
}

/** 冷却期内跳过真实 fetch，供 mock 层立即回退（不再重复等待超时） */
function throwOfflineSkip(method) {
  const err = new Error('后端离线冷却中')
  err.offlineSkip = true
  if (!canUseMockFallback() || isWriteMethod(method)) {
    err.biz = true
    err.code = isWriteMethod(method) ? 503002 : 503001
    err.message = isWriteMethod(method)
      ? '真实接口不可用，写操作禁止 mock 成功'
      : '真实接口不可用，生产环境已禁用 mock fallback'
  }
  throw err
}

function _holdToken(access) {
  state.token = access || ''
}

export function shouldTryReal() {
  return realApiEnabled()
}

export function canUseMockFallback() {
  return allowMockFallback()
}

export function isWriteMethod(method = 'GET') {
  return !['GET', 'HEAD', 'OPTIONS'].includes(String(method || 'GET').toUpperCase())
}

function strictFailure(label, e) {
  const err = e instanceof Error ? e : new Error(String(e || '真实接口不可用'))
  err.strict = true
  err.label = label
  return err
}

function markOffline() {
  state.offlineUntil = Date.now() + OFFLINE_COOLDOWN_MS
  if (!state.notified) {
    state.notified = true
    try {
      toast.info('服务暂时不可用，已切换为只读体验数据')
    } catch {
      /* toast 不可用时静默 */
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
    ? '?' +
      Object.entries(params)
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
      signal: controller.signal,
      credentials: 'same-origin'
    })
    const payload = await res.json().catch(() => null)
    if (!payload || typeof payload.code !== 'number') {
      throw new Error(`响应结构异常（HTTP ${res.status}）`)
    }
    if (payload.code !== 0) {
      const normalized = normalizeUiError({
        message: payload.message,
        code: payload.code,
        bizCode: payload.bizCode,
        traceId: payload.traceId
      })
      const err = new Error(normalized.userMessage)
      err.biz = true
      err.code = payload.code
      err.bizCode = payload.bizCode
      err.details = payload.details
      err.traceId = payload.traceId
      err.rawDeveloperDetail = normalized.rawDeveloperDetail
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
        e.message = isWriteMethod(method) ? '真实接口不可用，写操作禁止 mock 成功' : '真实接口不可用，生产环境已禁用 mock fallback'
      }
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

function browserSessionChannel() {
  const u = currentUserFromToken()
  const userType = String(u?.userType || '').toUpperCase()
  const role = String(u?.currentRoleCode || '').toUpperCase()
  if (userType.startsWith('PLATFORM_') || role === 'PLATFORM_SUPER_ADMIN') return 'platform'
  if (userType === 'STUDENT' || role === 'STUDENT') return 'student'
  try {
    const route = `${window.location.pathname || ''}${window.location.hash || ''}`.toLowerCase()
    if (route.includes('/platform-login') || route.includes('/admin/platform')) return 'platform'
  } catch { /* SSR/test 环境默认学校 PC */ }
  return 'staff'
}

function browserSessionHeaders() {
  return { 'X-Browser-Session': browserSessionChannel() }
}

let refreshPromise = null
async function tryRefresh() {
  if (refreshPromise) return refreshPromise
  const accessTokenAtStart = state.token
  refreshPromise = (async () => {
    try {
      const d = await rawRequest('/auth/browser-refresh', {
        method: 'POST', auth: false, forceProbe: true, headers: browserSessionHeaders()
      })
      // 登录/切换身份可能在 refresh 飞行期间已经替换会话，迟到响应不得覆盖新身份。
      if (state.token && state.token !== accessTokenAtStart) return true
      _holdToken(d.accessToken || '')
      return !!state.token
    } catch {
      if (state.token && state.token !== accessTokenAtStart) return true
      _holdToken('')
      return false
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

async function ensureToken() {
  if (state.token) return
  if (await tryRefresh()) return
  const err = new Error('未登录，请先登录')
  err.biz = true
  err.code = 401001
  throw err
}

function _redirectToLogin() {
  _holdToken('')
  try {
    if (!window.location.hash.startsWith('#/login') && window.location.pathname !== '/login') {
      const back = encodeURIComponent(window.location.pathname + window.location.search)
      window.location.assign(`/login?redirect=${back}`)
    }
  } catch { /* 非浏览器环境忽略 */ }
}

export function setToken(token) {
  _holdToken(token)
}

export function applyAuthSession(accessToken, _refreshToken) {
  // refreshToken 参数仅保留旧调用兼容；浏览器绝不再保存或读取它。
  _holdToken(accessToken)
}

export function clearAuthSession() {
  _holdToken('')
  clearOfflineState()
  try {
    import('@/security/permissionGate').then((m) => m.clearPermissionPatterns?.()).catch(() => {})
  } catch {
    /* ignore */
  }
}

export function getToken() {
  return state.token
}

export function currentUserFromToken() {
  const t = state.token
  if (!t || t.split('.').length !== 3) return null
  try {
    const b64 = t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(b64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
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
  await ensureToken()
  const data = await rawRequest('/auth/browser-switch-role', {
    method: 'POST',
    body: { contextId, clientType }
  })
  if (data && data.accessToken) applyAuthSession(data.accessToken)
  return data
}

export function isPlatformSuperAdmin() {
  const u = currentUserFromToken()
  return !!u && (u.currentRoleCode === 'PLATFORM_SUPER_ADMIN' || u.userType === 'PLATFORM_SUPER_ADMIN')
}

export async function issueLoginCaptcha(payload) {
  return rawRequest('/auth/captcha', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

export async function requestPasswordResetCode(payload) {
  return rawRequest('/auth/password-reset/request', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

export async function verifyPasswordResetCode(payload) {
  return rawRequest('/auth/password-reset/verify', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

export async function confirmPasswordReset(payload) {
  return rawRequest('/auth/password-reset/confirm', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

/** 浏览器账号密码登录：refreshToken 由后端写对应 PC 入口的 HttpOnly Cookie，JS 只得到内存 accessToken。 */
export async function loginWithPassword(loginName, password, tenantCode = '', challenge = {}) {
  clearOfflineState()
  const data = await rawRequest('/auth/browser-login', {
    method: 'POST',
    auth: false,
    forceProbe: true,
    body: { loginName, password, tenantCode: tenantCode || undefined,
      clientType: challenge.clientType || 'PC', captchaId: challenge.captchaId || undefined,
      captchaCode: challenge.captchaCode || undefined, clientNonce: challenge.clientNonce || undefined }
  })
  _holdToken(data.accessToken || '')
  return data
}

export async function request(path, options = {}) {
  await ensureToken()
  const accessTokenAtStart = state.token
  try {
    return await rawRequest(path, options)
  } catch (e) {
    if (e.biz && e.code === 401001) {
      if (state.token && state.token !== accessTokenAtStart) return rawRequest(path, options)
      if (await tryRefresh()) return rawRequest(path, options)
      if (state.token && state.token !== accessTokenAtStart) return rawRequest(path, options)
      _redirectToLogin()
    }
    throw e
  }
}

export async function logoutRemote() {
  try {
    // rawRequest has no implicit ensure/refresh. Keeping auth enabled sends a still-live access
    // token for jti blacklisting when available, while cookie-only logout still works when the
    // in-memory token is already empty/expired. Explicit channel prevents another PC surface's
    // HttpOnly cookie from being consumed or cleared by this logout.
    await rawRequest('/auth/browser-logout', {
      method: 'POST', auth: true, forceProbe: true, headers: browserSessionHeaders()
    })
  } catch {
    /* 离线登出静默；本地 access 仍必须清掉，服务端响应会尽力清除当前通道 Cookie */
  }
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
      signal: controller.signal,
      credentials: 'same-origin'
    })
    const payload = await res.json().catch(() => null)
    if (!payload || typeof payload.code !== 'number') throw new Error(`响应结构异常（HTTP ${res.status}）`)
    if (payload.code !== 0) {
      const err = new Error(payload.message || `业务错误 ${payload.code}`)
      err.biz = true
      err.code = payload.code
      err.bizCode = payload.bizCode
      err.details = payload.details
      throw err
    }
    return payload.data
  } catch (e) {
    if (!e.biz) {
      markOffline()
      e.biz = true
      e.code = 503002
      e.message = '真实接口不可用，写操作禁止 mock 成功'
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export async function requestBlob(path, { method = 'GET', params, body, auth = true } = {}) {
  await ensureToken()
  const accessTokenAtStart = state.token
  const qs = params
    ? '?' +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&')
    : ''

  const doFetch = async () => {
    const headers = {}
    if (auth && state.token) headers.Authorization = `Bearer ${state.token}`
    if (body) headers['Content-Type'] = 'application/json'
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 15000)
    try {
      const res = await fetch(`${API_BASE_URL}${API_PREFIX}${path}${qs}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        credentials: 'same-origin'
      })
      if (res.status === 401) {
        const err = new Error('未登录，请先登录')
        err.biz = true
        err.code = 401001
        throw err
      }
      if (!res.ok) {
        const payload = await res.clone().json().catch(() => null)
        const err = new Error(payload?.message || `下载失败（HTTP ${res.status}）`)
        err.biz = true
        err.code = payload?.code || res.status
        err.bizCode = payload?.bizCode
        err.details = payload?.details
        throw err
      }
      return await res.blob()
    } catch (e) {
      if (!e.biz) {
        markOffline()
        e.biz = true
        e.code = 503001
        e.message = '真实接口不可用，下载失败'
      }
      throw e
    } finally {
      clearTimeout(timer)
    }
  }

  try {
    return await doFetch()
  } catch (e) {
    if (e.biz && e.code === 401001) {
      if (state.token && state.token !== accessTokenAtStart) return doFetch()
      if (await tryRefresh()) return doFetch()
      if (state.token && state.token !== accessTokenAtStart) return doFetch()
      _redirectToLogin()
    }
    throw e
  }
}

export function withFallback(label, realFn, mockFn) {
  if (!shouldTryReal()) {
    if (canUseMockFallback()) return mockFn()
    return Promise.reject(strictFailure(label, new Error('生产环境已禁用 mock fallback')))
  }
  if (canUseMockFallback() && isBackendOffline()) return mockFn()
  return realFn().catch((e) => {
    if (e.biz || !canUseMockFallback()) throw strictFailure(label, e)
    // eslint-disable-next-line no-console
    console.warn(`[realApi] ${label} 回退 mock：`, e.message)
    return mockFn()
  })
}

export function bizStateHint(err) {
  const bc = err && (err.bizCode || '')
  if (bc === 'NO_PERMISSION' || err?.code === 403001) {
    return { kind: 'no-permission', title: '无访问权限', desc: '你的角色未开通该功能，请联系管理员。' }
  }
  if (bc === 'NO_DATA_SCOPE' || err?.code === 403002) {
    return { kind: 'no-scope', title: '尚未配置管理范围', desc: '你还没有被分配可管理的班级/学院/楼栋，请联系管理员配置后再试。' }
  }
  return null
}

export async function realFirst(label, realFn, mockFn, { write = false } = {}) {
  if (!shouldTryReal()) {
    if (!write && canUseMockFallback()) return mockFn()
    throw strictFailure(label, new Error(write ? '写操作禁止 mock 成功' : '生产环境已禁用 mock fallback'))
  }
  if (!write && canUseMockFallback() && isBackendOffline()) return mockFn()
  try {
    return await realFn()
  } catch (e) {
    if (e.biz || write || !canUseMockFallback()) throw strictFailure(label, e)
    return mockFn()
  }
}