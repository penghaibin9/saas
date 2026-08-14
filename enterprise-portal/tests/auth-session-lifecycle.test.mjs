import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const request=fs.readFileSync(new URL('../src/services/request.js',import.meta.url),'utf8')
const layout=fs.readFileSync(new URL('../src/layouts/EnterprisePortalLayout.vue',import.meta.url),'utf8')

test('expired refresh invalidates tokens and stale campaign exactly once',()=>{
  assert.match(request,/function invalidateEnterpriseAuth/)
  assert.match(request,/clearEnterpriseSession\(\)/)
  assert.match(request,/setSelectedCampaignId\(''\)/)
  assert.match(request,/authExpired\(payload,response\)/)
  assert.match(request,/if\(refreshing\)return refreshing/)
})

test('temporary refresh network failure does not deliberately clear enterprise auth state',()=>{
  const refreshBody=request.match(/async function refreshOnce\(\)[\s\S]*?\n}\n\nexport async function request/)?.[0]||''
  assert.match(refreshBody,/网络不可达，暂时无法刷新企业登录状态/)
  const networkBlock=refreshBody.match(/catch\{[\s\S]*?error\.network=true;throw error\n    }/)?.[0]||''
  assert.doesNotMatch(networkBlock,/clearEnterpriseSession|clearAccessToken|setSelectedCampaignId/)
})

test('enterprise portal exposes explicit logout that clears session and Pinia context',()=>{
  assert.match(layout,/clearEnterpriseSession\(\)/)
  assert.match(layout,/context\.\$reset\(\)/)
  assert.match(layout,/router\.replace\('\/login'\)/)
  assert.match(layout,/>退出<\/button>/)
})
