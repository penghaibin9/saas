import { API_BASE_URL, API_PREFIX } from '@/services/http/config'

function base64ToBlob(contentBase64, mediaType) {
  const raw = atob(contentBase64 || '')
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i)
  return new Blob([bytes], {
    type: mediaType || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
}

function resolveDownloadUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/')) return `${API_BASE_URL}${url}`
  return `${API_BASE_URL}${API_PREFIX}${url.startsWith('/') ? url : `/${url}`}`
}

export function downloadXlsxFromApi(payload = {}) {
  const filename = payload.filename || payload.fileName || `export-${Date.now()}.xlsx`
  if (payload.downloadUrl || payload.url) {
    window.open(resolveDownloadUrl(payload.downloadUrl || payload.url), '_blank')
    return
  }
  const blob = base64ToBlob(payload.contentBase64, payload.mediaType)
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(href)
}

export default downloadXlsxFromApi

