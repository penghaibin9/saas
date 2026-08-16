import test from 'node:test'
import assert from 'node:assert/strict'
import { enterpriseInternshipApi, setEnterpriseApiContext } from '../src/services/enterpriseInternshipApi.js'
import { clearEnterpriseSession, setAuthTokens, setSelectedCampaignId } from '../src/services/request.js'

function installSessionStorage(){
  const values=new Map()
  globalThis.sessionStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,String(value)),removeItem:key=>values.delete(key)}
}

test('resume PDF uses canonical owned-application binary route with enterprise bearer auth', async () => {
  installSessionStorage();setSelectedCampaignId('2027');setEnterpriseApiContext('RECRUITMENT',0);setAuthTokens({accessToken:'enterprise-access',refreshToken:'enterprise-refresh'})
  const originalFetch=globalThis.fetch
  const calls=[]
  globalThis.fetch=async(url,options={})=>{
    calls.push({url:String(url),options})
    const values=new Map([
      ['content-type','application/pdf'],
      ['content-disposition','inline; filename="internship-application-snapshot-991-v2.pdf"'],
      ['x-internship-snapshot-hash','abc123'],
    ])
    return {
      status:200,
      headers:{get:name=>values.get(String(name).toLowerCase())||''},
      blob:async()=>new Blob(['%PDF-1.4\nresume'],{type:'application/pdf'}),
    }
  }
  try{
    const result=await enterpriseInternshipApi.resumePdf('501')
    assert.equal(calls.length,1)
    const url=new URL(calls[0].url,'http://local')
    assert.equal(url.pathname,'/api/v1/internship/enterprise-portal/applications/501/resume-pdf')
    assert.equal(url.searchParams.get('campaignId'),'2027')
    assert.equal(calls[0].options.method,'GET')
    assert.equal(calls[0].options.headers.Authorization,'Bearer enterprise-access')
    assert.equal(calls[0].options.headers.Accept,'application/pdf,application/octet-stream')
    assert.equal(result.blob.type,'application/pdf')
    assert.equal(result.fileName,'internship-application-snapshot-991-v2.pdf')
    assert.equal(result.snapshotHash,'abc123')
  }finally{
    globalThis.fetch=originalFetch;clearEnterpriseSession();setEnterpriseApiContext('NONE',0)
  }
})

test('resume PDF remains synchronously fail-closed outside recruitment context without network access', () => {
  installSessionStorage();setSelectedCampaignId('2027');setEnterpriseApiContext('NONE',0)
  const originalFetch=globalThis.fetch
  let calls=0;globalThis.fetch=async()=>{calls+=1;throw new Error('network must not be reached')}
  try{
    assert.throws(
      ()=>enterpriseInternshipApi.resumePdf('501'),
      error=>error?.code==='ENTERPRISE_RECRUITMENT_CONTEXT_UNAVAILABLE',
    )
    assert.equal(calls,0)
  }finally{globalThis.fetch=originalFetch;clearEnterpriseSession();setEnterpriseApiContext('NONE',0)}
})
