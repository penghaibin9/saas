/**
 * 统一请求封装（上线质量收口版）
 * - 401 刷新单飞；业务错误不回退假成功；写操作支持提交锁。
 * - 学生岗位实习请求自动携带当前选择批次，所有子页面共享同一业务上下文。
 */
import { ENV } from '@/config/env'

const TOKEN_KEY = 'gx_token_v1'
const REFRESH_KEY = 'gx_refresh_v1'
const INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'
const state = { offlineUntil: 0, warned: false }

export function setToken(token) {
  try { uni.setStorageSync(TOKEN_KEY, token || '') } catch (e) {}
}

export function getToken() {
  try { return uni.getStorageSync(TOKEN_KEY) || '' } catch (e) { return '' }
}

export function setRefreshToken(token) {
  try { uni.setStorageSync(REFRESH_KEY, token || '') } catch (e) {}
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
    safeToast(ENV.allowMockFallback
      ? '网络不稳定，开发演示数据可能不是最新'
      : '网络不稳定，请检查网络后重试', 'none')
  }
}

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

const _toastState = { last: '', at: 0 }
export function safeToast(title, icon = 'none') {
  try {
    const now = Date.now()
    if (title === _toastState.last && now - _toastState.at < 2500) return
    _toastState.last = title
    _toastState.at = now
    uni.showToast({ title, icon, duration: 2200 })
  } catch (e) {}
}

export function toastError(e) {
  safeToast(normalizeError(e).text, 'none')
}

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

let _redirecting = false
export function requireAuthOrRedirect(message = '登录已失效，请重新登录') {
  clearTokens()
  if (_redirecting) return
  _redirecting = true
  safeToast(message, 'none')
  setTimeout(() => {
    try { uni.reLaunch({ url: '/pages/login/index' }) } catch (e) {}
    _redirecting = false
  }, 600)
}

export function mockRequest(payload, { latency = ENV.mockLatency, fail = false } = {}) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (fail) reject({ code: 'MOCK_ERROR', message: '数据加载失败' })
      else resolve(JSON.parse(JSON.stringify(payload)))
    }, latency)
  })
}

let _refreshing = null
function _refreshOnce() {
  if (_refreshing) return _refreshing
  const rt = getRefreshToken()
  if (!rt) return Promise.reject({ code: 401001, biz: true, message: '未登录' })
  _refreshing = realRequest('/auth/refresh', {
    method: 'POST', auth: false, data: { refreshToken: rt }
  }).then((d) => {
    setToken(d.accessToken)
    setRefreshToken(d.refreshToken || '')
    return d.accessToken
  }).catch((e) => {
    requireAuthOrRedirect()
    throw e
  }).finally(() => { _refreshing = null })
  return _refreshing
}

function selectedInternshipBatchId(path) {
  if (!String(path || '').startsWith('/mobile/internship')) return ''
  try {
    const value = String(uni.getStorageSync(INTERNSHIP_BATCH_KEY) || '').trim()
    return /^\d+$/.test(value) ? value : ''
  } catch (e) {
    return ''
  }
}

/** 真实后端请求：返回统一响应 data；code!==0 抛业务错误。 */
export function realRequest(path, { method = 'GET', data, auth = true, _retried = false } = {}) {
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' }
    const token = auth ? getToken() : ''
    if (token) header.Authorization = 'Bearer ' + token
    const internshipBatchId = selectedInternshipBatchId(path)
    if (internshipBatchId) header['X-Internship-Batch-Id'] = internshipBatchId
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

export function realFirst(label, realFn, mockFn) {
  if (!shouldTryReal()) {
    if (ENV.allowMockFallback && mockFn) return mockFn()
    return Promise.reject({ code: 'NETWORK', message: '真实接口不可用，生产环境已禁用 mock fallback' })
  }
  return realFn().catch((e) => {
    if (e && e.biz) throw e
    if (ENV.allowMockFallback && mockFn) return mockFn()
    throw e
  })
}

export function realFirstStrict(label, realFn, mockFn) {
  return realFirst(label, realFn, mockFn)
}

export function request(options) {
  return realRequest(options.url, { method: options.method, data: options.data })
}

export default {
  mockRequest, realRequest, realFirst, realFirstStrict, request,
  setToken, getToken, clearTokens, safeToast, toastError, normalizeError,
  createSubmitLock, requireAuthOrRedirect, isBusinessError, isNetworkError
}
