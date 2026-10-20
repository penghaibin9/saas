import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

test('student and teacher miniapps share the loan receipt state machine', () => {
  const pages = JSON.parse(read('../src/pages.json'))
  const studentPkg = pages.subPackages.find(item => item.root === 'pages/student')
  const teacherPkg = pages.subPackages.find(item => item.root === 'pages/teacher')
  assert.ok(studentPkg.pages.some(item => item.path === 'affairs/loan'))
  assert.ok(teacherPkg.pages.some(item => item.path === 'affairs/loan/index'))
  const student = read('../src/pages/student/affairs/loan.vue')
  const teacher = read('../src/pages/teacher/affairs/loan/index.vue')
  for (const action of ['RESUBMIT', 'WITHDRAW']) assert.match(student, new RegExp(`allows\\(item, '${action}'\\)`))
  for (const action of ['SUBMIT_RECEIPT', 'VERIFY', 'RETURN', 'CONFIRM']) assert.match(teacher, new RegExp(`allows\\(item, '${action}'\\)`))
  assert.match(read('../src/services/realApi.js'), /\/mobile\/teacher\/affairs\/loans/)
  assert.match(read('../src/services/realApi.js'), /\/mobile\/affairs\/loans/)
})
