import { getSelectedCampaignId, request } from './request.js'
import { sanitizeCompanyPatch, sanitizePositionPayload } from './enterpriseContract.js'

const AUTH_ROOT = '/internship/enterprise-portal'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])

function recruitmentParams(){
  const campaignId=getSelectedCampaignId()
  if(!campaignId)throw new Error('尚未选择经学校校验的招聘季，无法读取或处理招聘数据')
  return {campaignId}
}

function unavailableFacade(name){
  const error=new Error(`该企业协同能力尚未由学校端开放：${name}`)
  error.code='ENTERPRISE_FACADE_UNFROZEN'
  error.facade=name
  return Promise.reject(error)
}

function requireVersion(value,label='数据'){
  if(value===null||value===undefined||value===''||!Number.isInteger(Number(value))||Number(value)<0)throw new Error(`${label}版本缺失，请刷新后重试`)
  return Number(value)
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

function normalizeApplicantSummary(row={}){
  const student=row.student||{}
  return {
    applicationId:row.applicationId,
    name:student.realName||'学生',
    major:student.majorName||'',
    grade:student.grade||'',
    positionName:row.positionTitle||'',
    volunteerNo:row.volunteerNo,
    appliedAt:row.submittedAt||null,
    decisionStatus:row.decisionStatus||'PENDING',
    decisionEffectStatus:row.effectStatus||null,
  }
}

function normalizeApplicantPage(data={}){
  return {
    items:(Array.isArray(data.items)?data.items:[]).map(normalizeApplicantSummary),
    total:Number.isFinite(Number(data.total))?Number(data.total):0,
    page:Number.isFinite(Number(data.page))?Number(data.page):1,
    pageSize:Number.isFinite(Number(data.pageSize))?Number(data.pageSize):20,
  }
}

async function fetchApplicationMaterial(id){
  return normalizeMaterial(await request(`${AUTH_ROOT}/applications/${id}`, { params:recruitmentParams() }))
}

export const enterpriseInternshipApi = {
  context: (campaignId) => request(`${AUTH_ROOT}/context`, { params:{ campaignId } }),
  dashboard: () => request(`${AUTH_ROOT}/dashboard`, { params:recruitmentParams() }),
  campaigns: () => request(`${AUTH_ROOT}/campaigns`),
  company: () => request(`${AUTH_ROOT}/company`),
  updateCompany: (payload={}) => request(`${AUTH_ROOT}/company`, {
    method:'PUT',
    body:{...sanitizeCompanyPatch(payload),expectedVersion:requireVersion(payload.expectedVersion,'企业资料')},
  }),
  positions: ({page=1,pageSize=20,status='',keyword=''}={}) => request(`${AUTH_ROOT}/positions`, {
    params:{...recruitmentParams(),page,pageSize,status,keyword},
  }),
  position: (id) => request(`${AUTH_ROOT}/positions/${id}`, { params:recruitmentParams() }),
  createPosition: (payload={}) => request(`${AUTH_ROOT}/positions`, {
    method:'POST',params:recruitmentParams(),body:sanitizePositionPayload(payload),
  }),
  updatePosition: (id,payload={}) => request(`${AUTH_ROOT}/positions/${id}`, {
    method:'PUT',params:recruitmentParams(),body:{...sanitizePositionPayload(payload),expectedVersion:requireVersion(payload.expectedVersion,'岗位')},
  }),
  submitPosition: (id,expectedVersion) => request(`${AUTH_ROOT}/positions/${id}/submit`, {
    method:'POST',params:recruitmentParams(),body:{expectedVersion:requireVersion(expectedVersion,'岗位')},
  }),
  withdrawPosition: (id,expectedVersion) => request(`${AUTH_ROOT}/positions/${id}/withdraw`, {
    method:'POST',params:recruitmentParams(),body:{expectedVersion:requireVersion(expectedVersion,'岗位')},
  }),
  applications: async ({page=1,pageSize=50,decisionStatus='',positionId=''}={}) => normalizeApplicantPage(await request(`${AUTH_ROOT}/applications`, {
    params:{...recruitmentParams(),page,pageSize,decisionStatus,positionId},
  })),
  applicationMaterial: fetchApplicationMaterial,
  resumePdf: () => unavailableFacade('简历 PDF'),
  decideApplication: (id,status,payload={}) => {
    if (!DECISIONS.has(status)) throw new Error(`不允许的企业 Decision: ${status}`)
    return request(`${AUTH_ROOT}/applications/${id}/decision`, { method:'POST', params:recruitmentParams(), body:{ status, ...payload } })
  },
  revealContact: (id) => request(`${AUTH_ROOT}/applications/${id}/contact-view`, { method:'POST', params:recruitmentParams() }),
  withdrawAccept: (id,reason) => {
    const text=String(reason||'').trim()
    if(text.length<2)throw new Error('撤回拟接收必须填写原因')
    return request(`${AUTH_ROOT}/applications/${id}/withdraw-accept`, { method:'POST', params:recruitmentParams(), body:{ reason:text } })
  },
  internshipStudents: () => unavailableFacade('实习学生列表'),
  internshipStudent: () => unavailableFacade('实习学生详情'),
  evaluationTasks: () => unavailableFacade('企业评价任务'),
  submitEvaluation: () => unavailableFacade('企业评价提交'),
}

export const enterpriseDecisionStatuses = Object.freeze([...DECISIONS])
