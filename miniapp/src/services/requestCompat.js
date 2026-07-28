import requestDefault, * as base from './request.js'

const TEACHER_GRADUATION_BATCH_KEY = 'gx_teacher_graduation_batch_v1'

export const mockRequest = base.mockRequest
export const realFirst = base.realFirst
export const realFirstStrict = base.realFirstStrict
export const request = base.request
export const setToken = base.setToken
export const getToken = base.getToken
export const setRefreshToken = base.setRefreshToken
export const getRefreshToken = base.getRefreshToken
export const clearTokens = base.clearTokens
export const shouldTryReal = base.shouldTryReal
export const safeToast = base.safeToast
export const toastError = base.toastError
export const normalizeError = base.normalizeError
export const createSubmitLock = base.createSubmitLock
export const requireAuthOrRedirect = base.requireAuthOrRedirect
export const isBusinessError = base.isBusinessError
export const isNetworkError = base.isNetworkError

export function getTeacherGraduationBatch() {
  try {
    const raw = uni.getStorageSync(TEACHER_GRADUATION_BATCH_KEY)
    if (!raw) return null
    const value = typeof raw === 'string' ? JSON.parse(raw) : raw
    return value && /^\d+$/.test(String(value.id || '')) ? value : null
  } catch (e) {
    return null
  }
}

export function setTeacherGraduationBatch(batch) {
  try {
    if (!batch || !/^\d+$/.test(String(batch.id || ''))) {
      uni.removeStorageSync(TEACHER_GRADUATION_BATCH_KEY)
      return
    }
    uni.setStorageSync(TEACHER_GRADUATION_BATCH_KEY, JSON.stringify({
      id: String(batch.id),
      name: String(batch.name || ''),
      status: String(batch.status || '')
    }))
  } catch (e) {}
}

function withTeacherGraduationBatch(path) {
  const value = String(path || '')
  if (!value.startsWith('/mobile/teacher/graduation') || value.startsWith('/mobile/teacher/graduation/batches')) {
    return value
  }
  if (/(?:\?|&)batchId=/.test(value)) return value
  const batch = getTeacherGraduationBatch()
  if (!batch) return value
  return `${value}${value.includes('?') ? '&' : '?'}batchId=${encodeURIComponent(batch.id)}`
}

export function realRequest(path, options) {
  return base.realRequest(withTeacherGraduationBatch(path), options)
}

export default {
  ...requestDefault,
  realRequest,
  getTeacherGraduationBatch,
  setTeacherGraduationBatch
}
