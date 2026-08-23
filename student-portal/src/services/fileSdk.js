import { downloadFile, fetchFileBlob, request, uploadFile } from './request'

export const FILE_STATUS_TEXT = Object.freeze({
  NOT_REQUIRED: '无需扫描',
  PENDING: '等待安全扫描',
  RUNNING: '正在安全扫描',
  CLEAN: '安全可用',
  INFECTED: '检测到风险，已拒绝',
  ERROR: '安全扫描失败'
})

const enc = encodeURIComponent

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

function uploadPath({ bizType = 'ATTACHMENT', bizId = '' } = {}) {
  const query = new URLSearchParams({ bizType: String(bizType || 'ATTACHMENT') })
  if (bizId !== undefined && bizId !== null && String(bizId) !== '') query.set('bizId', String(bizId))
  return `/files?${query.toString()}`
}

function authorizedPath(ticket = {}) {
  const value = String(ticket.url || ticket.downloadUrl || '')
  return value.startsWith('/api/v1/') ? value.slice('/api/v1'.length) : value
}

async function fetchPresignedBlob(url, { signal } = {}) {
  const res = await fetch(url, { method: 'GET', signal })
  if (!res.ok) {
    const error = new Error('文件预览读取失败')
    error.status = res.status
    throw error
  }
  return res.blob()
}

export const fileSdk = {
  statusText: FILE_STATUS_TEXT,
  normalize: normalizeFile,
  async upload(file, options = {}) {
    return normalizeFile(await uploadFile(uploadPath(options), file))
  },
  async list({ bizType, bizId }) {
    const query = new URLSearchParams({ bizType: String(bizType), bizId: String(bizId) })
    const data = await request(`/files?${query.toString()}`)
    return (data?.items || []).map(normalizeFile)
  },
  async metadata(fileId) {
    return normalizeFile(await request(`/files/${enc(fileId)}`))
  },
  async versions(fileId) {
    const data = await request(`/files/${enc(fileId)}/versions`)
    return (data?.items || []).map((item) => ({ ...item, file: normalizeFile(item.file || {}) }))
  },
  async authorizedUrl(fileId) {
    return request(`/files/${enc(fileId)}/url`)
  },
  async fetchPreviewBlob(fileId, options = {}) {
    const auth = await this.authorizedUrl(fileId)
    if (auth?.delivery === 'COS_PRESIGNED' && /^https:\/\//i.test(auth.url || '')) {
      return fetchPresignedBlob(auth.url, options)
    }
    return this.fetchPreviewBlobFrom(auth, options)
  },
  async fetchPreviewBlobFrom(ticket, options = {}) {
    const path = typeof ticket === 'string' ? ticket : authorizedPath(ticket)
    if (!path || !String(path).startsWith('/')) throw new Error('服务端未返回有效文件预览授权路径')
    return fetchFileBlob(path, options)
  },
  async fetchPeerPreviewBlob(peerId, fileId, options = {}) {
    if (!peerId || !fileId) throw new Error('互查任务或文件标识缺失')
    return fetchFileBlob(`/mobile/graduation/peer/${enc(peerId)}/files/${enc(fileId)}/preview`, options)
  },
  async download(fileId, fileName = '附件') {
    return downloadFile(`/files/download/${enc(fileId)}`, fileName)
  },
  async downloadFrom(ticket, fileName = '附件') {
    const path = typeof ticket === 'string' ? ticket : authorizedPath(ticket)
    if (!path || !String(path).startsWith('/')) throw new Error('服务端未返回有效文件授权路径')
    return downloadFile(path, fileName)
  },
  async preview(fileId, _fileName = '附件', options = {}) {
    return this.fetchPreviewBlob(fileId, options)
  },
  async previewFrom(ticket, _fileName = '附件', options = {}) {
    return this.fetchPreviewBlobFrom(ticket, options)
  }
}

export default fileSdk
