import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const root = new URL('../src/', import.meta.url)
const read = path => fs.readFileSync(new URL(path, root), 'utf8')

test('recheck history uses a bounded server page and does not locally truncate history', () => {
  const page = read('pages/student/academic-affairs/recheck.vue')
  const api = read('services/realApi.js')
  const studentApi = read('services/studentApi.js')

  assert.match(page, /const RECHECK_PAGE_SIZE = 20/)
  assert.match(page, /studentApi\.getMyRecheck\(\{ page: requestedPage, pageSize: RECHECK_PAGE_SIZE \}\)/)
  assert.match(page, /normalizeRecheckPage\(mine, requestedPage\)/)
  assert.match(page, /previousPage\(\).*recheckPage - 1/)
  assert.match(page, /nextPage\(\).*recheckPage \+ 1/)
  assert.doesNotMatch(page, /d\.items\.slice\(0, listLimit\)/)
  assert.match(api, /acadRecheckMy = \(params = \{\}\)/)
  assert.match(studentApi, /getMyRecheck: \(params = \{\}\)/)
})

test('a score page deep link is read through a self-scoped exact-grade API', () => {
  const page = read('pages/student/academic-affairs/recheck.vue')
  const api = read('services/realApi.js')
  const studentApi = read('services/studentApi.js')

  assert.match(page, /studentApi\.getMyRecheckEligible\(directTargetId\)/)
  assert.match(page, /mergeGrades\(tr\.items\.filter/)
  assert.match(api, /acadRecheckEligible = \(gradeId\).*grade-recheck\/eligible/)
  assert.match(studentApi, /getMyRecheckEligible: \(gradeId\)/)
})
