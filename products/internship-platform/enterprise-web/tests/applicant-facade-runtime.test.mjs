import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, reactive, ref } from 'vue'
import { importEnterpriseRuntime } from './helpers/import-vite-runtime.mjs'

const { apiModule, requestModule } = await importEnterpriseRuntime()
const { enterpriseInternshipApi, setEnterpriseApiContext } = apiModule
const { setSelectedCampaignId } = requestModule

test('企业角色和状态输出中文，截止显示保留同一时间且未知值不泄露代码',()=>{
  const {enterpriseRoleLabel,enterpriseCampaignStatusLabel,formatEnterpriseDateTime}=apiModule
  assert.deepEqual(['COMPANY_ADMIN','HR','MENTOR','UNKNOWN_ROLE'].map(enterpriseRoleLabel),['企业管理员','招聘对接人','企业导师','企业成员'])
  assert.deepEqual(['DRAFT','OPEN','FROZEN','CLOSED','ARCHIVED','UNKNOWN_STATUS'].map(enterpriseCampaignStatusLabel),['筹备中','进行中','已冻结','已结束','已归档','状态待核对'])
  assert.equal(formatEnterpriseDateTime('2026-10-05T19:06:22Z'),formatEnterpriseDateTime('2026-10-06T03:06:22+08:00'))
  assert.equal(formatEnterpriseDateTime(null),'—');assert.equal(formatEnterpriseDateTime('UNKNOWN_TIME'),'时间待确认')
})

function response(data){return {status:200,json:async()=>({code:0,message:'ok',data})}}

function installSessionStorage(){
  const values=new Map()
  globalThis.sessionStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,String(value)),removeItem:key=>values.delete(key)}
}

function controller(path, props, api, exports){
  const script=parse(fs.readFileSync(new URL(path,import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')
  return new Function('computed','ref','watch','onMounted','defineProps','defineEmits','nextTick','enterpriseInternshipApi',script+`\nreturn {${exports}}`)(computed,ref,()=>{},()=>{},()=>props,()=>()=>{},fn=>fn(),api)
}

test('direct confirmed applicant detail preserves authority, Chinese history and bounded history page',async()=>{
  installSessionStorage();setSelectedCampaignId('2027');setEnterpriseApiContext('RECRUITMENT',0)
  const originalFetch=globalThis.fetch;let url
  globalThis.fetch=async input=>{url=new URL(input,'http://local');return response({applicationId:'501',volunteerNo:1,submittedAt:'2026-10-05T19:05:30Z',applicationStatus:'APPROVED',groupStatus:'APPROVED',decisionStatus:'ACCEPT_INTENT',effectStatus:'CONSUMED',allowedDecisionActions:[],decisionDisabledReason:'学校已确认岗位，企业处理已结束',decisionHistory:[{id:'8',status:'ACCEPT_INTENT',effectStatus:'CONSUMED',submissionVersion:2,decidedAt:'2026-10-05T19:06:22Z'}],decisionHistoryTotal:25,decisionHistoryPage:2,decisionHistoryPageSize:20,schoolFactSnapshot:{realName:'合成学生'},profileSnapshot:{profile:{selfIntro:'本次冻结介绍'}}})}
  try{
    const payload=await enterpriseInternshipApi.applicationMaterial('501',2)
    assert.equal(url.searchParams.get('historyPage'),'2');assert.equal(url.searchParams.get('campaignId'),'2027')
    assert.equal(payload.decisionEffectStatus,'CONSUMED');assert.deepEqual(payload.allowedDecisionActions,[])
    assert.equal(payload.decisionHistory[0].statusLabel,'拟接收');assert.equal(payload.decisionHistory[0].effectLabel,'已用于学校确认')
    const props=reactive({applicationId:'501',summary:{applicationId:'501',decisionStatus:'INTERVIEW',decisionEffectStatus:'ACTIVE',appliedAt:'old'},campaignWritable:true})
    const vm=controller('../src/views/ApplicantDetailView.vue',props,{applicationMaterial:async()=>payload},'data,material,load,schoolConfirmed')
    await vm.load(2)
    assert.equal(vm.schoolConfirmed.value,true);assert.equal(vm.data.value.volunteerNo,1)
    assert.equal(vm.data.value.appliedAt,payload.submittedAt);assert.equal(vm.data.value.decisionEffectStatus,'CONSUMED')
    assert.equal(vm.data.value.decisionHistoryPage,2);assert.equal(vm.data.value.decisionHistoryTotal,25)
    props.summary=null;await vm.load();assert.equal(vm.data.value.decisionHistory.length,1)
  }finally{globalThis.fetch=originalFetch;setEnterpriseApiContext('NONE',0)}
})

test('late applicant detail cannot overwrite another object or leave cleared selection loading',async()=>{
  let resolveOld;const old=new Promise(resolve=>{resolveOld=resolve})
  const props=reactive({applicationId:'501',summary:null,campaignWritable:true})
  const vm=controller('../src/views/ApplicantDetailView.vue',props,{applicationMaterial:id=>id==='501'?old:Promise.resolve({applicationId:id,schoolFacts:{realName:'下一位学生'},allowedDecisionActions:[]})},'data,material,loading,error,load')
  const first=vm.load();props.applicationId='502';await vm.load()
  resolveOld({applicationId:'501',schoolFacts:{realName:'前一位学生'}});await first
  assert.equal(vm.data.value.applicationId,'502');assert.equal(vm.data.value.name,'下一位学生')
  props.applicationId='';await vm.load();assert.equal(vm.data.value,null);assert.equal(vm.loading.value,false)
})

test('enterprise decisions default deny missing contracts and confirmed applicants',async()=>{
  const writes=[];const props=reactive({application:{applicationId:'501',decisionStatus:'ACCEPT_INTENT',decisionEffectStatus:'CONSUMED',allowedDecisionActions:[],decisionDisabledReason:'学校已确认岗位，企业处理已结束'},campaignWritable:true})
  const vm=controller('../src/components/applicant/DecisionActions.vue',props,{decideApplication:async(...args)=>writes.push(args)},'availableActions,baseDisabled,requestDecision,decide,error')
  assert.equal(vm.baseDisabled.value,true);assert.equal(vm.availableActions.value.length,0)
  vm.requestDecision('ACCEPT_INTENT');await vm.decide('REJECTED');assert.equal(writes.length,0)
  props.application={applicationId:'502'};await vm.decide('INTERESTED')
  assert.equal(vm.baseDisabled.value,true);assert.equal(writes.length,0);assert.match(vm.error.value,/尚未允许/)
})

test('existing safety withdrawal follows the server action contract even in a frozen campaign',async()=>{
  const writes=[];const props=reactive({application:{applicationId:'501',decisionStatus:'ACCEPT_INTENT',decisionEffectStatus:'ACTIVE',allowedDecisionActions:['REJECTED']},campaignWritable:false})
  const vm=controller('../src/components/applicant/DecisionActions.vue',props,{withdrawAccept:async(...args)=>writes.push(args)},'requestWithdrawAccept,withdrawAccept,confirming,withdrawReason')
  vm.requestWithdrawAccept();assert.equal(vm.confirming.value,'WITHDRAW_ACCEPT')
  vm.withdrawReason.value='合成岗位计划调整';await vm.withdrawAccept()
  assert.deepEqual(writes,[['501','合成岗位计划调整']])
})

test('canonical applicant list sends only frozen filters and strips school/internal identifiers from UI DTO',async()=>{
  installSessionStorage();setSelectedCampaignId('2027');setEnterpriseApiContext('RECRUITMENT',0)
  const calls=[];const originalFetch=globalThis.fetch
  globalThis.fetch=async(url,options={})=>{
    calls.push({url:String(url),options})
    return response({items:[{applicationId:'501',volunteerNo:1,positionId:'81',positionTitle:'机械装配技术实习生',student:{studentId:'9001',realName:'张三',studentNo:'20250001',collegeName:'智能制造学院',majorName:'机械制造及自动化',grade:'2025级',className:'机制2501'},submissionVersion:2,materialSnapshotId:'991',submittedAt:'2026-08-15T09:30:00',decisionStatus:'INTERVIEW',effectStatus:'ACTIVE',decisionVersion:3}],total:1,page:2,pageSize:50})
  }
  try{
    const data=await enterpriseInternshipApi.applications({page:2,pageSize:50,decisionStatus:'INTERVIEW',keyword:'测试岗位',major:'must-not-send',grade:'must-not-send',match:'HIGH'})
    assert.equal(calls.length,1)
    const url=new URL(calls[0].url,'http://local')
    assert.equal(url.pathname,'/api/v1/internship/enterprise-portal/applications')
    assert.deepEqual([...url.searchParams.keys()].sort(),['campaignId','decisionStatus','keyword','page','pageSize'].sort())
    assert.equal(url.searchParams.get('campaignId'),'2027')
    assert.equal(url.searchParams.get('decisionStatus'),'INTERVIEW');assert.equal(url.searchParams.get('keyword'),'测试岗位')
    assert.deepEqual(data,{items:[{applicationId:'501',name:'张三',major:'机械制造及自动化',grade:'2025级',positionName:'机械装配技术实习生',volunteerNo:1,appliedAt:'2026-08-15T09:30:00',decisionStatus:'INTERVIEW',decisionEffectStatus:'ACTIVE'}],total:1,page:2,pageSize:50})
    for(const forbidden of ['studentId','studentNo','materialSnapshotId','submissionVersion','decisionVersion','collegeName','className'])assert.equal(forbidden in data.items[0],false,forbidden)
  }finally{globalThis.fetch=originalFetch;setEnterpriseApiContext('NONE',0)}
})

test('contact reveal and withdraw accept use the frozen dedicated POST routes',async()=>{
  installSessionStorage();setSelectedCampaignId('2027');setEnterpriseApiContext('RECRUITMENT',0)
  const calls=[];const originalFetch=globalThis.fetch
  globalThis.fetch=async(url,options={})=>{
    calls.push({url:String(url),options})
    if(String(url).includes('/contact-view'))return response({applicationId:'501',contactMode:'IMMEDIATE',phone:'13800138000'})
    return response({applicationId:'501',decisionStatus:'REJECTED',effectStatus:'SUPERSEDED',version:4})
  }
  try{
    const contact=await enterpriseInternshipApi.revealContact('501')
    assert.equal(contact.phone,'13800138000')
    await enterpriseInternshipApi.withdrawAccept('501','岗位计划调整')
    assert.equal(calls.length,2)
    assert.match(calls[0].url,/\/applications\/501\/contact-view\?campaignId=2027$/)
    assert.equal(calls[0].options.method,'POST')
    assert.match(calls[1].url,/\/applications\/501\/withdraw-accept\?campaignId=2027$/)
    assert.equal(calls[1].options.method,'POST')
    assert.deepEqual(JSON.parse(calls[1].options.body),{reason:'岗位计划调整'})
  }finally{globalThis.fetch=originalFetch;setEnterpriseApiContext('NONE',0)}
})

test('internship collaboration preserves large batch ids without JavaScript precision loss',async()=>{
  installSessionStorage()
  const batchId='9007199254740993'
  setEnterpriseApiContext('COLLABORATION',batchId)
  const calls=[];const originalFetch=globalThis.fetch
  globalThis.fetch=async(url)=>{calls.push(String(url));return response({items:[],total:0,page:1,pageSize:50})}
  try{
    await enterpriseInternshipApi.internshipStudents()
    assert.equal(calls.length,1)
    const url=new URL(calls[0],'http://local')
    assert.equal(url.searchParams.get('batchId'),batchId)
  }finally{globalThis.fetch=originalFetch;setEnterpriseApiContext('NONE',0)}
})
