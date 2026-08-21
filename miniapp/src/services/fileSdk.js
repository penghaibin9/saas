import { realDownload, realRequest, realUpload } from './request'

export const FILE_STATUS_TEXT = Object.freeze({
  NOT_REQUIRED: '无需扫描',
  PENDING: '等待安全扫描',
  RUNNING: '正在安全扫描',
  CLEAN: '安全可用',
  INFECTED: '检测到风险，已拒绝',
  ERROR: '安全扫描失败'
})

const enc = encodeURIComponent
const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp'])
const DOCUMENT_EXTENSIONS = new Set(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'])

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

export function previewIdentity(file = {}) {
  const fileId = String(file.fileId || file.id || '').trim()
  const fileVersionId = String(file.fileVersionId || file.versionId || '').trim()
  const sourceSha = String(file.sourceSha256 || file.sourceSha || file.sha256 || '').trim()
  return [fileId, fileVersionId, sourceSha].join(':')
}

export function chooseSingleFile({ count = 1 } = {}) {
  return new Promise((resolve, reject) => {
    if (typeof uni.chooseMessageFile === 'function') {
      uni.chooseMessageFile({
        count,
        type: 'file',
        success: (res) => resolve((res.tempFiles || [])[0] || null),
        fail: reject
      })
      return
    }
    uni.chooseImage({
      count,
      sizeType: ['compressed', 'original'],
      success: (res) => resolve({
        path: (res.tempFilePaths || [])[0],
        name: 'attachment.jpg',
        size: (res.tempFiles || [])[0]?.size || 0
      }),
      fail: reject
    })
  })
}

function fileExtension(fileName) {
  const name = String(fileName || '').toLowerCase()
  const index = name.lastIndexOf('.')
  return index >= 0 ? name.slice(index + 1) : ''
}

function nativePreviewKind(fileName = '') {
  const ext = fileExtension(fileName)
  if (IMAGE_EXTENSIONS.has(ext)) return 'image'
  if (!ext || DOCUMENT_EXTENSIONS.has(ext)) return 'document'
  return 'unsupported'
}

function assertNativePreviewSupported(fileName = '') {
  const kind = nativePreviewKind(fileName)
  if (kind === 'unsupported') {
    throw {
      code: 'PREVIEW_UNSUPPORTED',
      biz: true,
      message: '当前文件类型不支持小程序内预览，请使用 PC 端查看或下载'
    }
  }
  return kind
}

function openDownloaded(downloaded, fileName = '', { strictNative = false } = {}) {
  const ext = fileExtension(fileName)
  const detected = nativePreviewKind(fileName)
  const kind = strictNative ? assertNativePreviewSupported(fileName) : detected
  return new Promise((resolve, reject) => {
    if (kind === 'image') {
      uni.previewImage({ urls: [downloaded.tempFilePath], current: downloaded.tempFilePath, success: resolve, fail: reject })
      return
    }
    uni.openDocument({
      filePath: downloaded.tempFilePath, fileType: ext || undefined, showMenu: true,
      success: resolve,
      fail: (error) => reject({ code: 'PREVIEW_FAILED', biz: true, message: error?.errMsg || '当前文件无法预览，请在 PC 端查看' })
    })
  })
}

export async function openBusinessFile(fileId) {
  const id = String(fileId || '').trim()
  if (!id) throw { code: 'FILE_REQUIRED', biz: true, message: '附件不存在' }
  const meta = normalizeFile(await realRequest(`/files/${enc(id)}`))
  if (!meta.canPreview && !meta.canDownload) {
    throw { code: 404001, biz: true, message: '附件不存在或尚未通过安全扫描' }
  }
  const downloaded = await realDownload(`/files/download/${enc(id)}`)
  await openDownloaded(downloaded, meta.fileName)
  return meta
}

export const fileSdk = {
  statusText: FILE_STATUS_TEXT,
  normalize: normalizeFile,
  identity: previewIdentity,
  choose: chooseSingleFile,
  async upload(file, options = {}) {
    const filePath = file?.path || file?.tempFilePath
    if (!filePath) throw { code: 'FILE_REQUIRED', biz: true, message: '请选择要上传的文件' }
    return normalizeFile(await realUpload('/files', filePath, {
      name: 'file',
      formData: {
        bizType: String(options.bizType || 'ATTACHMENT'),
        bizId: String(options.bizId || '')
      }
    }))
  },
  async openAuthorized({
    fileId,
    fileVersionId = '',
    sourceSha = '',
    ticketPath,
    openPath,
    action = 'preview',
    fileName = ''
  }) {
    const id = String(fileId || '').trim()
    if (!id) throw { code: 'FILE_REQUIRED', biz: true, message: '附件不存在' }
    const nativeKind = assertNativePreviewSupported(fileName)
    const descriptor = {
      fileId: id,
      fileVersionId: String(fileVersionId || ''),
      sourceSha: String(sourceSha || ''),
      action,
      surface: 'MINIAPP',
      nativeKind
    }
    descriptor.identity = previewIdentity(descriptor)

    const ticket = await realRequest(ticketPath, { method: 'POST', data: { action } })
    const raw = encodeURIComponent(String(ticket?.ticket || ''))
    if (!raw) throw { code: 'PREVIEW_TICKET_MISSING', biz: true, message: '文件票据不存在或已失效' }
    const downloaded = await realDownload(`${openPath}?ticket=${raw}`)
    await openDownloaded(downloaded, fileName, { strictNative: true })
    return {
      ...ticket,
      previewDescriptor: descriptor,
      telemetry: {
        event: 'document_preview_return',
        surface: 'MINIAPP',
        action,
        identity: descriptor.identity,
        nativeKind
      }
    }
  },
  async list({ bizType, bizId }) {
    const data = await realRequest(`/files?bizType=${enc(bizType)}&bizId=${enc(bizId)}`)
    return (data?.items || []).map(normalizeFile)
  },
  async metadata(fileId) {
    return normalizeFile(await realRequest(`/files/${enc(fileId)}`))
  },
  async versions(fileId) {
    const data = await realRequest(`/files/${enc(fileId)}/versions`)
    return (data?.items || []).map((item) => ({ ...item, file: normalizeFile(item.file || {}) }))
  },
  async open(fileId) {
    return openBusinessFile(fileId)
  },
  async download(fileId) {
    return realDownload(`/files/download/${enc(fileId)}`)
  }
}

export default fileSdk
