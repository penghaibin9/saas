import { request } from '@/services/http/client'

const school = id => `/platform/tenants/${encodeURIComponent(id)}`
const version = (id, vid) => `${school(id)}/business-form-versions/${encodeURIComponent(vid)}`
export const businessFormsControlApi = {
  schools: keyword => request('/platform/business-form-schools', { params: { keyword, limit: 30 } }),
  definitions: id => request(`${school(id)}/business-forms`),
  sources: id => request(`${school(id)}/business-form-sources`),
  versions: (id, definitionId, page = 1) => request(`${school(id)}/business-forms/${encodeURIComponent(definitionId)}/versions`, { params: { page, pageSize: 50 } }),
  preview: (id, vid) => request(version(id, vid)),
  validate: (id, vid) => request(`${version(id, vid)}/validate`),
  impact: (id, vid) => request(`${version(id, vid)}/impact`),
  publish: (id, vid, body) => request(`${version(id, vid)}/publish`, { method: 'POST', body, timeoutMs: 30000 }),
  disable: (id, vid, body) => request(`${version(id, vid)}/disable`, { method: 'POST', body, timeoutMs: 30000 })
}
