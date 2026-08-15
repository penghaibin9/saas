import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/PositionListView.vue',import.meta.url),'utf8')
const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')

test('A02-4 position list exposes canonical eight-state labels without inventing authority',()=>{
  for(const label of ['草稿','待学校审核','已发布','已下线','已暂停','已招满','风险','已归档'])assert.match(page,new RegExp(label))
  assert.match(page,/撤回修改/)
  assert.doesNotMatch(page,/直接发布/)
})

test('A02-4 position list is server-paged and does not materialize/filter a fake local full dataset',()=>{
  assert.match(api,/pageSize=20/)
  assert.match(api,/params:\{\.\.\.recruitmentParams\(\),page,pageSize,status,keyword\}/)
  assert.match(page,/pageSize=20,total=ref\(0\)/)
  assert.match(page,/keyword:keyword\.value\.trim\(\)/)
  assert.match(page,/上一页/)
  assert.match(page,/下一页/)
  assert.doesNotMatch(page,/items\.value\.filter\(/)
})

test('A02-4 missing applicant placement counters stay unknown instead of fake zero',()=>{
  assert.match(page,/function countText/)
  assert.match(page,/value===undefined\|\|value===null\?'—':value/)
  assert.doesNotMatch(page,/applicantCount\?\?0/)
  assert.doesNotMatch(page,/acceptIntentCount\?\?0/)
  assert.doesNotMatch(page,/placementCount\?\?0/)
})

test('A02-4 withdraw is optimistic-lock protected with server version',()=>{
  assert.match(page,/withdrawPosition\(item\.id,item\.version\)/)
})
