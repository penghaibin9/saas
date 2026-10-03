import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/InternshipStudentListView.vue',import.meta.url),'utf8')
const template=page.match(/<template>([\s\S]*?)<\/template>/)?.[1]||''

test('A02-8 formal internship students are collaboration-gated and server-paged for large enterprise cohorts',()=>{
  assert.match(page,/pageSize=50/)
  assert.match(page,/collabReady/)
  assert.match(page,/batchId:batchId\.value/)
  assert.match(page,/internshipStudents\(\{batchId:batchId\.value,status:status\.value,keyword:keyword\.value,page:page\.value,pageSize\}\)/)
  assert.match(template,/上一页/)
  assert.match(template,/下一页/)
  assert.doesNotMatch(page,/items\.value\.filter/)
})

test('A02-8 page stays on formal InternshipRecord authority and never promotes ACCEPT_INTENT',()=>{
  assert.match(page,/InternshipRecord-only/)
  assert.match(page,/MENTOR scope is enforced by backend member\/contact scope/)
  assert.match(template,/学校已正式落岗的实习学生/)
  assert.match(template,/企业导师仅查看学校授权的学生/)
  assert.doesNotMatch(page,/ACCEPT_INTENT/)
  assert.doesNotMatch(template,/拟接收.*正式实习/)
})

test('A02-8 omitted total metadata remains unknown rather than inferred from current page',()=>{
  assert.match(page,/total\.value=.*null/)
  assert.match(page,/第 \$\{page\.value\} 页/)
  assert.doesNotMatch(page,/items\.value\.length\s*\*\s*pageSize/)
})
