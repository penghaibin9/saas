import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/components/applicant/DecisionActions.vue',import.meta.url),'utf8')
const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')

test('A02-7 server decisionDisabledReason actually disables enterprise actions',()=>{
  assert.match(page,/Boolean\(props\.application\.decisionDisabledReason\)/)
  assert.match(page,/if\(props\.application\.decisionDisabledReason\)/)
})

test('A02-7 ACCEPT_INTENT requires explicit confirmation and never claims placement',()=>{
  assert.match(page,/确认拟接收这名学生/)
  assert.match(page,/学校最终确认流程/)
  assert.match(page,/不等于正式落岗/)
  assert.doesNotMatch(page,/已录用/)
})

test('A02-7 released accept intent is not treated as an active locked decision',()=>{
  assert.match(page,/!props\.application\.acceptIntentReleased/)
})

test('A02-7 withdrawing ACCEPT_INTENT follows A01 REJECTED transition and requires reason',()=>{
  assert.match(page,/撤回拟接收必须填写原因/)
  assert.match(page,/withdrawReason\.value\.trim\(\)/)
  assert.match(page,/确认撤回并标记不合适/)
  assert.match(api,/status:'REJECTED', reason:text/)
  assert.match(api,/text\.length<2/)
  assert.doesNotMatch(api,/withdraw-accept/)
})
