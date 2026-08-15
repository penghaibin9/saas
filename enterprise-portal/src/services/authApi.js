import { request, setAuthTokens, setSelectedCampaignId, setTenantCode } from './request'

const ROOT='/internship/enterprise-portal'
let validatedInvite=null

function captureAuth(data,tenantCode,campaignId=''){
  setAuthTokens(data||{})
  setTenantCode(tenantCode)
  // 普通登录必须清掉上一次企业成员/招聘季选择；只有同一 tenantCode + token
  // 刚刚由 A01 inspectInvite 校验出的 campaignId 才能在邀请激活后锁定。
  setSelectedCampaignId(campaignId||'')
  return data
}

function inviteKey(value){return String(value||'')}

export const enterpriseAuthApi={
  login: async ({tenantCode,loginName,password,memberId}) => {
    validatedInvite=null
    const data=await request(`${ROOT}/auth/login`,{method:'POST',auth:false,body:{tenantCode,loginName,password,...(memberId?{memberId}:{})}})
    if(!data?.accessToken)throw new Error('企业登录响应缺少 accessToken')
    return captureAuth(data,tenantCode)
  },
  inspectInvite: async ({tenantCode,token}) => {
    validatedInvite=null
    const data=await request(`${ROOT}/auth/invite/inspect`,{method:'POST',auth:false,body:{tenantCode,token}})
    const campaignId=inviteKey(data?.campaignId)
    if(!campaignId)throw new Error('企业邀请校验响应缺少 campaignId')
    validatedInvite={tenantCode:inviteKey(tenantCode),token:inviteKey(token),campaignId}
    return data
  },
  acceptInvite: async ({tenantCode,token,phone,password}) => {
    const tenant=inviteKey(tenantCode),inviteToken=inviteKey(token)
    if(!validatedInvite||validatedInvite.tenantCode!==tenant||validatedInvite.token!==inviteToken){
      throw new Error('请先重新校验当前企业邀请后再接受')
    }
    const campaignId=validatedInvite.campaignId
    const data=await request(`${ROOT}/auth/invite/accept`,{method:'POST',auth:false,body:{tenantCode,token,phone,password}})
    if(!data?.accessToken)throw new Error('企业邀请激活响应缺少 accessToken')
    validatedInvite=null
    return captureAuth(data,tenantCode,campaignId)
  },
}
