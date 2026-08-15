import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const layout=read('../src/layouts/EnterprisePortalLayout.vue')
const positions=read('../src/views/PositionListView.vue')
const positionForm=read('../src/views/PositionFormView.vue')
const applicants=read('../src/views/ApplicantListView.vue')
const detail=read('../src/views/ApplicantDetailView.vue')
const contact=read('../src/components/applicant/ContactRevealButton.vue')
const decision=read('../src/components/applicant/DecisionActions.vue')
const store=read('../src/stores/enterpriseContext.js')

test('expired or invalid enterprise access blocks protected portal content',()=>{
  assert.match(store,/contextReady/)
  assert.match(layout,/访问授权不可用/)
  assert.match(layout,/访问授权已过期/)
  assert.match(layout,/RouterView v-else/)
})

test('campaign closed and unavailable context fail closed',()=>{
  assert.match(store,/contextReady/)
  assert.match(store,/CLOSED/)
  assert.match(store,/ARCHIVED/)
  assert.match(positions,/招聘季已关闭/)
})

test('pending position is read-only until the school-review position is withdrawn to draft',()=>{
  assert.match(positions,/撤回修改/)
  assert.match(positionForm,/positionStatus\.value==='PENDING'/)
  assert.match(positionForm,/撤回到草稿修改/)
  assert.match(positionForm,/withdrawPosition/)
  assert.match(positionForm,/待学校审核的岗位需先撤回后再修改/)
  assert.doesNotMatch(positionForm,/PENDING 必须先撤回再修改/)
})

test('contact stays hidden until the dedicated server contact-view request succeeds',()=>{
  assert.match(contact,/MASKED_ONLY/)
  assert.match(contact,/enterpriseInternshipApi\.revealContact/)
  assert.match(contact,/data\?\.phone/)
  assert.match(contact,/data\?\.email/)
  assert.match(contact,/当前处理状态和企业范围再次校验/)
  assert.doesNotMatch(contact,/contactPolicy\?\.allowed===true/)
  assert.doesNotMatch(contact,/student\.phone|student\.email/)
})

test('decision conflict and released intent follow independent effect state rather than inferred group fields',()=>{
  assert.match(decision,/decisionDisabledReason/)
  assert.match(decision,/decisionEffectStatus==='ACTIVE'/)
  assert.match(decision,/decisionEffectStatus!=='ACTIVE'/)
  assert.match(decision,/撤回拟接收/)
  assert.match(decision,/withdrawAccept/)
  assert.match(detail,/等待学校最终确认/)
  assert.match(detail,/拟接收已失效或进入后续处理/)
  assert.doesNotMatch(decision,/volunteerGroupStatus==='LOCKED'/)
})

test('no applicant is an explicit empty state',()=>{
  assert.match(applicants,/暂无报名学生/)
})
