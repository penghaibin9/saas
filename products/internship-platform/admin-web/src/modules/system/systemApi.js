import { request, requestBlob, requestUpload } from '@/services/http/client'
export const get = (path, params) => request(`/system${path}`, { params })
export const save = (path, body, method = 'POST') => request(`/system${path}`, { method, body })
export const upload = (kind, file) => requestUpload(`/system/identity-import/${kind}/preview`, file, 'file', { timeoutMs: 120000 })
export async function download(path, name, params) {
  const blob = await requestBlob(`/system${path}`, { params })
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
