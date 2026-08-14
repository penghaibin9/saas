import { request, setAccessToken } from './request'

const ROOT='/enterprise/internship'

export const enterpriseAuthApi={
  login: async ({schoolCode,loginName,password}) => {
    const data=await request(`${ROOT}/auth/login`,{method:'POST',auth:false,body:{schoolCode,loginName,password}})
    if(!data?.accessToken) throw new Error('企业登录响应缺少 accessToken')
    setAccessToken(data.accessToken)
    return data
  },
  invitePreview: (token) => request(`${ROOT}/invite/preview`,{auth:false,params:{token}}),
  acceptInvite: async ({token,identity,password}) => {
    const data=await request(`${ROOT}/invite/accept`,{method:'POST',auth:false,body:{token,identity,password}})
    if(data?.accessToken) setAccessToken(data.accessToken)
    return data
  },
}
