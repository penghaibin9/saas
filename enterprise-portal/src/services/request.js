const API_BASE = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return ''
})()
const API_PREFIX = '/api/v1'
const ENTERPRISE_AUTH_ROOT = '/internship/enterprise-portal'
const CAMPAIGN_KEY = 'ep_campaign_id_v1'
const TENANT_CODE_KEY = 'ep_tenant_code_v1'
let accessToken = ''
let refreshToken = ''
let refreshing = null

function sessionGet(key){ try{return sessionStorage.getItem(key)||''}catch{return ''} }
function sessionSet(key,value){ try{if(value)sessionStorage.setItem(key,String(value));else sessionStorage.removeItem(key)}catch{/* memory-only browser */} }

export function setAuthTokens(data={}){
  accessToken=String(data.accessToken||'')
  refreshToken=String(data.refreshToken||'')
}
export function setAccessToken(token){ accessToken=String(token||'') }
export function clearAccessToken(){ accessToken='';refreshToken='' }
export function setSelectedCampaignId(value){ sessionSet(CAMPAIGN_KEY,value) }
export function getSelectedCampaignId(){ return sessionGet(CAMPAIGN_KEY) }
export function setTenantCode(value){ sessionSet(TENANT_CODE_KEY,value) }
export function getTenantCode(){ return sessionGet(TENANT_CODE_KEY) }

async function readPayload(response){ try{return await response.json()}catch{return null} }
async function refreshOnce(){
  if(refreshing)return refreshing
  if(!refreshToken)throw Object.assign(new Error('企业登录已失效，请重新登录'),{status:401})
  refreshing=(async()=>{
    const response=await fetch(`${API_BASE}${API_PREFIX}${ENTERPRISE_AUTH_ROOT}/auth/refresh`,{
      method:'POST',headers:{'Content-Type':'application/json','X-Browser-Session':'enterprise'},credentials:'include',body:JSON.stringify({refreshToken}),
    })
    const payload=await readPayload(response)
    if(!payload||payload.code!==0||!payload.data?.accessToken)throw Object.assign(new Error(payload?.message||'企业登录已失效，请重新登录'),{status:401})
    setAuthTokens(payload.data)
    return accessToken
  })().finally(()=>{refreshing=null})
  return refreshing
}

export async function request(path,{method='GET',body,params,auth=true,_retried=false}={}){
  const query=new URLSearchParams()
  Object.entries(params||{}).forEach(([key,value])=>{
    if(value===undefined||value===null||value==='')return
    if(Array.isArray(value))value.forEach(item=>query.append(key,String(item)))
    else query.set(key,String(value))
  })
  const suffix=query.size?`${path.includes('?')?'&':'?'}${query.toString()}`:''
  const headers={'Content-Type':'application/json','X-Browser-Session':'enterprise'}
  if(auth&&accessToken)headers.Authorization=`Bearer ${accessToken}`
  let response
  try{
    response=await fetch(`${API_BASE}${API_PREFIX}${path}${suffix}`,{method,headers,credentials:'include',body:body===undefined?undefined:JSON.stringify(body)})
  }catch{
    const error=new Error('网络不可达，请检查企业协同后端服务');error.network=true;throw error
  }
  const payload=await readPayload(response)
  if(!payload||typeof payload.code!=='number'){
    const error=new Error(`响应结构异常（HTTP ${response.status}）`);error.status=response.status;throw error
  }
  if(response.status===401||payload.code===401001){
    if(auth&&!_retried&&refreshToken){await refreshOnce();return request(path,{method,body,params,auth,_retried:true})}
    clearAccessToken()
    const error=new Error(payload.message||'企业登录已失效，请重新登录');error.status=401;throw error
  }
  if(payload.code!==0){
    const error=new Error(payload.message||`业务错误 ${payload.code}`);error.status=response.status;error.code=payload.code;error.bizCode=payload.bizCode;error.details=payload.details;throw error
  }
  return payload.data
}
