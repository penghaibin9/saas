import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const page = read('src/pages/student/internship/agreement/index.vue')
const studentApi = read('src/services/studentApi.js')
const internshipApi = read('src/services/internshipApi.js')

test('Student Mini agreement uses canonical context APIs only', () => {
  assert.match(studentApi, /internship\.studentInternshipAgreements\(\)/)
  assert.match(studentApi, /internship\.studentInternshipAgreementDetail\(id\)/)
  assert.match(studentApi, /internship\.studentInternshipAgreementConfirm\(id, body\)/)
  assert.match(internshipApi, /\/mobile\/internship\/context\/agreements/)
  assert.doesNotMatch(studentApi, /real\.internshipAgreement/)
})

test('Agreement deep link loads exact detail without depending on ambiguous list selection', () => {
  assert.match(page, /if \(this\._openId\) this\.openExactDetail\(this\._openId\)/)
  assert.match(page, /getInternshipAgreementDetail\(id\)/)
  assert.doesNotMatch(page, /this\.list\.find\(\(x\).*this\._openId/)
})

test('Agreement writes carry explicit context and version and never auto-replay conflicts', () => {
  assert.match(page, /batchId: this\.detail\?\.batchId/)
  assert.match(page, /internshipId: this\.detail\?\.internId/)
  assert.match(page, /expectedVersion: this\.detail\?\.version/)
  assert.match(page, /系统不会自动重放/)
  const conflict = page.indexOf("if (code.includes('409')")
  assert.ok(conflict >= 0)
  assert.equal(page.slice(conflict, conflict + 300).includes('confirmInternshipAgreement'), false)
})
