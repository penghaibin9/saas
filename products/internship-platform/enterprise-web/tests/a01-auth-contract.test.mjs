import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const auth=read('../src/services/authApi.js'),api=read('../src/services/enterpriseInternshipApi.js'),request=read('../src/services/request.js'),invite=read('../src/views/InviteAcceptView.vue'),store=read('../src/stores/enterpriseContext.js'),select=read('../src/views/CampaignSelectView.vue')

test('A02 browser UI consumes A01 enterprise auth/context routes through cookie transport',()=>{
  assert.match(auth,/\/internship\/enterprise-portal/)
  for(const path of ['/auth/browser-login','/auth/invite/inspect','/auth/browser-invite/accept'])assert.match(auth,new RegExp(path.replace(/\//g,'\\/')))
  assert.match(api,/AUTH_ROOT = '\/internship\/enterprise-portal'/)
  assert.match(api,/context.*campaignId/)
})

test('A01 invite DTO uses tenantCode token phone password and never client company scope',()=>{
  for(const field of ['tenantCode','token','phone','password'])assert.match(auth,new RegExp(field))
  assert.doesNotMatch(auth,/companyId/)
  assert.match(invite,/phoneMasked/)
  assert.match(invite,/至少 8 位/)
})

test('invite activation can only lock the campaign returned by inspectInvite for the same tenant and token',()=>{
  assert.match(auth,/let validatedInvite=null/)
  assert.match(auth,/validatedInvite=\{tenantCode:inviteKey\(tenantCode\),token:inviteKey\(token\),campaignId\}/)
  assert.match(auth,/validatedInvite\.tenantCode!==tenant/)
  assert.match(auth,/validatedInvite\.token!==inviteToken/)
  assert.match(auth,/const campaignId=validatedInvite\.campaignId/)
  assert.doesNotMatch(invite,/campaignId:preview\.value/)
  assert.match(invite,/不会再次提交 campaignId 或 companyId/)
})

test('enterprise refresh uses per-tab HttpOnly browser transport without persisting bearer secrets',()=>{
  assert.match(request,/auth\/browser-refresh/)
  assert.match(request,/X-Browser-Session-Id/)
  assert.match(request,/credentials:'include'/)
  assert.match(request,/restoreEnterpriseSession/)
  assert.doesNotMatch(request,/let refreshToken/)
  assert.doesNotMatch(request,/sessionStorage\.setItem\([^\n]*(accessToken|refreshToken)/)
  assert.doesNotMatch(request,/localStorage/)
})

test('every normal login clears stale campaign selection while invite activation may lock its validated campaign',()=>{
  assert.match(auth,/setSelectedCampaignId\(campaignId\|\|''\)/)
  assert.match(auth,/return captureAuth\(data,tenantCode\)/)
  assert.match(auth,/return captureAuth\(data,tenantCode,campaignId\)/)
  assert.doesNotMatch(auth,/previousTenant/)
})

test('missing campaign or missing explicit capability stays fail closed',()=>{
  assert.match(select,/不允许选择 companyId/)
  assert.match(store,/recruitmentWrite:false/)
  assert.match(store,/recruitmentWrite===true/)
  assert.match(store,/尚未选择招聘季/)
})
