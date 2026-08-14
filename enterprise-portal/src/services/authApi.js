import { request, setAuthTokens, setSelectedCampaignId, setTenantCode } from './request'

const ROOT='/internship/enterprise-portal'

function captureAuth(data,tenantCode,campaignId=''){
  setAuthTokens(data||{})
  setTenantCode(tenantCode)
  if(campaignId)setSelectedCampaignId(campaignId)
  return data
}

export const enterpriseAuthApi={
  login: async ({tenantCode,loginName,password,memberId}) => {
    const data=await request(`${ROOT}/auth/login`,{method:'POST',auth:false,body:{tenantCode,loginName,password,...(memberId?{memberId}:{})}})
    if(!data?.accessToken)throw new Error('企业登录响应缺少 accessToken')
    return captureAuth(data,tenantCode)
  },
  inspectInvite: ({tenantCode,token}) => request(`${ROOT}/auth/invite/inspect`,{method:'POST',auth:false,body:{tenantCode,token}}),
  acceptInvite: async ({tenantCode,token,phone,password,campaignId}) => {
    const data=await request(`${ROOT}/auth/invite/accept`,{method:'POST',auth:false,body:{tenantCode,token,phone,password}})
    if(!data?.accessToken)throw new Error('企业邀请激活响应缺少 accessToken')
    return captureAuth(data,tenantCode,campaignId)
  },
}
