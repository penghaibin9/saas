import { request } from './request'

// E-A02 只消费 A01 canonical facade；企业范围由服务端推导，学校特权动作不在此客户端暴露。
const ROOT = '/enterprise/internship'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])
const COMPANY_EDITABLE = new Set(['logoFileId','coverFileId','shortName','shortIntro','website','mainBusiness','establishedYear','address'])
const POSITION_EDITABLE = new Set([
  'title','category','majorRequirement','gradeRequirement','workLocation','headcount','mentorContactId',
  'workContent','workAddress','dailyHours','weeklyHours','shiftType','nightShift','overtimeAllowed','restDaysPerWeek',
  'remunerationType','remunerationAmount','remunerationCycle','salaryRange','subsidy','accommodationProvided','mealProvided',
  'hazardousFlag','specialEquipment','prohibitedReason','remark',
])

function editablePayload(source, allowed) {
  const result = {}
  for (const [key,value] of Object.entries(source || {})) {
    if (allowed.has(key) && value !== undefined) result[key] = value
  }
  return result
}

export const enterpriseInternshipApi = {
  context: () => request(`${ROOT}/context`),
  dashboard: () => request(`${ROOT}/dashboard`),
  campaigns: () => request(`${ROOT}/campaigns`),
  company: () => request(`${ROOT}/company`),
  updateCompany: (patch) => request(`${ROOT}/company`, { method:'PUT', body:editablePayload(patch, COMPANY_EDITABLE) }),
  positions: (params) => request(`${ROOT}/positions`, { params }),
  position: (id) => request(`${ROOT}/positions/${id}`),
  createPosition: (payload) => request(`${ROOT}/positions`, { method:'POST', body:editablePayload(payload, POSITION_EDITABLE) }),
  updatePosition: (id,payload) => request(`${ROOT}/positions/${id}`, { method:'PUT', body:editablePayload(payload, POSITION_EDITABLE) }),
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
  evaluationTask: (id) => request(`${ROOT}/evaluation-tasks/${id}`),
  submitEvaluation: (id,payload) => request(`${ROOT}/evaluation-tasks/${id}/submit`, { method:'POST', body:payload }),
}

export const enterpriseDecisionStatuses = Object.freeze([...DECISIONS])
