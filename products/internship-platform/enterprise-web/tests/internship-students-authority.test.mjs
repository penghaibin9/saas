import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/InternshipStudentListView.vue',import.meta.url),'utf8')
const template=page.match(/<template>([\s\S]*?)<\/template>/)?.[1]||''

test('internship students page stays InternshipRecord-only internally while enterprise copy remains business-facing',()=>{
  assert.match(page,/InternshipRecord-only/)
  assert.match(page,/MENTOR/)
  assert.match(page,/member\/contact scope/)
  assert.match(template,/学校已正式落岗的实习学生/)
  assert.match(template,/企业导师仅查看学校授权的学生/)
  assert.doesNotMatch(page,/ACCEPT_INTENT/)
  assert.doesNotMatch(template,/InternshipRecord|member\/contact scope|Authority|canonical|facade/)
})
