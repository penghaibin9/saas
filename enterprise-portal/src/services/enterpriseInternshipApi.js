import { getSelectedCampaignId, request, requestBinary } from './request.js'
import { sanitizeCompanyPatch, sanitizePositionPayload } from './enterpriseContract.js'

const AUTH_ROOT = '/internship/enterprise-portal'
const DECISIONS = new Set(['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED'])
let activeContextMode='NONE'
let activeCollaborationBatchId=0

export function setEnterpriseApiContext(mode='NONE',batchId=0){
  activeContextMode=String(mode||'NONE').toUpperCase()
  activeCollaborationBatchId=Number(batchId)||0
}

function recruitmentParams(){
  const campaignId=getSelectedCampaignId()
  if(!campaignId)throw new Error('尚未选择经学校校验的招聘季，无法读取或处理招聘数据')
  return {campaignId}
}
function requireRecruitmentAccess(){
  if(activeContextMode!=='RECRUITMENT'){
    const error=new Error('招聘访问已结束，系统不会使用实习协同授权读取或处理招聘数据')
    error.code='ENTERPRISE_RECRUITMENT_CONTEXT_UNAVAILABLE'
    throw error
  }
  return recruitmentParams()
}
function collaborationParams(batchId){
  const value=Number(batchId||activeCollaborationBatchId)
  if(!Number.isInteger(value)||value<=0)throw new Error('当前实习协同批次不可用，请重新进入学校已开放的协同批次')
  return {batchId:value}
}
function requireVersion(value,label='数据'){
  if(value===null||value===undefined||value===''||!Number.isInteger(Number(value))||Number(value)<0)throw new Error(`${label}版本缺失，请刷新后重试`)
  return Number(value)
}
function normalizeMaterial(data={}){
  const snapshot=data.profileSnapshot||{},profile=snapshot.profile||{},items=Array.isArray(snapshot.items)?snapshot.items:[]
  const groups={skillEvidence:[],certificates:[],projects:[],practices:[],awards:[],portfolio:[]}
  const targetByType={SKILL_EVIDENCE:'skillEvidence',CERTIFICATE:'certificates',PROJECT:'projects',PRACTICE:'practices',AWARD:'awards',PORTFOLIO:'portfolio'}
  for(const item of items){const target=targetByType[String(item?.itemType||'').toUpperCase()];if(target)groups[target].push(item)}
  return {...data,profile,schoolFacts:data.schoolFactSnapshot||{},skillTags:Array.isArray(profile.skillTags)?profile.skillTags:[],...groups}
}
function normalizeApplicantSummary(row={}){
  const student=row.student||{}
  return {applicationId:row.applicationId,name:student.realName||'学生',major:student.majorName||'',grade:student.grade||'',positionName:row.positionTitle||'',volunteerNo:row.volunteerNo,appliedAt:row.submittedAt||null,decisionStatus:row.decisionStatus||'PENDING',decisionEffectStatus:row.effectStatus||null}
}
function normalizeApplicantPage(data={}){return {items:(Array.isArray(data.items)?data.items:[]).map(normalizeApplicantSummary),total:Number.isFinite(Number(data.total))?Number(data.total):0,page:Number.isFinite(Number(data.page))?Number(data.page):1,pageSize:Number.isFinite(Number(data.pageSize))?Number(data.pageSize):20}}
function evaluationPayload(payload={}){
  const result={attendanceScore:Number(payload.attendanceScore),skillScore:Number(payload.skillScore),attitudeScore:Number(payload.attitudeScore),collaborationScore:Number(payload.collaborationScore),safetyScore:Number(payload.safetyScore),overallComment:String(payload.overallComment||'').trim(),recommendHire:Boolean(payload.recommendHire)}
  if(payload.expectedVersion!==null&&payload.expectedVersion!==undefined&&payload.expectedVersion!=='')result.expectedVersion=requireVersion(payload.expectedVersion,'企业评价')
  return result
}
async function fetchApplicationMaterial(id){return normalizeMaterial(await request(`${AUTH_ROOT}/applications/${id}`,{params:requireRecruitmentAccess()}))}

export const enterpriseInternshipApi={
  context:(campaignId)=>request(`${AUTH_ROOT}/context`,{params:{campaignId}}),
  collaborationContext:(batchId)=>request(`${AUTH_ROOT}/collaboration-context`,{params:collaborationParams(batchId)}),
  dashboard:()=>request(`${AUTH_ROOT}/dashboard`,{params:requireRecruitmentAccess()}),
  campaigns:()=>request(`${AUTH_ROOT}/campaigns`),
  company:()=>request(`${AUTH_ROOT}/company`),
  updateCompany:(payload={})=>request(`${AUTH_ROOT}/company`,{method:'PUT',body:{...sanitizeCompanyPatch(payload),expectedVersion:requireVersion(payload.expectedVersion,'企业资料')}}),
  positions:({page=1,pageSize=20,status='',keyword=''}={})=>request(`${AUTH_ROOT}/positions`,{params:{...requireRecruitmentAccess(),page,pageSize,status,keyword}}),
  position:(id)=>request(`${AUTH_ROOT}/positions/${id}`,{params:requireRecruitmentAccess()}),
  createPosition:(payload={})=>request(`${AUTH_ROOT}/positions`,{method:'POST',params:requireRecruitmentAccess(),body:sanitizePositionPayload(payload)}),
  updatePosition:(id,payload={})=>request(`${AUTH_ROOT}/positions/${id}`,{method:'PUT',params:requireRecruitmentAccess(),body:{...sanitizePositionPayload(payload),expectedVersion:requireVersion(payload.expectedVersion,'岗位')}}),
  submitPosition:(id,expectedVersion)=>request(`${AUTH_ROOT}/positions/${id}/submit`,{method:'POST',params:requireRecruitmentAccess(),body:{expectedVersion:requireVersion(expectedVersion,'岗位')}}),
  withdrawPosition:(id,expectedVersion)=>request(`${AUTH_ROOT}/positions/${id}/withdraw`,{method:'POST',params:requireRecruitmentAccess(),body:{expectedVersion:requireVersion(expectedVersion,'岗位')}}),
  applications:async({page=1,pageSize=50,decisionStatus='',positionId=''}={})=>normalizeApplicantPage(await request(`${AUTH_ROOT}/applications`,{params:{...requireRecruitmentAccess(),page,pageSize,decisionStatus,positionId}})),
  applicationMaterial:fetchApplicationMaterial,
  resumePdf:(id)=>requestBinary(`${AUTH_ROOT}/applications/${id}/resume-pdf`,{params:requireRecruitmentAccess()}),
  decideApplication:(id,status,payload={})=>{if(!DECISIONS.has(status))throw new Error(`不允许的企业 Decision: ${status}`);return request(`${AUTH_ROOT}/applications/${id}/decision`,{method:'POST',params:requireRecruitmentAccess(),body:{status,...payload}})},
  revealContact:(id)=>request(`${AUTH_ROOT}/applications/${id}/contact-view`,{method:'POST',params:requireRecruitmentAccess()}),
  withdrawAccept:(id,reason)=>{const text=String(reason||'').trim();if(text.length<2)throw new Error('撤回拟接收必须填写原因');return request(`${AUTH_ROOT}/applications/${id}/withdraw-accept`,{method:'POST',params:requireRecruitmentAccess(),body:{reason:text}})},
  internshipStudents:({batchId,page=1,pageSize=50,status='',keyword=''}={})=>request(`${AUTH_ROOT}/internship-students`,{params:{...collaborationParams(batchId),page,pageSize,status,keyword}}),
  internshipStudent:(id,batchId)=>request(`${AUTH_ROOT}/internship-students/${id}`,{params:collaborationParams(batchId)}),
  evaluationTasks:({batchId,status='',page=1,pageSize=50}={})=>request(`${AUTH_ROOT}/evaluation-tasks`,{params:{...collaborationParams(batchId),status,page,pageSize}}),
  submitEvaluation:(id,payload={},batchId)=>request(`${AUTH_ROOT}/evaluation-tasks/${id}/submit`,{method:'POST',params:collaborationParams(batchId),body:evaluationPayload(payload)}),
}
export const enterpriseDecisionStatuses=Object.freeze([...DECISIONS])
