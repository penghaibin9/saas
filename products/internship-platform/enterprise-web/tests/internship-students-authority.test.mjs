import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/InternshipStudentListView.vue',import.meta.url),'utf8')
const template=page.match(/<template>([\s\S]*?)<\/template>/)?.[1]||''
test('正式学生状态与日期使用中文，未知内部状态不直接暴露',()=>{
  const code=page.slice(page.indexOf('function studentStatus('),page.indexOf('async function load('))
  const {studentStatus,studentDate}=new Function(code+';return {studentStatus,studentDate}')()
  assert.equal(studentStatus({status:'ONBOARD'}),'在岗中')
  assert.equal(studentStatus({status:'ONBOARD',status_label:'ONBOARD'}),'在岗中')
  assert.equal(studentStatus({status:'UNKNOWN_INTERNAL'}),'状态待核对')
  assert.match(studentDate('2026-10-18T12:28:31Z'),/2026.*10.*18/)
  assert.equal(studentDate('invalid'),'待确认');assert.equal(studentDate(null),'待确认')
})

test('internship students page stays InternshipRecord-only internally while enterprise copy remains business-facing',()=>{
  assert.match(page,/InternshipRecord-only/)
  assert.match(page,/MENTOR/)
  assert.match(page,/member\/contact scope/)
  assert.match(template,/学校已正式落岗的实习学生/)
  assert.match(template,/企业导师仅查看学校授权的学生/)
  assert.doesNotMatch(page,/ACCEPT_INTENT/)
  assert.doesNotMatch(template,/InternshipRecord|member\/contact scope|Authority|canonical|facade/)
})
