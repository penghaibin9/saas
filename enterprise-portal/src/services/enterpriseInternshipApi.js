import { getSelectedCampaignId, request } from './request.js'

const AUTH_ROOT = '/internship/enterprise-portal'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])

function recruitmentParams(){
  const campaignId=getSelectedCampaignId()
  if(!campaignId)throw new Error('尚未选择招聘季，无法调用企业招聘 Authority')
  return {campaignId}
}

function unavailableFacade(name){
  const error=new Error(`该企业协同能力尚未由学校端开放：${name}`)
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
  dashboard: () => unavailableFacade('招聘工作台'),
  campaigns: () => unavailableFacade('招聘季列表'),
  company: () => unavailableFacade('企业资料'),
  updateCompany: () => unavailableFacade('企业资料编辑'),
  positions: () => unavailableFacade('岗位列表'),
  position: () => unavailableFacade('岗位详情'),
  createPosition: () => unavailableFacade('新建岗位'),
  updatePosition: () => unavailableFacade('编辑岗位'),
  submitPosition: () => unavailableFacade('提交岗位审核'),
  withdrawPosition: () => unavailableFacade('撤回岗位审核'),
  applications: () => unavailableFacade('报名学生列表'),
  application: () => unavailableFacade('候选人概要'),
  applicationMaterial: async (id) => normalizeMaterial(await request(`${AUTH_ROOT}/applications/${id}`, { params:recruitmentParams() })),
  resumePdf: () => unavailableFacade('简历 PDF'),
  decideApplication: (id,status,payload={}) => {
    if (!DECISIONS.has(status)) throw new Error(`不允许的企业 Decision: ${status}`)
    return request(`${AUTH_ROOT}/applications/${id}/decision`, { method:'POST', params:recruitmentParams(), body:{ status, ...payload } })
  },
  revealContact: () => unavailableFacade('联系方式查看'),
  withdrawAccept: (id,reason) => {
    const text=String(reason||'').trim()
    if(text.length<2)throw new Error('撤回拟接收必须填写原因')
    return request(`${AUTH_ROOT}/applications/${id}/decision`, { method:'POST', params:recruitmentParams(), body:{ status:'REJECTED', reason:text } })
  },
  internshipStudents: () => unavailableFacade('实习学生列表'),
  internshipStudent: () => unavailableFacade('实习学生详情'),
  evaluationTasks: () => unavailableFacade('企业评价任务'),
  submitEvaluation: () => unavailableFacade('企业评价提交'),
}

export const enterpriseDecisionStatuses = Object.freeze([...DECISIONS])
