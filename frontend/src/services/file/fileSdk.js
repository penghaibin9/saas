import { API_BASE_URL, API_PREFIX } from '@/services/http/config'
import { getToken, request, requestBlob } from '@/services/http/client'
import { loadCosBrowserSdk } from './cosBrowserSdk'

export const FILE_STATUS_TEXT = Object.freeze({
  NOT_REQUIRED: '无需扫描',
  PENDING: '等待安全扫描',
  RUNNING: '正在安全扫描',
  CLEAN: '安全可用',
  INFECTED: '检测到风险，已拒绝',
  ERROR: '安全扫描失败'
})

const COS_DIRECT_THRESHOLD = 20 * 1024 * 1024
const COS_SLICE_SIZE = 5 * 1024 * 1024

export function normalizeFile(file = {}) {
  const scanStatus = String(file.scanStatus || 'NOT_REQUIRED').toUpperCase()
  const allowedActions = Array.isArray(file.allowedActions) ? file.allowedActions : []
  return {
    ...file,
    scanStatus,
    statusText: file.statusText || FILE_STATUS_TEXT[scanStatus] || '状态未知',
    readyForBusiness: Boolean(file.readyForBusiness),
    allowedActions,
    canPreview: allowedActions.includes('preview'),
    canDownload: allowedActions.includes('download')
  }
}

function parseEnvelope(raw, status) {
  let payload = null
  try { payload = raw ? JSON.parse(raw) : null } catch { /* handled below */ }
  if (!payload || typeof payload.code !== 'number') {
    const err = new Error(`上传响应结构异常（HTTP ${status || 0}）`)
    err.code = 'BAD_RESPONSE'
    throw err
  }
  return payload
}

function uploadError(payload, status) {
  const err = new Error(payload?.message || `上传失败（HTTP ${status || 0}）`)
  err.biz = true
  err.code = payload?.code || status || 'UPLOAD_FAILED'
  err.bizCode = payload?.bizCode
  err.traceId = payload?.traceId
  return err
}

function emitTo(listeners, value) {
  const percent = Math.max(0, Math.min(100, Math.round(Number(value) || 0)))
  listeners.forEach((fn) => {
    try { fn(percent) } catch { /* 页面回调异常不影响上传 */ }
  })
}

function openBlob(blob) {
  const url = URL.createObjectURL(blob)
  const opened = window.open(url, '_blank', 'noopener,noreferrer')
  if (!opened) URL.revokeObjectURL(url)
  else setTimeout(() => URL.revokeObjectURL(url), 60000)
  return { url, opened: Boolean(opened) }
}

function saveBlob(blob, fileName = '附件') {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName || '附件'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function openAuthorizedUrl(url, fileName = '附件', preview = false) {
  const anchor = document.createElement('a')
  anchor.href = url
  if (!preview) anchor.download = fileName || '附件'
  anchor.target = preview ? '_blank' : '_self'
  anchor.rel = 'noopener noreferrer'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  return { url, opened: true }
}

function randomKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

/** 历史同域 XHR 上传；本地存储和小文件仍可使用。 */
function createServerUploadTask(file, { bizType, bizId, onProgress, path }) {
  let xhr = null
  let cancelled = false
  const listeners = new Set()
  if (typeof onProgress === 'function') listeners.add(onProgress)

  const send = (retried = false) => new Promise((resolve, reject) => {
    if (!file) {
      reject(uploadError({ message: '请选择要上传的文件', code: 422001 }, 422))
      return
    }
    if (cancelled) {
      const err = new Error('上传已取消'); err.code = 'UPLOAD_CANCELLED'; err.cancelled = true; reject(err); return
    }
    const form = new FormData()
    form.append('file', file)
    form.append('bizType', String(bizType || 'ATTACHMENT'))
    if (bizId !== undefined && bizId !== null && String(bizId) !== '') form.append('bizId', String(bizId))

    xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE_URL}${API_PREFIX}${path}`, true)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.timeout = Math.max(120000, Math.ceil(Number(file.size || 0) / (512 * 1024)) * 1000)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) emitTo(listeners, (event.loaded / event.total) * 100)
    }
    xhr.onerror = () => reject(uploadError({ message: '网络异常，文件上传失败', code: 'NETWORK' }, xhr?.status))
    xhr.ontimeout = () => reject(uploadError({ message: '文件上传超时，请重试', code: 'UPLOAD_TIMEOUT' }, 408))
    xhr.onabort = () => {
      const err = new Error('上传已取消'); err.code = 'UPLOAD_CANCELLED'; err.cancelled = true; reject(err)
    }
    xhr.onload = async () => {
      let payload
      try { payload = parseEnvelope(xhr.responseText, xhr.status) } catch (e) { reject(e); return }
      const unauthorized = xhr.status === 401 || payload.code === 401001
      if (unauthorized && !retried && !cancelled) {
        try {
          await request('/auth/me')
          resolve(await send(true))
        } catch (e) {
          reject(e)
        }
        return
      }
      if (payload.code !== 0) { reject(uploadError(payload, xhr.status)); return }
      emitTo(listeners, 100)
      resolve(normalizeFile(payload.data || {}))
    }
    xhr.send(form)
  })

  return {
    promise: send(false),
    cancel() {
      cancelled = true
      if (xhr && xhr.readyState !== XMLHttpRequest.DONE) xhr.abort()
    },
    pause() {},
    resume() {},
    onProgress(listener) {
      if (typeof listener === 'function') listeners.add(listener)
      return () => listeners.delete(listener)
    }
  }
}

/**
 * 教师/管理 PC COS 直传任务。
 * 后端只签发当前租户单一 quarantine objectKey 的短时 STS；SDK 负责分片、失败重试、暂停和恢复。
 */
function createCosUploadTask(file, { bizType, bizId, onProgress, clientType = 'ADMIN_PC' }) {
  let cos = null
  let taskId = null
  let sessionId = null
  let cancelled = false
  let activeFallback = null
  const listeners = new Set()
  if (typeof onProgress === 'function') listeners.add(onProgress)

  const abandon = () => {
    if (sessionId) request(`/files/upload-sessions/${encodeURIComponent(sessionId)}/abandon`, { method: 'POST' }).catch(() => {})
  }

  const run = async () => {
    if (!file) throw uploadError({ message: '请选择要上传的文件', code: 422001 }, 422)
    let session
    try {
      session = await request('/files/upload-sessions', {
        method: 'POST',
        body: {
          fileName: file.name || 'unnamed',
          sizeBytes: Number(file.size || 0),
          sha256: null,
          bizType: String(bizType || 'ATTACHMENT'),
          bizId: bizId === undefined || bizId === null || String(bizId) === '' ? null : String(bizId),
          clientType,
          idempotencyKey: randomKey()
        }
      })
    } catch (error) {
      if (error?.code === 'FILE_STORAGE_NOT_COS' || error?.bizCode === 'FILE_STORAGE_NOT_COS') {
        activeFallback = createServerUploadTask(file, { bizType, bizId, onProgress: (v) => emitTo(listeners, v), path: '/files' })
        return activeFallback.promise
      }
      throw error
    }
    sessionId = session.sessionId
    const COS = await loadCosBrowserSdk()
    if (cancelled) throw Object.assign(new Error('上传已取消'), { code: 'UPLOAD_CANCELLED', cancelled: true })
    const credentials = session.credentials || {}
    cos = new COS({
      SecretId: credentials.tmpSecretId,
      SecretKey: credentials.tmpSecretKey,
      SecurityToken: credentials.sessionToken,
      StartTime: Number(credentials.startTime || 0),
      ExpiredTime: Number(credentials.expiredTime || 0),
      FileParallelLimit: 1,
      ChunkParallelLimit: 3,
      ChunkRetryTimes: 3,
      ChunkSize: COS_SLICE_SIZE,
      SliceSize: COS_SLICE_SIZE,
      UploadCheckContentMd5: true
    })
    const uploaded = await new Promise((resolve, reject) => {
      cos.uploadFile({
        Bucket: session.bucketName,
        Region: session.region,
        Key: session.objectKey,
        Body: file,
        SliceSize: COS_SLICE_SIZE,
        onTaskReady(id) { taskId = id },
        onProgress(data) { emitTo(listeners, Number(data?.percent || 0) * 98) }
      }, (error, data) => {
        if (error) reject(uploadError({ message: error.message || 'COS 分片上传失败', code: error.code }, error.statusCode))
        else resolve(data || {})
      })
    })
    if (cancelled) {
      abandon()
      throw Object.assign(new Error('上传已取消'), { code: 'UPLOAD_CANCELLED', cancelled: true })
    }
    const completed = await request(`/files/upload-sessions/${encodeURIComponent(sessionId)}/complete`, {
      method: 'POST',
      body: { etag: uploaded.ETag || uploaded.etag || null }
    })
    emitTo(listeners, 100)
    return normalizeFile(completed || {})
  }

  return {
    promise: run().catch((error) => {
      if (!error?.cancelled) abandon()
      throw error
    }),
    cancel() {
      cancelled = true
      if (activeFallback) activeFallback.cancel()
      if (cos && taskId) cos.cancelTask(taskId)
      abandon()
    },
    pause() {
      if (activeFallback?.pause) activeFallback.pause()
      if (cos && taskId) cos.pauseTask(taskId)
    },
    resume() {
      if (activeFallback?.resume) activeFallback.resume()
      if (cos && taskId) cos.restartTask(taskId)
    },
    onProgress(listener) {
      if (typeof listener === 'function') listeners.add(listener)
      return () => listeners.delete(listener)
    }
  }
}

/**
 * 统一 PC 上传任务。大文件默认走 COS STS 分片；小文件或本地开发使用同域流式上传。
 */
export function createFileUploadTask(file, {
  bizType = 'ATTACHMENT',
  bizId = '',
  onProgress,
  path = '/files',
  forceDirect = false,
  directThreshold = COS_DIRECT_THRESHOLD,
  clientType = 'ADMIN_PC'
} = {}) {
  const useDirect = forceDirect || Number(file?.size || 0) >= Number(directThreshold || COS_DIRECT_THRESHOLD)
  if (useDirect && path === '/files') {
    return createCosUploadTask(file, { bizType, bizId, onProgress, clientType })
  }
  return createServerUploadTask(file, { bizType, bizId, onProgress, path })
}

export const fileSdk = {
  statusText: FILE_STATUS_TEXT,
  normalize: normalizeFile,
  upload: createFileUploadTask,
  async list({ bizType, bizId }) {
    const data = await request('/files', { params: { bizType, bizId } })
    return (data?.items || []).map(normalizeFile)
  },
  async metadata(fileId) {
    return normalizeFile(await request(`/files/${encodeURIComponent(fileId)}`))
  },
  async versions(fileId) {
    const data = await request(`/files/${encodeURIComponent(fileId)}/versions`)
    return (data?.items || []).map((item) => ({ ...item, file: normalizeFile(item.file || {}) }))
  },
  async authorizedUrl(fileId) {
    return request(`/files/${encodeURIComponent(fileId)}/url`)
  },
  async blob(fileId) {
    return requestBlob(`/files/download/${encodeURIComponent(fileId)}`)
  },
  async blobFrom(authorizedPath) {
    if (!authorizedPath || typeof authorizedPath !== 'string' || !authorizedPath.startsWith('/')) {
      const error = new Error('服务端未返回有效文件授权路径')
      error.code = 'INVALID_AUTHORIZED_FILE_PATH'
      throw error
    }
    return requestBlob(authorizedPath)
  },
  async preview(fileId) {
    const auth = await this.authorizedUrl(fileId)
    if (auth?.delivery === 'COS_PRESIGNED' && /^https:\/\//i.test(auth.url || '')) {
      return openAuthorizedUrl(auth.url, auth.fileName, true)
    }
    return openBlob(await this.blob(fileId))
  },
  async previewFrom(authorizedPath) {
    if (/^https:\/\//i.test(authorizedPath || '')) return openAuthorizedUrl(authorizedPath, '附件', true)
    return openBlob(await this.blobFrom(authorizedPath))
  },
  async download(fileId, fileName = '附件') {
    const auth = await this.authorizedUrl(fileId)
    if (auth?.delivery === 'COS_PRESIGNED' && /^https:\/\//i.test(auth.url || '')) {
      return openAuthorizedUrl(auth.url, auth.fileName || fileName, false)
    }
    saveBlob(await this.blob(fileId), fileName)
    return { opened: true }
  },
  async downloadFrom(authorizedPath, fileName = '附件') {
    if (/^https:\/\//i.test(authorizedPath || '')) return openAuthorizedUrl(authorizedPath, fileName, false)
    saveBlob(await this.blobFrom(authorizedPath), fileName)
    return { opened: true }
  }
}

export default fileSdk
