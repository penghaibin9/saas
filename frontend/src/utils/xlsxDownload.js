import { API_BASE_URL, API_PREFIX } from '@/services/http/config'
import { getToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

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

/**
 * 后端下载端点走 Authorization: Bearer 鉴权（无 Cookie/无 query token 后备通道），
 * window.open/普通跳转都带不上这个 header，只会打开一个 401 JSON 错误页——
 * 这里改成带 token 的 fetch 取 blob 再触发保存，和 base64 分支效果一致。
 * 保持 downloadXlsxFromApi 本身仍是同步、不抛异常的旧签名，失败自己弹 toast，
 * 不强迫现有 25+ 处调用方都改成 await（否则 base64 分支的同步异常也会变成
 * 未处理的 Promise rejection，波及面更大）。
 */
async function downloadAuthedUrl(url, filename) {
  try {
    const token = getToken()
    const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) {
      let msg = `下载失败（HTTP ${res.status}）`
      try {
        const body = await res.clone().json()
        if (body?.message) msg = body.message
      } catch { /* 非 JSON 响应体，保留默认文案 */ }
      throw new Error(msg)
    }
    const blob = await res.blob()
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(href)
  } catch (e) {
    toast.error(e?.message || '下载失败')
  }
}

export function downloadXlsxFromApi(payload = {}) {
  const filename = payload.filename || payload.fileName || `export-${Date.now()}.xlsx`
  if (payload.downloadUrl || payload.url) {
    downloadAuthedUrl(resolveDownloadUrl(payload.downloadUrl || payload.url), filename)
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

