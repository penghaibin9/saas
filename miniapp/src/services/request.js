/**
 * 统一请求封装（P3：真实后端优先 + mock 兜底）
 * ------------------------------------------------------------
 * - mockRequest()：原 mock 通道，保持不变。
 * - realRequest()：uni.request 调后端，解析统一响应 {code,bizCode,message,data,traceId}。
 * - realFirst()：真实优先；网络失败进入 15s 离线冷却并回退 mock，页面不白屏。
 * - token 存 uni storage（gx_token_v1），登录态由 stores/session 维护。
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

export function shouldTryReal() {
  return !ENV.useMock && Date.now() >= state.offlineUntil
}

function markOffline() {
  state.offlineUntil = Date.now() + 15000
  if (!state.warned) {
    state.warned = true
    try { uni.showToast({ title: '后端不可达，已用演示数据', icon: 'none', duration: 2000 }) } catch (e) { /* 忽略 */ }
  }
}

/** 模拟一次数据请求。fail=true 时用于演示 error 态。 */
export function mockRequest(payload, { latency = ENV.mockLatency, fail = false } = {}) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (fail) {
        reject({ code: 'MOCK_ERROR', message: '数据加载失败（模拟）' })
      } else {
        resolve(JSON.parse(JSON.stringify(payload)))
      }
    }, latency)
  })
}

/** 真实后端请求：返回统一响应的 data 字段；code!==0 抛业务错 */
export function realRequest(path, { method = 'GET', data, auth = true } = {}) {
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
          if (body.code === 401001 && auth && !path.startsWith('/auth/')) {
            // 401：尝试用 refreshToken 换新令牌并重试一次
            _refreshAndRetry(path, { method, data }).then(resolve).catch(() =>
              reject({ code: body.code, biz: true, message: body.message || '登录已失效', traceId: body.traceId }))
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

function _refreshAndRetry(path, opts) {
  const rt = getRefreshToken()
  if (!rt) return Promise.reject({ code: 401001, biz: true, message: '未登录' })
  return realRequest('/auth/refresh', { method: 'POST', auth: false, data: { refreshToken: rt } })
    .then((d) => {
      setToken(d.accessToken)
      setRefreshToken(d.refreshToken || '')
      return realRequest(path, opts)
    })
    .catch((e) => {
      setToken('')
      setRefreshToken('')
      throw e
    })
}

/** 真实优先 + mock 兜底 */
export function realFirst(label, realFn, mockFn) {
  if (!shouldTryReal()) return mockFn()
  return realFn().catch((e) => {
    console.warn('[realApi] ' + label + ' 回退 mock：', e && e.message)
    return mockFn()
  })
}

/** 兼容旧签名：预留通道 */
export function request(options) {
  return realRequest(options.url, { method: options.method, data: options.data })
}

export default { mockRequest, realRequest, realFirst, request, setToken, getToken }
