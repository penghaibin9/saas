import { getSelectedCampaignId, request } from './request'

const AUTH_ROOT = '/internship/enterprise-portal'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])

function recruitmentParams(){
  const campaignId=getSelectedCampaignId()
  if(!campaignId)throw new Error('尚未选择招聘季，无法调用企业招聘 Authority')
  return {campaignId}
}

function unavailableFacade(name){
  const error=new Error(`企业协同接口尚未由 A01 Authority 冻结：${name}`)
  error.code='ENTERPRISE_FACADE_UNFROZEN'
  error.facade=name
  return Promise.reject(error)
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
  dashboard: () => unavailableFacade('Campaign dashboard'),
  campaigns: () => unavailableFacade('Campaign list'),
  company: () => unavailableFacade('Company detail'),
  updateCompany: () => unavailableFacade('Company update'),
  positions: () => unavailableFacade('Position list'),
  position: () => unavailableFacade('Position detail'),
  createPosition: () => unavailableFacade('Position create'),
  updatePosition: () => unavailableFacade('Position update'),
  submitPosition: () => unavailableFacade('Position submit'),
  withdrawPosition: () => unavailableFacade('Position withdraw'),
  applications: () => unavailableFacade('Application list'),
  application: () => unavailableFacade('Application candidate summary'),
  applicationMaterial: async (id) => normalizeMaterial(await request(`${AUTH_ROOT}/applications/${id}`, { params:recruitmentParams() })),
  resumePdf: () => unavailableFacade('Application resume PDF'),
  decideApplication: (id,status,payload={}) => {
    if (!DECISIONS.has(status)) throw new Error(`不允许的企业 Decision: ${status}`)
    return request(`${AUTH_ROOT}/applications/${id}/decision`, { method:'POST', params:recruitmentParams(), body:{ status, ...payload } })
  },
  revealContact: () => unavailableFacade('Application contact reveal'),
  withdrawAccept: (id,reason) => {
    const text=String(reason||'').trim()
    if(text.length<2)throw new Error('撤回拟接收必须填写原因')
    return request(`${AUTH_ROOT}/applications/${id}/decision`, { method:'POST', params:recruitmentParams(), body:{ status:'REJECTED', reason:text } })
  },
  internshipStudents: () => unavailableFacade('InternshipRecord enterprise projection'),
  internshipStudent: () => unavailableFacade('InternshipRecord detail'),
  evaluationTasks: () => unavailableFacade('Enterprise evaluation task list'),
  submitEvaluation: () => unavailableFacade('Enterprise evaluation submit'),
}

export const enterpriseDecisionStatuses = Object.freeze([...DECISIONS])
