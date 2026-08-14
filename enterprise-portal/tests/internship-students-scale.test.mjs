import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/InternshipStudentListView.vue',import.meta.url),'utf8')

test('A02-8 formal internship students are server-paged for large enterprise cohorts',()=>{
  assert.match(page,/pageSize=50/)
  assert.match(page,/internshipStudents\(\{status:status\.value,keyword:keyword\.value,page:page\.value,pageSize\}\)/)
  assert.match(page,/上一页/)
  assert.match(page,/下一页/)
  assert.doesNotMatch(page,/items\.value\.filter/)
})

test('A02-8 page stays on formal InternshipRecord authority and never promotes ACCEPT_INTENT',()=>{
  assert.match(page,/正式落岗的 InternshipRecord/)
  assert.match(page,/MENTOR 范围由后端 member\/contact scope 裁剪/)
  assert.doesNotMatch(page,/ACCEPT_INTENT/)
  assert.doesNotMatch(page,/拟接收.*正式实习/)
})

test('A02-8 omitted total metadata remains unknown rather than inferred from current page',()=>{
  assert.match(page,/total\.value=.*null/)
  assert.match(page,/第 \$\{page\.value\} 页/)
  assert.doesNotMatch(page,/items\.value\.length\s*\*\s*pageSize/)
})
