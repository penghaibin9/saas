import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const view = fs.readFileSync(
  new URL('../src/modules/graduation/views/GraduationReviewAssignView.vue', import.meta.url),
  'utf8',
)
const studentApi = fs.readFileSync(
  new URL('../src/modules/graduation/api/graduation-student.api.js', import.meta.url),
  'utf8',
)

test('formal review assignment requests only students whose latest final is approved', () => {
  assert.match(view, /finalStatus:\s*'APPROVED'/)
  assert.match(view, /已通过正式定稿/)
  assert.match(view, /latest|最新正式定稿|最新/)
  assert.doesNotMatch(view, /pageSize:\s*50/)
})

test('review assignment reuses the server-search workbench paging contract instead of browser filtering', () => {
  assert.match(studentApi, /const pickerSearch = params\.page == null/)
  assert.match(studentApi, /page:\s*1,\s*pageSize:\s*200/)
  assert.doesNotMatch(view, /\.filter\([^\n]*finalStatus/)
})

test('formal review submit still goes through the authoritative assignment API', () => {
  assert.match(view, /graduationDefenseGradeApi\.assignReview\(this\.current\.id, null, this\.reviewerMentorId\)/)
  assert.match(view, /exact FileVersion/)
  assert.match(view, /SoD/)
})
