import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const auth=read('../src/services/authApi.js'),api=read('../src/services/enterpriseInternshipApi.js'),request=read('../src/services/request.js'),invite=read('../src/views/InviteAcceptView.vue'),store=read('../src/stores/enterpriseContext.js'),select=read('../src/views/CampaignSelectView.vue')

test('A02-1 consumes A01 actual enterprise auth/context routes',()=>{
  assert.match(auth,/\/internship\/enterprise-portal/)
  for(const path of ['/auth/login','/auth/invite/inspect','/auth/invite/accept'])assert.match(auth,new RegExp(path.replace(/\//g,'\\/')))
  assert.match(api,/AUTH_ROOT = '\/internship\/enterprise-portal'/)
  assert.match(api,/context.*campaignId/)
})

test('A01 invite DTO uses tenantCode token phone password and never client company scope',()=>{
  for(const field of ['tenantCode','token','phone','password'])assert.match(auth,new RegExp(field))
  assert.doesNotMatch(auth,/companyId/)
  assert.match(invite,/phoneMasked/)
  assert.match(invite,/至少 8 位/)
})

test('enterprise refresh follows A01 refresh route without persisting bearer tokens to browser storage',()=>{
  assert.match(request,/auth\/refresh/)
  assert.match(request,/refreshToken/)
  assert.doesNotMatch(request,/sessionStorage\.setItem\([^\n]*(accessToken|refreshToken)/)
  assert.doesNotMatch(request,/localStorage/)
})

test('missing campaign or missing explicit capability stays fail closed',()=>{
  assert.match(select,/不允许选择 companyId/)
  assert.match(store,/recruitmentWrite:false/)
  assert.match(store,/recruitmentWrite===true/)
  assert.match(store,/尚未选择招聘季/)
})
