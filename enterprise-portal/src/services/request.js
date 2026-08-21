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
const BROWSER_SESSION_KEY = 'ep_browser_session_id_v1'
let accessToken = ''
let refreshing = null

function sessionGet(key){ try{return sessionStorage.getItem(key)||''}catch{return ''} }
function sessionSet(key,value){ try{if(value)sessionStorage.setItem(key,String(value));else sessionStorage.removeItem(key)}catch{/* memory-only browser */} }
function newBrowserSessionId(){return globalThis.crypto?.randomUUID?.()||`enterprise-${Date.now()}-${Math.random()}`}
function browserSessionId(){
  let value=sessionGet(BROWSER_SESSION_KEY)
  if(!value){value=newBrowserSessionId();sessionSet(BROWSER_SESSION_KEY,value)}
  return value
}
function browserHeaders(){return {'X-Browser-Session':'enterprise','X-Browser-Session-Id':browserSessionId()}}

export function setAuthTokens(data={}){accessToken=String(data.accessToken||'')}
export function setAccessToken(token){accessToken=String(token||'')}
export function clearAccessToken(){accessToken=''}
export function hasEnterpriseAuth(){return Boolean(accessToken)}
export function setSelectedCampaignId(value){sessionSet(CAMPAIGN_KEY,value)}
export function getSelectedCampaignId(){return sessionGet(CAMPAIGN_KEY)}
export function setTenantCode(value){sessionSet(TENANT_CODE_KEY,value)}
export function getTenantCode(){return sessionGet(TENANT_CODE_KEY)}
function clearLocalEnterpriseSession(){
  clearAccessToken()
  setSelectedCampaignId('')
}
function revokeBrowserCookieBestEffort(){
  const token=accessToken
  try{
    void fetch(`${API_BASE}${API_PREFIX}${ENTERPRISE_AUTH_ROOT}/auth/browser-logout`,{
      method:'POST',headers:{'Content-Type':'application/json',...browserHeaders(),...(token?{Authorization:`Bearer ${token}`}:{})},credentials:'include',keepalive:true,
    }).catch(()=>{})
  }catch{/* local session clearing must never be blocked by the network */}
}
export function clearEnterpriseSession(){
  revokeBrowserCookieBestEffort()
  clearLocalEnterpriseSession()
}

async function readPayload(response){try{return await response.json()}catch{return null}}
function businessError(payload,response){
  const error=new Error(payload?.message||`业务错误 ${payload?.code??response.status}`)
  error.status=response.status;error.code=payload?.code;error.bizCode=payload?.bizCode;error.details=payload?.details
  return error
}
function authExpired(payload,response){
  return response.status===401||payload?.code===401001||payload?.bizCode==='UNAUTHORIZED'
}
function invalidateEnterpriseAuth(message='企业登录已失效，请重新登录'){
  clearLocalEnterpriseSession()
  const error=new Error(message);error.status=401;return error
}
async function refreshOnce(){
  if(refreshing)return refreshing
  refreshing=(async()=>{
    let response
    try{
      response=await fetch(`${API_BASE}${API_PREFIX}${ENTERPRISE_AUTH_ROOT}/auth/browser-refresh`,{
        method:'POST',headers:{'Content-Type':'application/json',...browserHeaders()},credentials:'include',
      })
    }catch{
      const error=new Error('网络不可达，暂时无法刷新企业登录状态');error.network=true;throw error
    }
    const payload=await readPayload(response)
    if(authExpired(payload,response))throw invalidateEnterpriseAuth(payload?.message)
    if(!payload||typeof payload.code!=='number'){
      const error=new Error(`刷新登录响应结构异常（HTTP ${response.status}）`);error.status=response.status;throw error
    }
    if(payload.code!==0)throw businessError(payload,response)
    if(!payload.data?.accessToken)throw invalidateEnterpriseAuth('刷新登录响应缺少 accessToken，请重新登录')
    setAuthTokens(payload.data)
    return accessToken
  })().finally(()=>{refreshing=null})
  return refreshing
}

export async function restoreEnterpriseSession(){
  if(accessToken)return accessToken
  return refreshOnce()
}

export async function logoutEnterpriseSession(){
  const token=accessToken
  try{
    await fetch(`${API_BASE}${API_PREFIX}${ENTERPRISE_AUTH_ROOT}/auth/browser-logout`,{
      method:'POST',headers:{'Content-Type':'application/json',...browserHeaders(),...(token?{Authorization:`Bearer ${token}`}:{})},credentials:'include',
    })
  }catch{/* local session is still cleared below */}
  clearLocalEnterpriseSession()
}

function requestSuffix(path,params){
  const query=new URLSearchParams()
  Object.entries(params||{}).forEach(([key,value])=>{
    if(value===undefined||value===null||value==='')return
    if(Array.isArray(value))value.forEach(item=>query.append(key,String(item)))
    else query.set(key,String(value))
  })
  return query.size?`${path.includes('?')?'&':'?'}${query.toString()}`:''
}

export async function request(path,{method='GET',body,params,auth=true,_retried=false}={}){
  const suffix=requestSuffix(path,params)
  const headers={'Content-Type':'application/json',...browserHeaders()}
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
  if(authExpired(payload,response)){
    if(auth&&!_retried){await refreshOnce();return request(path,{method,body,params,auth,_retried:true})}
    throw invalidateEnterpriseAuth(payload.message)
  }
  if(payload.code!==0)throw businessError(payload,response)
  return payload.data
}

function responseHeader(response,name){
  try{return String(response?.headers?.get?.(name)||'')}catch{return ''}
}
function downloadFilename(disposition){
  const utf8=String(disposition||'').match(/filename\*=UTF-8''([^;]+)/i)
  if(utf8){try{return decodeURIComponent(utf8[1])}catch{return utf8[1]}}
  const plain=String(disposition||'').match(/filename="?([^";]+)"?/i)
  return plain?plain[1]:''
}

export async function requestBinary(path,{params,auth=true,_retried=false}={}){
  const suffix=requestSuffix(path,params)
  const headers={...browserHeaders(),'Accept':'application/pdf,application/octet-stream'}
  if(auth&&accessToken)headers.Authorization=`Bearer ${accessToken}`
  let response
  try{
    response=await fetch(`${API_BASE}${API_PREFIX}${path}${suffix}`,{method:'GET',headers,credentials:'include'})
  }catch{
    const error=new Error('文件读取失败：网络不可达');error.network=true;throw error
  }
  const contentType=responseHeader(response,'content-type').toLowerCase()
  if(contentType.includes('application/json')||response.status===401||response.status>=400){
    const payload=await readPayload(response)
    if(authExpired(payload,response)){
      if(auth&&!_retried){await refreshOnce();return requestBinary(path,{params,auth,_retried:true})}
      throw invalidateEnterpriseAuth(payload?.message)
    }
    if(payload&&typeof payload.code==='number')throw businessError(payload,response)
    const error=new Error(`文件读取失败（HTTP ${response.status}）`);error.status=response.status;throw error
  }
  const blob=await response.blob()
  if(!blob||!blob.size)throw new Error('文件响应为空，请刷新后重试')
  return {
    blob,
    contentType:contentType||blob.type||'application/octet-stream',
    fileName:downloadFilename(responseHeader(response,'content-disposition')),
    snapshotHash:responseHeader(response,'x-internship-snapshot-hash'),
  }
}

export async function uploadTemporaryFile(file,{bizType='INTERNSHIP_ENTERPRISE_PROFILE',_retried=false}={}){
  if(!(file instanceof File))throw new Error('请选择要上传的文件')
  const form=new FormData()
  form.append('file',file,file.name)
  form.append('bizType',bizType)
  const headers={...browserHeaders()}
  if(accessToken)headers.Authorization=`Bearer ${accessToken}`
  let response
  try{
    response=await fetch(`${API_BASE}${API_PREFIX}/files`,{method:'POST',headers,credentials:'include',body:form})
  }catch{
    const error=new Error('文件上传失败：网络不可达');error.network=true;throw error
  }
  const payload=await readPayload(response)
  if(!payload||typeof payload.code!=='number'){
    const error=new Error(`文件上传响应结构异常（HTTP ${response.status}）`);error.status=response.status;throw error
  }
  if(authExpired(payload,response)){
    if(!_retried){await refreshOnce();return uploadTemporaryFile(file,{bizType,_retried:true})}
    throw invalidateEnterpriseAuth(payload.message)
  }
  if(payload.code!==0)throw businessError(payload,response)
  if(!payload.data?.fileId)throw new Error('文件中心未返回 fileId')
  return payload.data
}
