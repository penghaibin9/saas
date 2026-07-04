/**
 * P2 · 统一请求客户端：解析后端统一响应 {code,bizCode,message,data,traceId,timestamp}。
 * 后端不可达时进入 15s 离线冷却（期间直接走 mock fallback，页面不白屏）。
 */
import { API_BASE_URL, API_PREFIX, realApiEnabled } from './config'
import { toast } from '@/utils/toast'

const state = { token: '', refreshToken: '', offlineUntil: 0, notified: false }

export function shouldTryReal() {
  return realApiEnabled() && Date.now() >= state.offlineUntil
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
    if (!e.biz) markOffline() // 网络层异常才进入离线冷却；业务错误正常抛出
    throw e
  } finally {
    clearTimeout(timer)
  }
}

async function ensureToken() {
  if (state.token) return
  const data = await rawRequest('/auth/mock-login', {
    method: 'POST',
    auth: false,
    body: { loginName: 'school_admin01', password: 'dev' }
  })
  state.token = data.accessToken
  state.refreshToken = data.refreshToken || ''
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
    state.token = d.accessToken
    state.refreshToken = d.refreshToken || ''
    return true
  } catch {
    state.token = ''
    state.refreshToken = ''
    return false
  }
}

/** 外部注入 token（如账号密码登录成功后），后续请求不再走 mock-login */
export function setToken(token) {
  state.token = token || ''
}

/** 账号密码登录（POST /api/v1/auth/login，真实校验）；成功后自动持有 token */
export async function loginWithPassword(loginName, password) {
  const data = await rawRequest('/auth/login', {
    method: 'POST',
    auth: false,
    body: { loginName, password }
  })
  state.token = data.accessToken
  state.refreshToken = data.refreshToken || ''
  return data
}

/** 带自动登录的请求入口（401 自动刷新一次并重试） */
export async function request(path, options = {}) {
  await ensureToken()
  try {
    return await rawRequest(path, options)
  } catch (e) {
    if (e.biz && e.code === 401001 && (await tryRefresh())) {
      return rawRequest(path, options)
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
  state.token = ''
  state.refreshToken = ''
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
    if (!e.biz) markOffline()
    throw e
  } finally {
    clearTimeout(timer)
  }
}

/** mock 兜底包裹：真实调用失败（后端挂/业务错）时执行 mockFn，页面不白屏 */
export function withFallback(label, realFn, mockFn) {
  if (!shouldTryReal()) return mockFn()
  return realFn().catch((e) => {
    // eslint-disable-next-line no-console
    console.warn(`[realApi] ${label} 回退 mock：`, e.message)
    return mockFn()
  })
}
