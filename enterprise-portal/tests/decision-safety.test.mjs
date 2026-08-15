import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/components/applicant/DecisionActions.vue',import.meta.url),'utf8')
const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')

test('A02-7 decision-disabled and inactive effect state both block enterprise actions',()=>{
  assert.match(page,/Boolean\(props\.application\.decisionDisabledReason\)/)
  assert.match(page,/decisionEffectStatus==='ACTIVE'/)
  assert.match(page,/decisionEffectStatus!=='ACTIVE'/)
})

test('A02-7 ACCEPT_INTENT requires explicit confirmation and never claims placement',()=>{
  assert.match(page,/确认拟接收这名学生/)
  assert.match(page,/学校最终确认流程/)
  assert.match(page,/不等于正式落岗/)
  assert.doesNotMatch(page,/已录用/)
})

test('A02-7 INTERVIEW requires an interviewAt payload before calling the frozen Decision route',()=>{
  assert.match(page,/type="datetime-local"/)
  assert.match(page,/if\(!interviewAt\.value\)/)
  assert.match(page,/interviewAt:interviewAt\.value/)
  assert.match(page,/interviewNote:interviewNote\.value\.trim\(\)/)
})

test('A02-7 withdrawing active ACCEPT_INTENT uses the dedicated A01 route and requires reason',()=>{
  assert.match(page,/撤回拟接收必须填写原因/)
  assert.match(page,/withdrawReason\.value\.trim\(\)/)
  assert.match(page,/确认撤回并标记不合适/)
  assert.match(api,/applications\/\$\{id\}\/withdraw-accept/)
  assert.match(api,/body:\{ reason:text \}/)
  assert.doesNotMatch(api,/withdrawAccept:[\s\S]*status:'REJECTED'/)
})
