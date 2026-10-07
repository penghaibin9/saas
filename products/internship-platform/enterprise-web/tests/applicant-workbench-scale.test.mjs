import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/ApplicantListView.vue',import.meta.url),'utf8')
const card=fs.readFileSync(new URL('../src/components/applicant/CandidateCard.vue',import.meta.url),'utf8')

test('A02-6 applicant workbench requests bounded canonical pages for large-school volume',()=>{
  assert.match(page,/pageSize=50/)
  assert.match(page,/applications\(\{page:page\.value,pageSize,decisionStatus/)
  assert.match(page,/上一页/)
  assert.match(page,/下一页/)
  assert.match(page,/data\.total/)
  assert.match(page,/page\.value\*pageSize<total\.value/)
})

test('A02-6 only exposes filters currently frozen by the A01 list contract',()=>{
  assert.match(page,/当前只开放处理状态筛选/)
  assert.doesNotMatch(page,/v-model\.trim="keyword"|v-model\.trim="major"|v-model\.trim="grade"|v-model="volunteerNo"|v-model="match"/)
  assert.doesNotMatch(page,/positionOptions|loadPositions/)
  assert.doesNotMatch(page,/keyword:|major:|grade:|volunteerNo:|match:/)
})

test('A02-6 candidate cards render business labels instead of raw decision enums or invented match scores',()=>{
  for(const label of ['待处理','感兴趣','面试','拟接收','不合适'])assert.match(card,new RegExp(label))
  assert.doesNotMatch(card,/matchPercent|matchHint|skillTags/)
  assert.doesNotMatch(card,/\{\{\s*applicant\.decisionStatus\s*\}\}/)
})
