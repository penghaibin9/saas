export const PREVIEW_SESSION_STATE = Object.freeze({
  IDLE: 'IDLE',
  FETCHING: 'FETCHING',
  READY: 'READY',
  ERROR: 'ERROR',
  UNSUPPORTED: 'UNSUPPORTED',
  DESTROYED: 'DESTROYED'
})

export const PREVIEW_KIND = Object.freeze({ PDF: 'PDF', IMAGE: 'IMAGE', DOCX: 'DOCX', UNSUPPORTED: 'UNSUPPORTED' })
export const DOCX_PREVIEW_MAX_SOURCE_BYTES = 25 * 1024 * 1024
export const PDF_PREVIEW_MAX_SOURCE_BYTES = 50 * 1024 * 1024
export const PDF_PREVIEW_MAX_PAGES = 500
export const PDF_PREVIEW_MAX_CANVAS_PIXELS = 12_000_000
export const PDF_PREVIEW_MAX_CANVAS_DIMENSION = 16384
export const IMAGE_PREVIEW_MAX_SOURCE_BYTES = 20 * 1024 * 1024
export const IMAGE_PREVIEW_MAX_PIXELS = 32_000_000
export const DOCX_PREVIEW_MAX_IMAGE_PIXELS = 16_000_000
export const DOCX_PREVIEW_MAX_TOTAL_IMAGE_PIXELS = 32_000_000

const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'])
const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export function inferPreviewKind(descriptor = {}) {
  const explicit = String(descriptor.preview?.kind || descriptor.previewKind || '').toUpperCase()
  if ([PREVIEW_KIND.PDF, PREVIEW_KIND.IMAGE, PREVIEW_KIND.DOCX].includes(explicit)) return explicit
  const mime = String(descriptor.mimeType || '').toLowerCase()
  const ext = String(descriptor.ext || descriptor.fileName || '').split('.').pop().toLowerCase()
  if (mime === 'application/pdf' || ext === 'pdf') return PREVIEW_KIND.PDF
  if (mime.startsWith('image/') || IMAGE_EXT.has(ext)) return PREVIEW_KIND.IMAGE
  if (mime === DOCX_MIME || ext === 'docx') return PREVIEW_KIND.DOCX
  return PREVIEW_KIND.UNSUPPORTED
}

export function previewSourceByteLimit(descriptor = {}) {
  const kind = typeof descriptor === 'string' ? descriptor : inferPreviewKind(descriptor)
  if (kind === PREVIEW_KIND.DOCX) return DOCX_PREVIEW_MAX_SOURCE_BYTES
  if (kind === PREVIEW_KIND.PDF) return PDF_PREVIEW_MAX_SOURCE_BYTES
  if (kind === PREVIEW_KIND.IMAGE) return IMAGE_PREVIEW_MAX_SOURCE_BYTES
  return 0
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
  const previewKind = inferPreviewKind(input)
  const preview = Object.freeze({
    ...(input.preview || {}),
    kind: previewKind
  })
  return Object.freeze({
    ...input,
    fileId: input.fileId == null ? null : String(input.fileId),
    fileVersionId: input.fileVersionId ?? input.versionId ?? null,
    sourceSha256: input.sourceSha256 || input.sha256 || '',
    preview,
    previewKind,
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
    retryable: ![
      'NO_PERMISSION', 'FILE_INFECTED', 'PREVIEW_UNSUPPORTED', 'PREVIEW_UNSUPPORTED_TYPE',
      'PREVIEW_TOO_LARGE', 'PREVIEW_TOO_COMPLEX', 'PREVIEW_IMAGE_MALFORMED', 'PREVIEW_DOCX_MALFORMED', 'PREVIEW_DOCX_TOO_COMPLEX',
      'PREVIEW_DOCX_DECOMPRESSION_UNSUPPORTED'
    ].includes(code)
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
