import { request, requestBlob, requestUpload } from '@/services/http/client'

const BASE = '/academic-affairs'
export const classroomCatalogApi = {
  buildings(params = {}) { return request(`${BASE}/classroom-buildings`, { params }) },
  saveBuilding(body, id) { return request(`${BASE}/classroom-buildings${id ? `/${id}` : ''}`, { method: id ? 'PUT' : 'POST', body }) },
  generate(body) { return request(`${BASE}/classroom-batches/generate-preview`, { method: 'POST', body }) },
  preview(rows) { return request(`${BASE}/classroom-batches/preview`, { method: 'POST', body: { rows } }) },
  upload(file) { return requestUpload(`${BASE}/classroom-batches/import-preview`, file) },
  batch(id) { return request(`${BASE}/classroom-batches/${encodeURIComponent(id)}`) },
  confirm(id) { return request(`${BASE}/classroom-batches/${encodeURIComponent(id)}/confirm`, { method: 'POST' }) },
  template() { return requestBlob(`${BASE}/classroom-batches/template.xlsx`) },
  result(id) { return requestBlob(`${BASE}/classroom-batches/${encodeURIComponent(id)}/result.xlsx`) }
}

export function downloadClassroomFile(result, name) {
  const blob = result instanceof Blob ? result : result.blob
  if (!(blob instanceof Blob)) throw new Error('下载结果不是有效文件，请重试')
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
