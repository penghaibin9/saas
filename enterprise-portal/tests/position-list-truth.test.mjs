import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/PositionListView.vue',import.meta.url),'utf8')

test('A02-4 position list exposes canonical eight-state labels without inventing authority',()=>{
  for(const label of ['草稿','待学校审核','已发布','已下线','已暂停','已招满','风险','已归档'])assert.match(page,new RegExp(label))
  assert.match(page,/撤回修改/)
  assert.doesNotMatch(page,/直接发布/)
})

test('A02-4 missing applicant placement counters stay unknown instead of fake zero',()=>{
  assert.match(page,/function countText/)
  assert.match(page,/value===undefined\|\|value===null\?'—':value/)
  assert.doesNotMatch(page,/applicantCount\?\?0/)
  assert.doesNotMatch(page,/acceptIntentCount\?\?0/)
  assert.doesNotMatch(page,/placementCount\?\?0/)
})
