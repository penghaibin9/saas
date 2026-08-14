import { request } from './request'
import { sanitizeCompanyPatch, sanitizePositionPayload } from './enterpriseContract'

const AUTH_ROOT = '/internship/enterprise-portal'
const ROOT = '/enterprise/internship'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])

export const enterpriseInternshipApi = {
  context: (campaignId) => request(`${AUTH_ROOT}/context`, { params:{ campaignId } }),
  dashboard: () => request(`${ROOT}/dashboard`),
  campaigns: () => request(`${ROOT}/campaigns`),
  company: () => request(`${ROOT}/company`),
  updateCompany: (patch) => request(`${ROOT}/company`, { method:'PUT', body:sanitizeCompanyPatch(patch) }),
  positions: (params) => request(`${ROOT}/positions`, { params }),
  position: (id) => request(`${ROOT}/positions/${id}`),
  createPosition: (payload) => request(`${ROOT}/positions`, { method:'POST', body:sanitizePositionPayload(payload) }),
  updatePosition: (id,payload) => request(`${ROOT}/positions/${id}`, { method:'PUT', body:sanitizePositionPayload(payload) }),
  submitPosition: (id) => request(`${ROOT}/positions/${id}/submit`, { method:'POST' }),
  withdrawPosition: (id) => request(`${ROOT}/positions/${id}/withdraw`, { method:'POST' }),
  applications: (params) => request(`${ROOT}/applications`, { params }),
  application: (id) => request(`${ROOT}/applications/${id}`),
  applicationMaterial: (id) => request(`${ROOT}/applications/${id}/material`),
  resumePdf: (id) => request(`${ROOT}/applications/${id}/resume-pdf`),
  decideApplication: (id,status,payload={}) => {
    if (!DECISIONS.has(status)) throw new Error(`不允许的企业 Decision: ${status}`)
    return request(`${ROOT}/applications/${id}/decision`, { method:'POST', body:{ status, ...payload } })
  },
  revealContact: (id) => request(`${ROOT}/applications/${id}/contact-view`, { method:'POST' }),
  withdrawAccept: (id) => request(`${ROOT}/applications/${id}/withdraw-accept`, { method:'POST' }),
  internshipStudents: (params) => request(`${ROOT}/students`, { params }),
  internshipStudent: (id) => request(`${ROOT}/students/${id}`),
  evaluationTasks: (params) => request(`${ROOT}/evaluation-tasks`, { params }),
  submitEvaluation: (id,payload) => request(`${ROOT}/evaluation-tasks/${id}/submit`, { method:'POST', body:payload }),
}

export const enterpriseDecisionStatuses = Object.freeze([...DECISIONS])
