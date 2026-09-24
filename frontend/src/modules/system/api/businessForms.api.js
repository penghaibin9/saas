import { request } from '@/services/http/client'

const enc = encodeURIComponent
const query = (params = {}) => {
  const values = Object.entries(params).filter(([, value]) => value !== '' && value != null)
  return values.length ? `?${values.map(([key, value]) => `${enc(key)}=${enc(value)}`).join('&')}` : ''
}

export const businessFormsApi = {
  definitions: (params = {}) => request(`/platform/business-forms${query(params)}`),
  createDefinition: (body) => request('/platform/business-forms', { method: 'POST', body }),
  versions: (definitionId) => request(`/platform/business-forms/${enc(definitionId)}/versions`),
  createDraft: (definitionId, body) => request(`/platform/business-forms/${enc(definitionId)}/versions`, { method: 'POST', body }),
  version: (versionId) => request(`/platform/business-form-versions/${enc(versionId)}`),
  validate: (versionId) => request(`/platform/business-form-versions/${enc(versionId)}/validate`),
  impact: (versionId) => request(`/platform/business-form-versions/${enc(versionId)}/impact`),
  publish: (versionId, body) => request(`/platform/business-form-versions/${enc(versionId)}/publish`, { method: 'POST', body }),
  disable: (versionId, body) => request(`/platform/business-form-versions/${enc(versionId)}/disable`, { method: 'POST', body }),
  evaluate: (body) => request('/platform/compliance/evaluate', { method: 'POST', body })
}

export default businessFormsApi
