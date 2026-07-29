import { API_BASE_URL, API_PREFIX } from '@/services/http/config'
import { getToken, request, requestBlob } from '@/services/http/client'

export const FILE_STATUS_TEXT = Object.freeze({
  NOT_REQUIRED: '无需扫描',
  PENDING: '等待安全扫描',
  RUNNING: '正在安全扫描',
  CLEAN: '安全可用',
  INFECTED: '检测到风险，已拒绝',
  ERROR: '安全扫描失败'
})

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

/**
 * 教师/管理 PC 上传任务。
 * - 复用统一 access/refresh 会话；401 时触发单飞刷新并只重试一次
 * - onProgress 接收 0~100
 * - cancel() 立即中止 XHR，页面销毁时可安全调用
 */
export function createFileUploadTask(file, {
  bizType = 'ATTACHMENT',
  bizId = '',
  onProgress,
  path = '/files'
} = {}) {
  let xhr = null
  let cancelled = false
  const listeners = new Set()
  if (typeof onProgress === 'function') listeners.add(onProgress)

  const emitProgress = (value) => {
    const percent = Math.max(0, Math.min(100, Math.round(Number(value) || 0)))
    listeners.forEach((fn) => {
      try { fn(percent) } catch { /* 页面回调异常不影响上传 */ }
    })
  }

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
    xhr.timeout = 120000
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) emitProgress((event.loaded / event.total) * 100)
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
          // request() 内部负责 refreshToken 单飞刷新；成功后重新读取新 access token。
          await request('/auth/me')
          resolve(await send(true))
        } catch (e) {
          reject(e)
        }
        return
      }
      if (payload.code !== 0) { reject(uploadError(payload, xhr.status)); return }
      emitProgress(100)
      resolve(normalizeFile(payload.data || {}))
    }
    xhr.send(form)
  })

  const promise = send(false)
  return {
    promise,
    cancel() {
      cancelled = true
      if (xhr && xhr.readyState !== XMLHttpRequest.DONE) xhr.abort()
    },
    onProgress(listener) {
      if (typeof listener === 'function') listeners.add(listener)
      return () => listeners.delete(listener)
    }
  }
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
  async preview(fileId) {
    const blob = await this.blob(fileId)
    const url = URL.createObjectURL(blob)
    const opened = window.open(url, '_blank', 'noopener,noreferrer')
    if (!opened) URL.revokeObjectURL(url)
    else setTimeout(() => URL.revokeObjectURL(url), 60000)
    return { url, opened: Boolean(opened) }
  },
  async download(fileId, fileName = '附件') {
    const blob = await this.blob(fileId)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = fileName || '附件'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }
}

export default fileSdk
