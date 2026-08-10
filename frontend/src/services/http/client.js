/**
 * P2 · 统一请求客户端：解析后端统一响应 {code,bizCode,message,data,traceId,timestamp}。
 * 后端不可达时进入 15s 离线冷却（期间直接走 mock fallback，页面不白屏）。
 * P11：不再自动 mock-login——未登录必须经登录页（账号密码=真实库 / 演示账号=演示租户）。
 * 令牌存 sessionStorage：F5 刷新不掉登录，关浏览器即清（比 localStorage 更安全）。
 */
import { API_BASE_URL, API_PREFIX, allowMockFallback, realApiEnabled } from './config'
import { toast } from '@/utils/toast'

const TOKEN_KEY = 'gx_pc_token_v1'
const REFRESH_KEY = 'gx_pc_refresh_v1'

function _load(key) {
  try { return sessionStorage.getItem(key) || '' } catch { return '' }
}

function _save(key, val) {
  try { val ? sessionStorage.setItem(key, val) : sessionStorage.removeItem(key) } catch { /* 忽略 */ }
}

const state = { token: _load(TOKEN_KEY), refreshToken: _load(REFRESH_KEY), offlineUntil: 0, notified: false }

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

function _holdTokens(access, refresh) {
  state.token = access || ''
  state.refreshToken = refresh || ''
  _save(TOKEN_KEY, state.token)
  _save(REFRESH_KEY, state.refreshToken)
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
      toast.info('后端服务不可达，已自动回退演示数据（mock）')
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
        e.message = isWriteMethod(method) ? '真实接口不可用，写操作禁止 mock 成功' : '真实接口不可用，生产环境已禁用 mock fallback'
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
  const refreshTokenAtStart = state.refreshToken
  const accessTokenAtStart = state.token
  if (!refreshTokenAtStart) return false
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    try {
      const d = await rawRequest('/auth/refresh', {
        method: 'POST',
        auth: false,
        forceProbe: true,
        body: { refreshToken: refreshTokenAtStart }
      })
      // 身份切换/重新登录可能在 refresh 飞行期间已经替换整套会话。
      // 旧 refresh 的迟到成功不得把新角色 token 覆盖回旧角色。
      if (state.token !== accessTokenAtStart || state.refreshToken !== refreshTokenAtStart) {
        return !!state.token
      }
      _holdTokens(d.accessToken, d.refreshToken || '')
      return true
    } catch {
      // 同理，旧 refresh 的迟到失败不能清空刚由 switch-role/login 写入的新会话。
      if (state.token !== accessTokenAtStart || state.refreshToken !== refreshTokenAtStart) {
        return !!state.token
      }
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

export function applyAuthSession(accessToken, refreshToken) {
  if (refreshToken === undefined) {
    state.token = accessToken || ''
    _save(TOKEN_KEY, state.token)
    return
  }
  _holdTokens(accessToken, refreshToken)
}

export function clearAuthSession() {
  _holdTokens('', '')
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
  const data = await request('/auth/switch-role', {
    method: 'POST',
    body: { contextId, clientType }
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

export async function requestPasswordResetCode(payload) {
  return rawRequest('/auth/password-reset/request', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

export async function verifyPasswordResetCode(payload) {
  return rawRequest('/auth/password-reset/verify', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

export async function confirmPasswordReset(payload) {
  return rawRequest('/auth/password-reset/confirm', { method: 'POST', auth: false, forceProbe: true, body: payload })
}

/** 账号密码登录（POST /api/v1/auth/login，真实校验）；成功后自动持有 token */
export async function loginWithPassword(loginName, password, tenantCode = '', challenge = {}) {
  clearOfflineState()
  const data = await rawRequest('/auth/login', {
    method: 'POST',
    auth: false,
    forceProbe: true,
    body: { loginName, password, tenantCode: tenantCode || undefined,
      clientType: challenge.clientType || 'PC', captchaId: challenge.captchaId || undefined,
      captchaCode: challenge.captchaCode || undefined, clientNonce: challenge.clientNonce || undefined }
  })
  _holdTokens(data.accessToken, data.refreshToken || '')
  return data
}

export async function request(path, options = {}) {
  await ensureToken()
  const accessTokenAtStart = state.token
  try {
    return await rawRequest(path, options)
  } catch (e) {
    if (e.biz && e.code === 401001) {
      // 该 401 如果属于身份切换前的旧 token，新会话已经可用时直接重试，禁止再拿旧 refresh 竞争。
      if (state.token && state.token !== accessTokenAtStart) return rawRequest(path, options)
      if (await tryRefresh()) return rawRequest(path, options)
      // refresh 等待期间也可能完成 switch-role/login；再次保护，避免误跳登录页。
      if (state.token && state.token !== accessTokenAtStart) return rawRequest(path, options)
      _redirectToLogin()
    }
    throw e
  }
}

export async function logoutRemote() {
  try {
    await rawRequest('/auth/logout', { method: 'POST' })
  } catch {
    /* 离线登出静默 */
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
        signal: controller.signal
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
