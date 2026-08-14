import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/EvaluationTaskListView.vue',import.meta.url),'utf8')

test('A02-9 evaluation tasks are server filtered and paged',()=>{
  assert.match(page,/pageSize=50/)
  assert.match(page,/evaluationTasks\(\{status:tab\.value==='ALL'\?'':tab\.value,page:page\.value,pageSize\}\)/)
  assert.match(page,/上一页/);assert.match(page,/下一页/)
  assert.doesNotMatch(page,/items\.value\.filter/)
})

test('A02-9 five canonical dimensions require explicit 0-100 scores instead of default 90',()=>{
  for(const field of ['attendanceScore','skillScore','attitudeScore','collaborationScore','safetyScore'])assert.match(page,new RegExp(field))
  assert.match(page,/五项评分均需明确填写 0–100 分/)
  assert.match(page,/attendanceScore:null/)
  assert.doesNotMatch(page,/attendanceScore:90/)
})

test('A02-9 evaluation payload cannot forge canonical actor source or audit fields',()=>{
  const submitBlock=page.match(/submitEvaluation\(id,\{[\s\S]*?\}\)/)?.[0]||''
  for(const forbidden of ['sourceType','actorMemberId','recordedAt','enterpriseContactId','tenantId','companyId'])assert.doesNotMatch(submitBlock,new RegExp(forbidden))
  assert.match(page,/source=ENTERPRISE_ONLINE/)
  assert.match(page,/服务端写入并审计/)
})
