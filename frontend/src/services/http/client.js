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
  state.offlineUntil = Date.now() + 15000
  if (!state.notified) {
    state.notified = true
    try {
      toast.info('后端服务不可达，已自动回退演示数据（mock）')
    } catch {
      /* toast 不可用时静默 */
    }
  }
}

async function rawRequest(path, { method = 'GET', params, body, auth = true } = {}) {
  const qs = params
    ? '?' +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&')
    : ''
  const headers = { 'Content-Type': 'application/json' }
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 4000)
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
      err.traceId = payload.traceId
      throw err
    }
    state.notified = false
    return payload.data
  } catch (e) {
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
  // P11：绝不自动免密登录。未登录直接抛业务 401，由路由守卫送回登录页。
  const err = new Error('未登录，请先登录')
  err.biz = true
  err.code = 401001
  throw err
}

/** 会话失效统一处理：清令牌回登录页（带回跳地址） */
function _redirectToLogin() {
  _holdTokens('', '')
  try {
    if (!window.location.hash.startsWith('#/login') && window.location.pathname !== '/login') {
      const back = encodeURIComponent(window.location.pathname + window.location.search)
      window.location.assign(`/login?redirect=${back}`)
    }
  } catch { /* 非浏览器环境忽略 */ }
}

/** 401 时用 refreshToken 换新 access（一次性轮换）；失败则清空登录态 */
async function tryRefresh() {
  if (!state.refreshToken) return false
  try {
    const d = await rawRequest('/auth/refresh', {
      method: 'POST',
      auth: false,
      body: { refreshToken: state.refreshToken }
    })
    _holdTokens(d.accessToken, d.refreshToken || '')
    return true
  } catch {
    _holdTokens('', '')
    return false
  }
}

/** 外部注入 token（如账号密码登录成功后） */
export function setToken(token) {
  state.token = token || ''
  _save(TOKEN_KEY, state.token)
}

/** 当前已登录令牌（sessionStorage：F5 不掉登录，关浏览器即清） */
export function getToken() {
  return state.token
}

/** 从 JWT 令牌解出当前用户（仅本地读取 payload 做前端路由判断，真正鉴权仍以后端 403 为准）。
 *  未登录 / 令牌非法时返回 null。 */
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
      realName: p.realName,
      userType: p.userType,
      currentRoleCode: p.currentRoleCode,
      tenantId: p.tenantId
    }
  } catch {
    return null
  }
}

/** 是否为平台超级管理员（老板本人）——用于 /admin/platform 路由守卫 */
export function isPlatformSuperAdmin() {
  const u = currentUserFromToken()
  return !!u && (u.currentRoleCode === 'PLATFORM_SUPER_ADMIN' || u.userType === 'PLATFORM_SUPER_ADMIN')
}

/** 账号密码登录（POST /api/v1/auth/login，真实校验）；成功后自动持有 token */
export async function loginWithPassword(loginName, password) {
  const data = await rawRequest('/auth/login', {
    method: 'POST',
    auth: false,
    body: { loginName, password }
  })
  _holdTokens(data.accessToken, data.refreshToken || '')
  return data
}

/** 请求入口（必须已登录；401 自动刷新一次并重试，刷新失败回登录页） */
export async function request(path, options = {}) {
  await ensureToken()
  try {
    return await rawRequest(path, options)
  } catch (e) {
    if (e.biz && e.code === 401001) {
      if (await tryRefresh()) return rawRequest(path, options)
      _redirectToLogin() // 会话彻底失效：回登录页，不让页面停在半死状态
    }
    throw e
  }
}

/** 登出：服务端 jti 黑名单 + 吊销 refresh，本地清空 */
export async function logoutRemote() {
  try {
    await rawRequest('/auth/logout', { method: 'POST' })
  } catch {
    /* 离线登出静默 */
  }
  _holdTokens('', '')
}

/** multipart 文件上传（FormData；浏览器自带 boundary，勿手工设 Content-Type） */
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

/** 二进制下载（Excel 模板/导出文件等）：复用现有 token/baseURL/401 刷新机制 */
export async function requestBlob(path, { method = 'GET', params, body, auth = true } = {}) {
  await ensureToken()
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
        const err = new Error(`下载失败（HTTP ${res.status}）`)
        err.biz = true
        err.code = res.status
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
      if (await tryRefresh()) return doFetch()
      _redirectToLogin()
    }
    throw e
  }
}

/** mock 兜底包裹：真实调用失败（后端挂/业务错）时执行 mockFn，页面不白屏 */
export function withFallback(label, realFn, mockFn) {
  if (!shouldTryReal()) {
    if (canUseMockFallback()) return mockFn()
    return Promise.reject(strictFailure(label, new Error('生产环境已禁用 mock fallback')))
  }
  return realFn().catch((e) => {
    if (e.biz || !canUseMockFallback()) throw strictFailure(label, e)
    // eslint-disable-next-line no-console
    console.warn(`[realApi] ${label} 回退 mock：`, e.message)
    return mockFn()
  })
}

export async function realFirst(label, realFn, mockFn, { write = false } = {}) {
  if (!shouldTryReal()) {
    if (!write && canUseMockFallback()) return mockFn()
    throw strictFailure(label, new Error(write ? '写操作禁止 mock 成功' : '生产环境已禁用 mock fallback'))
  }
  try {
    return await realFn()
  } catch (e) {
    if (e.biz || write || !canUseMockFallback()) throw strictFailure(label, e)
    return mockFn()
  }
}
