import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/EvaluationTaskListView.vue',import.meta.url),'utf8')
const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')

test('enterprise evaluation uses the frozen online route but cannot forge actor/source/audit fields',()=>{
  assert.match(page,/ENTERPRISE_ONLINE/)
  assert.match(api,/evaluation-tasks\/\$\{id\}\/submit/)
  assert.match(api,/function evaluationPayload/)
  for(const forbidden of [/sourceType\s*:/,/actorMemberId\s*:/,/recordedAt\s*:/,/enterpriseContactId\s*:/,/tenantId\s*:/,/companyId\s*:/]){
    assert.doesNotMatch(api.match(/function evaluationPayload[\s\S]*?async function fetchApplicationMaterial/)?.[0]||'',forbidden)
    assert.doesNotMatch(page,forbidden)
  }
})

test('evaluation preserves existing canonical five score dimensions',()=>{
  for(const field of ['attendanceScore','skillScore','attitudeScore','collaborationScore','safetyScore'])assert.match(page,new RegExp(field))
})

test('returned evaluation is prefilled and resubmitted with canonical version CAS',()=>{
  assert.match(page,/schoolReviewStatus==='RETURNED'/)
  assert.match(page,/evaluationVersion/)
  assert.match(page,/payload\.expectedVersion=selected\.value\.evaluationVersion/)
  assert.match(page,/修改后重交/)
})
