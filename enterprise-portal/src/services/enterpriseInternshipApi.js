import { getSelectedCampaignId, request } from './request'
import { sanitizeCompanyPatch, sanitizePositionPayload } from './enterpriseContract'

const AUTH_ROOT = '/internship/enterprise-portal'
const ROOT = '/enterprise/internship'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])

function recruitmentParams(){
  const campaignId=getSelectedCampaignId()
  if(!campaignId)throw new Error('尚未选择招聘季，无法调用企业招聘 Authority')
  return {campaignId}
}

function normalizeMaterial(data={}){
  const snapshot=data.profileSnapshot||{}
  const profile=snapshot.profile||{}
  const items=Array.isArray(snapshot.items)?snapshot.items:[]
  const groups={skillEvidence:[],certificates:[],projects:[],practices:[],awards:[],portfolio:[]}
  const targetByType={SKILL_EVIDENCE:'skillEvidence',CERTIFICATE:'certificates',PROJECT:'projects',PRACTICE:'practices',AWARD:'awards',PORTFOLIO:'portfolio'}
  for(const item of items){
    const target=targetByType[String(item?.itemType||'').toUpperCase()]
    if(target)groups[target].push(item)
  }
  return {
    ...data,
    profile,
    schoolFacts:data.schoolFactSnapshot||{},
    skillTags:Array.isArray(profile.skillTags)?profile.skillTags:[],
    ...groups,
  }
}

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
  applicationMaterial: async (id) => normalizeMaterial(await request(`${AUTH_ROOT}/applications/${id}`, { params:recruitmentParams() })),
  resumePdf: (id) => request(`${ROOT}/applications/${id}/resume-pdf`),
  decideApplication: (id,status,payload={}) => {
    if (!DECISIONS.has(status)) throw new Error(`不允许的企业 Decision: ${status}`)
    return request(`${AUTH_ROOT}/applications/${id}/decision`, { method:'POST', params:recruitmentParams(), body:{ status, ...payload } })
  },
  revealContact: (id) => request(`${ROOT}/applications/${id}/contact-view`, { method:'POST' }),
  withdrawAccept: (id,reason) => {
    const text=String(reason||'').trim()
    if(text.length<2)throw new Error('撤回拟接收必须填写原因')
    return request(`${AUTH_ROOT}/applications/${id}/decision`, { method:'POST', params:recruitmentParams(), body:{ status:'REJECTED', reason:text } })
  },
  internshipStudents: (params) => request(`${ROOT}/students`, { params }),
  internshipStudent: (id) => request(`${ROOT}/students/${id}`),
  evaluationTasks: (params) => request(`${ROOT}/evaluation-tasks`, { params }),
  submitEvaluation: (id,payload) => request(`${ROOT}/evaluation-tasks/${id}/submit`, { method:'POST', body:payload }),
}

export const enterpriseDecisionStatuses = Object.freeze([...DECISIONS])
