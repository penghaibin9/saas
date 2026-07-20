import { request } from '@/services/http/client'

const root = '/national-standards'

export const standardsApi = {
  stats: () => request(`${root}/stats`),
  documents: (params = {}) => request(`${root}/documents`, { params }),
  detail: (id) => request(`${root}/documents/${id}`),
  catalog: (params = {}) => request(`${root}/catalog`, { params }),
  bindings: () => request(`${root}/bindings`),
  bind: (body) => request(`${root}/bindings`, { method: 'POST', body })
}
