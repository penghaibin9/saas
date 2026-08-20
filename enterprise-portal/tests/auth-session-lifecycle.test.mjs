import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const request=fs.readFileSync(new URL('../src/services/request.js',import.meta.url),'utf8')
const layout=fs.readFileSync(new URL('../src/layouts/EnterprisePortalLayout.vue',import.meta.url),'utf8')
const router=fs.readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8')
const auth=fs.readFileSync(new URL('../src/services/authApi.js',import.meta.url),'utf8')
const browser=fs.readFileSync(new URL('../e2e/applicant-workbench.spec.mjs',import.meta.url),'utf8')

test('expired browser refresh invalidates only local memory state and stale campaign',()=>{
  assert.match(request,/function invalidateEnterpriseAuth/)
  assert.match(request,/clearLocalEnterpriseSession\(\)/)
  assert.match(request,/setSelectedCampaignId\(''\)/)
  assert.match(request,/authExpired\(payload,response\)/)
  assert.match(request,/if\(refreshing\)return refreshing/)
})

test('temporary refresh network failure does not deliberately clear enterprise auth state',()=>{
  const refreshBody=request.match(/async function refreshOnce\(\)[\s\S]*?\n}\n\nexport async function restoreEnterpriseSession/)?.[0]||''
  assert.match(refreshBody,/网络不可达，暂时无法刷新企业登录状态/)
  const networkBlock=refreshBody.match(/catch\{[\s\S]*?error\.network=true;throw error\n    }/)?.[0]||''
  assert.doesNotMatch(networkBlock,/clearEnterpriseSession|clearLocalEnterpriseSession|clearAccessToken|setSelectedCampaignId/)
})

test('enterprise portal explicit logout revokes browser cookie and clears Pinia context',()=>{
  assert.match(request,/auth\/browser-logout/)
  assert.match(request,/keepalive:true/)
  assert.match(layout,/clearEnterpriseSession\(\)/)
  assert.match(layout,/context\.\$reset\(\)/)
  assert.match(layout,/router\.replace\('\/login'\)/)
  assert.match(layout,/>退出<\/button>/)
})

test('protected enterprise routes restore HttpOnly browser session before redirecting to login',()=>{
  assert.match(request,/export function hasEnterpriseAuth/)
  assert.match(request,/export async function restoreEnterpriseSession/)
  assert.match(router,/router\.beforeEach\(async to=>/)
  assert.match(router,/await restoreEnterpriseSession\(\)/)
  assert.match(router,/if\(hasEnterpriseAuth\(\)\)return true/)
  assert.match(router,/path:'\/login'/)
  assert.match(router,/session-required/)
})

test('browser auth never stores refresh bearer and uses browser endpoints',()=>{
  assert.match(auth,/auth\/browser-login/)
  assert.match(auth,/auth\/browser-invite\/accept/)
  assert.match(request,/auth\/browser-refresh/)
  assert.match(request,/X-Browser-Session-Id/)
  assert.doesNotMatch(request,/let refreshToken/)
  assert.doesNotMatch(request,/localStorage/)
})

test('browser evidence enters the workbench through browser login and campaign selection',()=>{
  assert.match(browser,/enterprise-portal\/auth\/browser-login/)
  assert.match(browser,/enterprise-portal\/auth\/browser-refresh/)
  assert.match(browser,/getByLabel\('学校编码'\)/)
  assert.match(browser,/getByRole\('button',\{name:'登录'\}\)/)
  assert.match(browser,/选择招聘季/)
  assert.doesNotMatch(browser,/sessionStorage\.setItem\('ep_campaign_id_v1'/)
})
