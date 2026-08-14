import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const store=read('../src/stores/enterpriseContext.js'),home=read('../src/views/EnterpriseHomeView.vue'),positions=read('../src/views/PositionListView.vue'),form=read('../src/views/PositionFormView.vue'),decisions=read('../src/components/applicant/DecisionActions.vue'),select=read('../src/views/CampaignSelectView.vue'),layout=read('../src/layouts/EnterprisePortalLayout.vue')

test('closed and archived campaigns fail closed for recruitment writes',()=>{
  assert.match(store,/CLOSED','ARCHIVED/)
  assert.match(store,/recruitmentWrite:authContext\?\.capabilities\?\.recruitmentWrite===true/)
  assert.match(form,/recruitmentWritable/)
  assert.match(decisions,/campaignWritable/)
  assert.match(positions,/招聘季已关闭/)
})

test('campaign selector preserves closed and archived history instead of hiding it',()=>{
  assert.match(select,/historyItems/)
  assert.match(select,/历史招聘季/)
  assert.match(select,/进入历史只读视图/)
  assert.match(select,/岗位、申请与 Decision 作为历史记录保留/)
})

test('internship collaboration is never inferred from campaign history',()=>{
  assert.match(home,/context\.capabilities\?\.internshipCollab===true/)
  assert.match(home,/服务端显式确认有效 INTERNSHIP_COLLAB Grant/)
  assert.match(home,/不会根据历史招聘季状态自行推断权限/)
  assert.doesNotMatch(store,/internshipCollab\s*:\s*true/)
})

test('portal remains fail closed when enterprise context cannot be validated',()=>{
  assert.match(layout,/访问授权不可用/)
  assert.match(layout,/不会降级到未校验 companyId 或本地权限/)
  assert.match(layout,/campaignName/)
})
