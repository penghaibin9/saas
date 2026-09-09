import { request, requestUpload, requestBlob } from '@/services/http/client'
const root = '/platform/website-news'
export const websiteNewsApi = {
  format: () => request(`${root}/package-format`),
  list: (page = 1) => request(`${root}/packages`, { params: { page }, forceProbe: true }),
  upload: file => requestUpload(`${root}/packages`, file, 'file', { timeoutMs: 90000 }),
  detail: (id, page = 1) => request(`${root}/packages/${encodeURIComponent(id)}`, { params: { page }, forceProbe: true }),
  article: id => request(`${root}/articles/${encodeURIComponent(id)}`, { forceProbe: true }),
  confirm: (id, body) => request(`${root}/packages/${encodeURIComponent(id)}/confirm`, { method: 'POST', body, timeoutMs: 60000 }),
  control: (id, body) => request(`${root}/packages/${encodeURIComponent(id)}/control`, { method: 'POST', body }),
  withdraw: id => request(`${root}/articles/${encodeURIComponent(id)}/withdraw`, { method: 'POST', body: {} }),
  ledger: id => requestBlob(`${root}/packages/${encodeURIComponent(id)}/ledger.xlsx`)
}
