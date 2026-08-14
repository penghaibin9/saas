import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const layout=read('../src/layouts/EnterprisePortalLayout.vue')
const positions=read('../src/views/PositionListView.vue')
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

test('pending position is school-review state, never enterprise published state',()=>{
  assert.match(positions,/待学校审核/)
  assert.match(positions,/PENDING/)
  assert.doesNotMatch(positions,/直接发布/)
})

test('contact forbidden stays masked and disabled',()=>{
  assert.match(contact,/联系方式已脱敏/)
  assert.match(contact,/联系方式未授权/)
  assert.match(contact,/contactPolicy\.allowed===false/)
})

test('decision conflict and locked release keep server reason and release truth',()=>{
  assert.match(decision,/decision_disabled_reason|decisionDisabledReason/)
  assert.match(detail,/等待学校最终确认/)
  assert.match(detail,/本次拟接收已释放/)
  assert.match(detail,/TEACHER_CONFIRM_TIMEOUT/)
})

test('no applicant is an explicit empty state',()=>{
  assert.match(applicants,/暂无报名学生/)
})
