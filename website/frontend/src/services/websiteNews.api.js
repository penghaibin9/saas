import { request, requestUpload, requestBlob } from '@/services/http/client'
const root = '/manage/news'
export const websiteNewsApi = {
  categories: () => request(`${root}/categories`),
  products: () => request(`${root}/products`),
  overview: () => request(`${root}/overview`),
  articles: params => request(`${root}/articles`, { params:Object.fromEntries(Object.entries(params).filter(([,value])=>value!==''&&value!=null)) }),
  audits: params => request(`${root}/audit`, { params }),
  action: (id, action, body) => request(`${root}/articles/${encodeURIComponent(id)}/${action === 'submit' ? 'submit' : 'actions/' + action}`, { method:'POST', body }),
  revision: (id, body) => request(`${root}/articles/${encodeURIComponent(id)}/revisions`, { method:'POST', body }),
  restore: (id, body) => request(`${root}/articles/${encodeURIComponent(id)}/restore`, { method:'POST', body }),
  media: (id, file, params) => requestUpload(`${root}/articles/${encodeURIComponent(id)}/media?${new URLSearchParams(params)}`, file, 'file'),
  cover: (id, body) => request(`${root}/articles/${encodeURIComponent(id)}/cover`, { method:'POST', body }),
  create: body => request(`${root}/drafts`, { method: 'POST', body }),
  edit: (id, body) => request(`${root}/articles/${encodeURIComponent(id)}`, { method: 'PUT', body }),
  format: () => request(`${root}/package-format`),
  list: (page = 1) => request(`${root}/packages`, { params: { page }, forceProbe: true }),
  upload: file => requestUpload(`${root}/packages`, file, 'file', { timeoutMs: 90000 }),
  detail: (id, page = 1) => request(`${root}/packages/${encodeURIComponent(id)}`, { params: { page }, forceProbe: true }),
  article: (id, revisionId) => request(`${root}/articles/${encodeURIComponent(id)}`, { params:revisionId ? {revisionId} : undefined }),
  confirm: (id, body) => request(`${root}/packages/${encodeURIComponent(id)}/confirm`, { method: 'POST', body, timeoutMs: 60000 }),
  control: (id, body) => request(`${root}/packages/${encodeURIComponent(id)}/control`, { method: 'POST', body }),
  withdraw: (id, body) => request(`${root}/articles/${encodeURIComponent(id)}/withdraw`, { method: 'POST', body }),
  ledger: id => requestBlob(`${root}/packages/${encodeURIComponent(id)}/ledger.xlsx`)
}
