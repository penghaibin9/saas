import { request } from './request'

function query(values) {
  const parts = Object.entries(values || {})
    .filter(([, value]) => value != null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

export const internshipComplianceApi = {
  compliance: (operation = 'ONBOARD', batchId = '') =>
    request(`/portal/internship/compliance${query({ operation, batchId })}`),
  consents: (batchId = '') => request(`/portal/internship/consents${query({ batchId })}`),
  consentDetail: (id) => request(`/portal/internship/consents/${encodeURIComponent(id)}`),
  consentView: (id) => request(`/portal/internship/consents/${encodeURIComponent(id)}/view`, { method: 'POST' }),
  consentConfirm: (id, body) => request(`/portal/internship/consents/${encodeURIComponent(id)}/confirm`, { method: 'POST', body }),
  consentReject: (id, body) => request(`/portal/internship/consents/${encodeURIComponent(id)}/reject`, { method: 'POST', body }),
  safetyCourses: (batchId = '') => request(`/portal/internship/safety/courses${query({ batchId })}`),
  safetyCompletions: (batchId = '') => request(`/portal/internship/safety/completions${query({ batchId })}`),
  safetyDetail: (id) => request(`/portal/internship/safety/courses/${encodeURIComponent(id)}/detail`),
  safetyStart: (id) => request(`/portal/internship/safety/courses/${encodeURIComponent(id)}/start`, { method: 'POST' }),
  safetySubmit: (id, body) => request(`/portal/internship/safety/courses/${encodeURIComponent(id)}/submit`, { method: 'POST', body }),
  safetyCommit: (id, body) => request(`/portal/internship/safety/completions/${encodeURIComponent(id)}/commit`, { method: 'POST', body })
}

export default internshipComplianceApi
