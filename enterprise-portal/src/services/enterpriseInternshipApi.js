import { request } from './request'

// E-A02 只消费 A01 canonical facade；企业范围由服务端推导，学校特权动作不在此客户端暴露。
const ROOT = '/enterprise/internship'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])

export const enterpriseInternshipApi = {
  context: () => request(`${ROOT}/context`),
  dashboard: () => request(`${ROOT}/dashboard`),
  campaignHistory: () => request(`${ROOT}/campaigns/history`),
  company: () => request(`${ROOT}/company`),
  updateCompany: (patch) => request(`${ROOT}/company`, { method:'PUT', body:patch }),
  positions: (params) => request(`${ROOT}/positions`, { params }),
  position: (id) => request(`${ROOT}/positions/${id}`),
  createPosition: (payload) => request(`${ROOT}/positions`, { method:'POST', body:payload }),
  updatePosition: (id,payload) => request(`${ROOT}/positions/${id}`, { method:'PUT', body:payload }),
  submitPosition: (id) => request(`${ROOT}/positions/${id}/submit`, { method:'POST' }),
  withdrawPosition: (id) => request(`${ROOT}/positions/${id}/withdraw`, { method:'POST' }),
  applications: (params) => request(`${ROOT}/applications`, { params }),
  application: (id) => request(`${ROOT}/applications/${id}`),
  decideApplication: (id,status,payload={}) => {
    if (!DECISIONS.has(status)) throw new Error(`不允许的企业 Decision: ${status}`)
    return request(`${ROOT}/applications/${id}/decision`, { method:'POST', body:{ status, ...payload } })
  },
  revealContact: (id) => request(`${ROOT}/applications/${id}/contact-view`, { method:'POST' }),
  withdrawAccept: (id) => request(`${ROOT}/applications/${id}/withdraw-accept`, { method:'POST' }),
  internshipStudents: (params) => request(`${ROOT}/students`, { params }),
  evaluationTasks: (params) => request(`${ROOT}/evaluations`, { params }),
  evaluationTask: (id) => request(`${ROOT}/evaluations/${id}`),
  submitEvaluation: (id,payload) => request(`${ROOT}/evaluations/${id}/submit`, { method:'POST', body:payload }),
}

export const enterpriseDecisionStatuses = Object.freeze([...DECISIONS])
