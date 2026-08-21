export const PREVIEW_SESSION_STATE = Object.freeze({
  IDLE: 'IDLE',
  FETCHING: 'FETCHING',
  READY: 'READY',
  ERROR: 'ERROR',
  UNSUPPORTED: 'UNSUPPORTED',
  DESTROYED: 'DESTROYED'
})

export const PREVIEW_KIND = Object.freeze({ PDF: 'PDF', IMAGE: 'IMAGE', UNSUPPORTED: 'UNSUPPORTED' })

const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'])

export function inferPreviewKind(descriptor = {}) {
  const explicit = String(descriptor.previewKind || '').toUpperCase()
  if (explicit === PREVIEW_KIND.PDF || explicit === PREVIEW_KIND.IMAGE) return explicit
  const mime = String(descriptor.mimeType || '').toLowerCase()
  const ext = String(descriptor.ext || descriptor.fileName || '').split('.').pop().toLowerCase()
  if (mime === 'application/pdf' || ext === 'pdf') return PREVIEW_KIND.PDF
  if (mime.startsWith('image/') || IMAGE_EXT.has(ext)) return PREVIEW_KIND.IMAGE
  return PREVIEW_KIND.UNSUPPORTED
}

export function previewIdentity(descriptor = {}) {
  return [
    descriptor.fileId ?? '',
    descriptor.fileVersionId ?? descriptor.versionId ?? '',
    descriptor.sourceSha256 ?? descriptor.sha256 ?? ''
  ].map(String).join(':')
}

export function normalizePreviewDescriptor(input = {}) {
  const allowedActions = Array.isArray(input.allowedActions) ? input.allowedActions : []
  return Object.freeze({
    ...input,
    fileId: input.fileId == null ? null : String(input.fileId),
    fileVersionId: input.fileVersionId ?? input.versionId ?? null,
    sourceSha256: input.sourceSha256 || input.sha256 || '',
    previewKind: inferPreviewKind(input),
    allowedActions,
    canPreview: input.canPreview !== false && (allowedActions.length === 0 || allowedActions.includes('preview')),
    canDownload: input.canDownload === true || allowedActions.includes('download')
  })
}

export function isTicketExpiredError(error) {
  const code = String(error?.bizCode || error?.code || '').toUpperCase()
  return ['PREVIEW_TICKET_EXPIRED', 'FILE_TICKET_EXPIRED', 'TICKET_EXPIRED'].includes(code)
}

export function normalizePreviewError(error) {
  if (error?.name === 'AbortError' || error?.code === 'PREVIEW_ABORTED') {
    return { code: 'PREVIEW_ABORTED', message: '预览已切换', retryable: false }
  }
  const code = String(error?.bizCode || error?.code || 'PREVIEW_FAILED')
  return {
    code,
    message: error?.message || '文件预览失败，请重试',
    retryable: !['NO_PERMISSION', 'FILE_INFECTED', 'PREVIEW_UNSUPPORTED'].includes(code)
  }
}

export function buildPreviewDescriptorFromFile(file = {}) {
  return normalizePreviewDescriptor({
    ...file,
    fileVersionId: file.fileVersionId ?? file.versionId ?? null,
    sourceSha256: file.sourceSha256 || file.sha256 || '',
    versionNo: file.versionNo ?? null
  })
}
