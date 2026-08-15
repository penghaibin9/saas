import test from 'node:test'
import assert from 'node:assert/strict'
import { enterpriseInternshipApi } from '../src/services/enterpriseInternshipApi.js'
import { setSelectedCampaignId } from '../src/services/request.js'

function response(data){return {status:200,json:async()=>({code:0,message:'ok',data})}}

function installSessionStorage(){
  const values=new Map()
  globalThis.sessionStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,String(value)),removeItem:key=>values.delete(key)}
}

test('canonical applicant list sends only frozen filters and strips school/internal identifiers from UI DTO',async()=>{
  installSessionStorage();setSelectedCampaignId('2027')
  const calls=[];const originalFetch=globalThis.fetch
  globalThis.fetch=async(url,options={})=>{
    calls.push({url:String(url),options})
    return response({items:[{applicationId:'501',volunteerNo:1,positionId:'81',positionTitle:'机械装配技术实习生',student:{studentId:'9001',realName:'张三',studentNo:'20250001',collegeName:'智能制造学院',majorName:'机械制造及自动化',grade:'2025级',className:'机制2501'},submissionVersion:2,materialSnapshotId:'991',submittedAt:'2026-08-15T09:30:00',decisionStatus:'INTERVIEW',effectStatus:'ACTIVE',decisionVersion:3}],total:1,page:2,pageSize:50})
  }
  try{
    const data=await enterpriseInternshipApi.applications({page:2,pageSize:50,decisionStatus:'INTERVIEW',keyword:'must-not-send',major:'must-not-send',grade:'must-not-send',match:'HIGH'})
    assert.equal(calls.length,1)
    const url=new URL(calls[0].url,'http://local')
    assert.equal(url.pathname,'/api/v1/internship/enterprise-portal/applications')
    assert.deepEqual([...url.searchParams.keys()].sort(),['campaignId','decisionStatus','page','pageSize'].sort())
    assert.equal(url.searchParams.get('campaignId'),'2027')
    assert.equal(url.searchParams.get('decisionStatus'),'INTERVIEW')
    assert.deepEqual(data,{items:[{applicationId:'501',name:'张三',major:'机械制造及自动化',grade:'2025级',positionName:'机械装配技术实习生',volunteerNo:1,appliedAt:'2026-08-15T09:30:00',decisionStatus:'INTERVIEW',decisionEffectStatus:'ACTIVE'}],total:1,page:2,pageSize:50})
    for(const forbidden of ['studentId','studentNo','materialSnapshotId','submissionVersion','decisionVersion','collegeName','className'])assert.equal(forbidden in data.items[0],false,forbidden)
  }finally{globalThis.fetch=originalFetch}
})

test('contact reveal and withdraw accept use the frozen dedicated POST routes',async()=>{
  installSessionStorage();setSelectedCampaignId('2027')
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
  }finally{globalThis.fetch=originalFetch}
})
