import { clearTokens, commitNewSessionTokens, getRefreshToken, realRequest } from './request'
import { setForcePasswordChange } from '@/security/passwordChangeGate'

const SESSION_KEY='gx_session_v1'

function normalizedIdentity(data={}) {
  const user=data.user||{}
  const role=data.currentRole||{}
  return {
    userId:user.userId||'',
    loginName:user.loginName||'',
    realName:user.realName||'',
    userType:String(user.userType||'').toUpperCase(),
    studentNo:user.studentNo||'',
    roleCode:String(role.roleCode||'').toUpperCase(),
    roleName:role.roleName||'',
    tenantId:String(data.tenantId||''),
    tenantCode:data.tenantCode||'',
    tenantName:data.tenantName||''
  }
}

export function mobileHome(identity={}) {
  const role=String(identity.roleCode||'').toUpperCase()
  const type=String(identity.userType||'').toUpperCase()
  return role==='STUDENT'||type==='STUDENT'
    ? '/pages/student-internship/index'
    : '/pages/teacher-internship/index'
}

export function currentMobileSession() {
  try {
    const raw=uni.getStorageSync(SESSION_KEY)
    return raw&&typeof raw==='object'?raw:{}
  } catch (e) { return {} }
}

export async function loginMobile({tenantCode='',loginName='',password='',clientType='STUDENT_MINI'}={}) {
  const data=await realRequest('/auth/login',{
    method:'POST',auth:false,
    data:{tenantCode:tenantCode||undefined,loginName,password,clientType}
  })
  commitNewSessionTokens(data.accessToken||'',data.refreshToken||'')
  const identity=normalizedIdentity(data)
  const isTeacher=identity.userType!=='STUDENT'&&identity.roleCode!=='STUDENT'
  const session={logged:true,isTeacher,identity}
  try { uni.setStorageSync(SESSION_KEY,session) } catch (e) {}
  setForcePasswordChange(!!data.mustChangePassword)
  return {data,identity,home:mobileHome(identity)}
}

export async function logoutMobile() {
  const refreshToken=getRefreshToken()
  try {
    await realRequest('/auth/logout',{
      method:'POST',
      auth:false,
      data:refreshToken?{refreshToken}:{}
    })
  } catch (e) {
    // Local logout must still complete if the network is unavailable.
  }
  clearTokens()
  setForcePasswordChange(false)
  try {
    uni.removeStorageSync(SESSION_KEY)
    uni.removeStorageSync('gx_internship_context_v1')
    uni.removeStorageSync('gx_student_internship_batch_v1')
  } catch (e) {}
  return true
}
