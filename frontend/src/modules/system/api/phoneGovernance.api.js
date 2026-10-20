import { request } from '@/services/http/client'

export const phoneGovernanceApi = {
  query: body => request('/system/phone-bindings/query', { method: 'POST', body }),
  candidate: (id, body) => request(`/system/users/${encodeURIComponent(id)}/phone-candidate`, { method: 'PUT', body }),
  preview: body => request('/system/phone-bindings/batch-preview', { method: 'POST', body }),
  confirm: body => request('/system/phone-bindings/batch-confirm', { method: 'POST', body }),
  revoke: (id, body) => request(`/system/users/${encodeURIComponent(id)}/phone-binding/revoke`, { method: 'POST', body }),
  policy: () => request('/system/phone-login-policy'),
  setPolicy: body => request('/system/phone-login-policy', { method: 'PUT', body })
}
