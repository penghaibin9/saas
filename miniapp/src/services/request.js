/**
 * 统一请求封装（P10：上线质量收口版）
 * ------------------------------------------------------------
 * - realRequest()：uni.request 调后端，解析统一响应 {code,bizCode,message,data,traceId}。
 * - 401 刷新单飞：多接口同时 401 只发一次 /auth/refresh，其余排队等结果。
 * - refresh 失败：清 token 并跳转登录页（不再进入奇怪状态）。
 * - realFirst / realFirstStrict：读接口仅网络失败才回退 mock；
 *   业务错误（403/409/422/404）一律透出，绝不假装成功。
 * - safeToast：同文案 2.5s 内不重复弹，错误不刷屏。
 * - createSubmitLock：写操作提交锁，快速连点不重复提交。
 * - 日志绝不输出 token / 手机号 / 身份证。
 */
import { ENV } from '@/config/env'

const TOKEN_KEY = 'gx_token_v1'
const REFRESH_KEY = 'gx_refresh_v1'
const state = { offlineUntil: 0, warned: false }

export function setToken(token) {
  try { uni.setStorageSync(TOKEN_KEY, token || '') } catch (e) { /* 忽略存储失败 */ }
}

export function getToken() {
  try { return uni.getStorageSync(TOKEN_KEY) || '' } catch (e) { return '' }
}

export function setRefreshToken(token) {
  try { uni.setStorageSync(REFRESH_KEY, token || '') } catch (e) { /* 忽略 */ }
}

export function getRefreshToken() {
  try { return uni.getStorageSync(REFRESH_KEY) || '' } catch (e) { return '' }
}

export function clearTokens() {
  setToken('')
  setRefreshToken('')
}

export function shouldTryReal() {
  return !ENV.useMock && Date.now() >= state.offlineUntil
}

function markOffline() {
  state.offlineUntil = Date.now() + 15000
  if (!state.warned) {
    state.warned = true
    safeToast('网络不稳定，部分内容可能不是最新', 'none')
  }
}

/* ── 错误分类 ── */
export function isBusinessError(e) {
  return !!(e && e.biz)
}

export function isNetworkError(e) {
  return !!(e && (e.code === 'NETWORK' || e.code === 'BAD_RESPONSE'))
}

export function normalizeError(e) {
  const code = e && e.code
  if (isNetworkError(e)) return { kind: 'network', text: '网络异常，请检查网络后重试' }
  if (code === 401001) return { kind: 'auth', text: '登录已失效，请重新登录' }
  if (code === 403001 || code === 403002) return { kind: 'forbidden', text: (e && e.message) || '没有权限执行该操作' }
  if (code === 404001) return { kind: 'notfound', text: (e && e.message) || '数据不存在或已变更' }
  if (code === 409001) return { kind: 'conflict', text: (e && e.message) || '重复提交或状态已变化，请刷新后再试' }
  if (code === 422001 || code === 400001) return { kind: 'invalid', text: (e && e.message) || '填写内容有误，请检查后重试' }
  if (code === 429001) return { kind: 'ratelimit', text: (e && e.message) || '操作过于频繁，请稍后再试' }
  return { kind: 'unknown', text: (e && e.message) || '操作失败，请稍后重试' }
}

/* ── 防刷屏 toast ── */
const _toastState = { last: '', at: 0 }
export function safeToast(title, icon = 'none') {
  try {
    const now = Date.now()
    if (title === _toastState.last && now - _toastState.at < 2500) return
    _toastState.last = title
    _toastState.at = now
    uni.showToast({ title, icon, duration: 2200 })
  } catch (e) { /* 忽略 */ }
}

export function toastError(e) {
  safeToast(normalizeError(e).text, 'none')
}

/* ── 提交锁：同一个写操作短时间不能重复提交 ── */
export function createSubmitLock(cooldownMs = 1200) {
  let busy = false
  let lastAt = 0
  return {
    get busy() { return busy },
    async run(fn) {
      const now = Date.now()
      if (busy || now - lastAt < cooldownMs) {
        return Promise.reject({ code: 'LOCKED', message: '正在提交，请勿重复点击' })
      }
      busy = true
      lastAt = now
      try {
        return await fn()
      } finally {
        busy = false
      }
    }
  }
}

/* ── 未登录/会话失效 → 跳登录 ── */
let _redirecting = false
export function requireAuthOrRedirect(message = '登录已失效，请重新登录') {
  clearTokens()
  if (_redirecting) return
  _redirecting = true
  safeToast(message, 'none')
  setTimeout(() => {
    try { uni.reLaunch({ url: '/pages/login/index' }) } catch (e) { /* 忽略 */ }
    _redirecting = false
  }, 600)
}

/** 模拟一次数据请求。fail=true 时用于演示 error 态。 */
export function mockRequest(payload, { latency = ENV.mockLatency, fail = false } = {}) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (fail) {
        reject({ code: 'MOCK_ERROR', message: '数据加载失败' })
      } else {
        resolve(JSON.parse(JSON.stringify(payload)))
      }
    }, latency)
  })
}

/* ── 401 刷新单飞队列 ── */
let _refreshing = null
function _refreshOnce() {
  if (_refreshing) return _refreshing
  const rt = getRefreshToken()
  if (!rt) {
    return Promise.reject({ code: 401001, biz: true, message: '未登录' })
  }
  _refreshing = realRequest('/auth/refresh', { method: 'POST', auth: false, data: { refreshToken: rt } })
    .then((d) => {
      setToken(d.accessToken)
      setRefreshToken(d.refreshToken || '')
      return d.accessToken
    })
    .catch((e) => {
      // 刷新失败：清 token 跳登录，终止所有排队请求
      requireAuthOrRedirect()
      throw e
    })
    .finally(() => { _refreshing = null })
  return _refreshing
}

/** 真实后端请求：返回统一响应的 data 字段；code!==0 抛业务错（e.biz=true） */
export function realRequest(path, { method = 'GET', data, auth = true, _retried = false } = {}) {
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' }
    const token = auth ? getToken() : ''
    if (token) header.Authorization = 'Bearer ' + token
    uni.request({
      url: ENV.apiBaseUrl + ENV.apiPrefix + path,
      method,
      data: data || {},
      header,
      timeout: ENV.requestTimeout,
      success: (res) => {
        const body = res.data
        if (!body || typeof body.code !== 'number') {
          markOffline()
          reject({ code: 'BAD_RESPONSE', message: '响应结构异常' })
          return
        }
        if (body.code !== 0) {
          if (body.code === 401001 && auth && !_retried && !path.startsWith('/auth/')) {
            // 401：单飞刷新后重试一次；再失败则透出（requireAuthOrRedirect 已在刷新失败时触发）
            _refreshOnce()
              .then(() => realRequest(path, { method, data, auth, _retried: true }))
              .then(resolve)
              .catch(() => reject({ code: body.code, biz: true, message: body.message || '登录已失效', traceId: body.traceId }))
            return
          }
          reject({ code: body.code, biz: true, message: body.message || '业务错误', traceId: body.traceId })
          return
        }
        state.warned = false
        resolve(body.data)
      },
      fail: (err) => {
        markOffline()
        reject({ code: 'NETWORK', message: (err && err.errMsg) || '网络异常' })
      }
    })
  })
}

/**
 * 真实优先（读接口）：仅在网络失败时回退 mock 骨架；
 * 业务错误（401/403/409/422/404）一律透出，由页面处理，绝不假装成功。
 */
export function realFirst(label, realFn, mockFn) {
  if (!shouldTryReal()) return mockFn ? mockFn() : Promise.reject({ code: 'MOCK_ONLY', message: '离线模式' })
  return realFn().catch((e) => {
    if (e && e.biz) throw e // 业务错误透出，不兜底
    if (mockFn) return mockFn()
    throw e
  })
}

/** 与 realFirst 同语义（历史命名保留，写操作请直接用 realRequest，不给 mockFn）。 */
export function realFirstStrict(label, realFn, mockFn) {
  return realFirst(label, realFn, mockFn)
}

/** 兼容旧签名：预留通道 */
export function request(options) {
  return realRequest(options.url, { method: options.method, data: options.data })
}

export default {
  mockRequest, realRequest, realFirst, realFirstStrict, request,
  setToken, getToken, clearTokens, safeToast, toastError, normalizeError,
  createSubmitLock, requireAuthOrRedirect, isBusinessError, isNetworkError
}
