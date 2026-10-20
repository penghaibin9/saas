import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const realApi = await readFile(new URL('../src/services/realApi.js', import.meta.url), 'utf8')
const studentApi = await readFile(new URL('../src/services/studentApi.js', import.meta.url), 'utf8')
const page = await readFile(new URL('../src/pages/student/academic-affairs/selection.vue', import.meta.url), 'utf8')

test('miniapp preflights before enroll and reuses backend decision trace', () => {
  assert.match(realApi, /acadSelectionPreflight/)
  assert.match(studentApi, /preflightSelection/)
  const start = page.indexOf('runEnroll(captured)')
  const block = page.slice(start, page.indexOf('drop(courseOrRecord)', start))
  assert.ok(start >= 0)
  assert.ok(block.indexOf('preflightSelection') < block.indexOf('enrollSelection'))
  assert.match(block, /preflight\.allowed/)
  assert.match(block, /preflight\.decisionTrace/)
  assert.match(block, /reconcileWrite/)
  assert.match(page, /MobileAcademicDecisionCard/)
})

test('miniapp consumes B-C3 server actions instead of deriving eligibility from remain/status', () => {
  assert.match(page, /allowedActions/)
  assert.match(page, /statusLabel/)
  assert.match(page, /howToResolve/)
  assert.match(page, /hasAction\(target, action\)/)
  assert.match(page, /detailLabel\(course\)/)
  assert.match(page, /查看办理条件/)
  assert.doesNotMatch(page, /canEnroll\(c\)/)

  const enrollStart = page.indexOf('enroll(course)')
  const enrollBlock = page.slice(enrollStart, page.indexOf('runEnroll(captured)', enrollStart))
  assert.match(enrollBlock, /hasAction\(course, ['"]ENROLL['"]\)/)

  const dropStart = page.indexOf('drop(courseOrRecord)')
  const dropBlock = page.slice(dropStart, page.indexOf('\n    goSchedule()', dropStart))
  assert.match(dropBlock, /hasAction\(courseOrRecord, ['"]DROP['"]\)/)
})
