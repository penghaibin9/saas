import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/ApplicantListView.vue',import.meta.url),'utf8')

test('A02-6 applicant workbench requests bounded pages for large-school volume',()=>{
  assert.match(page,/pageSize=50/)
  assert.match(page,/applications\(\{page:page\.value,pageSize/)
  assert.match(page,/上一页/)
  assert.match(page,/下一页/)
  assert.match(page,/data\?\.total/)
})

test('A02-6 position filtering is a business selector rather than internal-id text entry',()=>{
  assert.match(page,/全部岗位/)
  assert.match(page,/positionOptions/)
  assert.match(page,/position\.title\|\|position\.name/)
  assert.doesNotMatch(page,/placeholder="岗位 ID"/)
})

test('A02-6 does not invent total pages when backend omits pagination metadata',()=>{
  assert.match(page,/total\.value=.*null/)
  assert.match(page,/第 \$\{page\.value\} 页/)
  assert.doesNotMatch(page,/Math\.ceil\([^\n]*items\.value\.length/)
})
