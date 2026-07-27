/**
 * 统一请求封装（P10：上线质量收口版）
 * ------------------------------------------------------------
 * - realRequest()：uni.request 调后端，解析统一响应 {code,bizCode,message,data,traceId}。
 * - 401 刷新单飞：多接口同时 401 只发一次 /auth/refresh，其余排队等结果。
 * - refresh 失败：清 token 并跳转登录页（不再进入奇怪状态）。
 * - realFirst / realFirstStrict：读接口仅网络失败才回退 mock；
 *   业务错误（403/409/422/404）一律透出，绝不假装成功。
 * - 教师毕设：显式批次、后端分页传输、前端逐页合并（最多 2000 条，超限明确标记）。
 * - safeToast：同文案 2.5s 内不重复弹，错误不刷屏。
 * - createSubmitLock：写操作提交锁，快速连点不重复提交。
 */
import { ENV } from '@/config/env'

const TOKEN_KEY = 'gx_token_v1'
const REFRESH_KEY = 'gx_refresh_v1'
const GD_TEACHER_BATCH_KEY = 'gx_gd_teacher_batch_v1'
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

/** 教师小程序当前毕业设计批次。对象形状：{ id, name, status }。 */
export function setTeacherGraduationBatch(batch) {
  try {
    const value = batch && batch.id
      ? { id: String(batch.id), name: batch.name || batch.batchName || '', status: batch.status || '' }
      : null
    if (value) uni.setStorageSync(GD_TEACHER_BATCH_KEY, value)
    else uni.removeStorageSync(GD_TEACHER_BATCH_KEY)
  } catch (e) { /* 忽略本地缓存失败，页面仍会要求重新选择 */ }
}
export function getTeacherGraduationBatch() {
  try {
    const value = uni.getStorageSync(GD_TEACHER_BATCH_KEY)
    return value && value.id ? value : null
  } catch (e) { return null }
}
export function clearTokens() {
  setToken('')
  setRefreshToken('')
  setTeacherGraduationBatch(null)
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

export function isBusinessError(e) { return !!(e && e.biz) }
export function isNetworkError(e) { return !!(e && (e.code === 'NETWORK' || e.code === 'BAD_RESPONSE')) }
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
  } catch (e) { /* 忽略 */ }
}
export function toastError(e) { safeToast(normalizeError(e).text, 'none') }

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
      try { return await fn() } finally { busy = false }
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
    try { uni.reLaunch({ url: '/pages/login/index' }) } catch (e) { /* 忽略 */ }
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

/* ── 教师毕业设计批次上下文与分页 ── */
const GD_TEACHER_PREFIX = '/mobile/teacher/graduation'
const GD_TASKBOOK_PATH = `${GD_TEACHER_PREFIX}/taskbooks`
const GD_TEACHER_PAGED_PATHS = new Set([
  GD_TEACHER_PREFIX,
  `${GD_TEACHER_PREFIX}/my-students`,
  `${GD_TEACHER_PREFIX}/midterm/queue`,
  `${GD_TEACHER_PREFIX}/reviews/my`,
  `${GD_TEACHER_PREFIX}/defense/arrangements`,
  `${GD_TEACHER_PREFIX}/grade/queue`,
  `${GD_TEACHER_PREFIX}/choices/pending`,
  `${GD_TEACHER_PREFIX}/change-requests/pending`,
  GD_TASKBOOK_PATH,
  `${GD_TEACHER_PREFIX}/defense/pending`
])
const GD_MAX_AUTO_PAGES = 20

function appendQuery(path, key, value) {
  if (new RegExp(`[?&]${key}=`).test(path)) return path
  return `${path}${path.includes('?') ? '&' : '?'}${key}=${encodeURIComponent(value)}`
}
function replaceQuery(path, key, value) {
  const re = new RegExp(`([?&])${key}=[^&]*`)
  if (re.test(path)) return path.replace(re, `$1${key}=${encodeURIComponent(value)}`)
  return appendQuery(path, key, value)
}
function withTeacherGraduationContext(path) {
  if (!path.startsWith(GD_TEACHER_PREFIX) || path.startsWith(`${GD_TEACHER_PREFIX}/batches`)) return path
  const batch = getTeacherGraduationBatch()
  if (!batch || !batch.id) throw { code: 422001, biz: true, message: '请先选择毕业设计批次' }
  let value = appendQuery(path, 'batchId', batch.id)
  const pathname = value.split('?')[0]
  if (GD_TEACHER_PAGED_PATHS.has(pathname)) {
    value = appendQuery(value, 'page', 1)
    value = appendQuery(value, 'pageSize', 100)
  }
  return value
}

function attachPageMeta(items, meta) {
  Object.defineProperty(items, '_pageMeta', { value: meta, enumerable: false, configurable: true })
  return items
}
function normalizeTeacherGraduationData(path, data) {
  const pathname = path.split('?')[0]
  if (pathname === GD_TASKBOOK_PATH && data && Array.isArray(data.items)) {
    return {
      list: data.items,
      total: data.total || data.items.length,
      page: data.page || 1,
      pageSize: data.pageSize || data.items.length,
      hasMore: !!data.hasMore,
      truncated: !!data.truncated
    }
  }
  if (GD_TEACHER_PAGED_PATHS.has(pathname) && pathname !== GD_TEACHER_PREFIX && data && Array.isArray(data.items)) {
    return attachPageMeta(data.items, {
      total: data.total || data.items.length,
      page: data.page || 1,
      pageSize: data.pageSize || data.items.length,
      hasMore: !!data.hasMore,
      truncated: !!data.truncated
    })
  }
  return data
}

async function collectTeacherGraduationPages(path, first, options) {
  const pathname = path.split('?')[0]
  if (!GD_TEACHER_PAGED_PATHS.has(pathname) || !first || !first.hasMore) {
    return normalizeTeacherGraduationData(path, first)
  }

  let page = Number(first.page || 1)
  let current = first
  let calls = 1
  if (pathname === GD_TEACHER_PREFIX) {
    const merged = {
      ...first,
      students: [...(first.students || [])],
      reviewDetail: [...(first.reviewDetail || [])],
      finalDetail: [...(first.finalDetail || [])]
    }
    while (current.hasMore && calls < GD_MAX_AUTO_PAGES) {
      page += 1; calls += 1
      const nextPath = replaceQuery(path, 'page', page)
      current = await realRequest(nextPath, { ...options, _rawPage: true })
      merged.students.push(...((current && current.students) || []))
      merged.reviewDetail.push(...((current && current.reviewDetail) || []))
      merged.finalDetail.push(...((current && current.finalDetail) || []))
    }
    merged.hasMore = !!(current && current.hasMore)
    merged.truncated = merged.hasMore
    return merged
  }

  const items = [...(first.items || [])]
  while (current.hasMore && calls < GD_MAX_AUTO_PAGES) {
    page += 1; calls += 1
    const nextPath = replaceQuery(path, 'page', page)
    current = await realRequest(nextPath, { ...options, _rawPage: true })
    items.push(...((current && current.items) || []))
  }
  return normalizeTeacherGraduationData(path, {
    ...first,
    items,
    total: Number(first.total || items.length),
    page: 1,
    pageSize: items.length,
    hasMore: !!(current && current.hasMore),
    truncated: !!(current && current.hasMore)
  })
}

/* ── 401 刷新单飞队列 ── */
let _refreshing = null
function _refreshOnce() {
  if (_refreshing) return _refreshing
  const rt = getRefreshToken()
  if (!rt) return Promise.reject({ code: 401001, biz: true, message: '未登录' })
  _refreshing = realRequest('/auth/refresh', { method: 'POST', auth: false, data: { refreshToken: rt } })
    .then((d) => {
      setToken(d.accessToken)
      setRefreshToken(d.refreshToken || '')
      return d.accessToken
    })
    .catch((e) => { requireAuthOrRedirect(); throw e })
    .finally(() => { _refreshing = null })
  return _refreshing
}

/** 真实后端请求：返回统一响应的 data 字段；code!==0 抛业务错（e.biz=true） */
export function realRequest(path, {
  method = 'GET', data, auth = true, _retried = false, _rawPage = false
} = {}) {
  let effectivePath
  try { effectivePath = withTeacherGraduationContext(path) } catch (e) { return Promise.reject(e) }
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' }
    const token = auth ? getToken() : ''
    if (token) header.Authorization = 'Bearer ' + token
    uni.request({
      url: ENV.apiBaseUrl + ENV.apiPrefix + effectivePath,
      method,
      data: data || {},
      header,
      timeout: ENV.requestTimeout,
      success: (res) => {
        const body = res.data
        if (!body || typeof body.code !== 'number') {
          markOffline(); reject({ code: 'BAD_RESPONSE', message: '响应结构异常' }); return
        }
        if (body.code !== 0) {
          if (body.code === 401001 && auth && !_retried && !path.startsWith('/auth/')) {
            _refreshOnce()
              .then(() => realRequest(path, { method, data, auth, _retried: true, _rawPage }))
              .then(resolve)
              .catch(() => reject({ code: body.code, biz: true, message: body.message || '登录已失效', traceId: body.traceId }))
            return
          }
          reject({ code: body.code, biz: true, message: body.message || '业务错误', traceId: body.traceId })
          return
        }
        state.warned = false
        if (_rawPage || method !== 'GET') { resolve(body.data); return }
        collectTeacherGraduationPages(effectivePath, body.data, { method, data, auth, _retried })
          .then(resolve).catch(reject)
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
export function realFirstStrict(label, realFn, mockFn) { return realFirst(label, realFn, mockFn) }
export function request(options) { return realRequest(options.url, { method: options.method, data: options.data }) }

export default {
  mockRequest, realRequest, realFirst, realFirstStrict, request,
  setToken, getToken, clearTokens, safeToast, toastError, normalizeError,
  setTeacherGraduationBatch, getTeacherGraduationBatch,
  createSubmitLock, requireAuthOrRedirect, isBusinessError, isNetworkError
}
