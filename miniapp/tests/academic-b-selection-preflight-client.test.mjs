import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const realApi = await readFile(new URL('../src/services/realApi.js', import.meta.url), 'utf8')
const studentApi = await readFile(new URL('../src/services/studentApi.js', import.meta.url), 'utf8')
const page = await readFile(new URL('../src/pages/student/academic-affairs/selection.vue', import.meta.url), 'utf8')

test('miniapp preflights before enroll and reuses backend decision trace', () => {
  assert.match(realApi, /acadSelectionPreflight/)
  assert.match(studentApi, /preflightSelection/)
  const start = page.indexOf('enroll(c)')
  const block = page.slice(start, page.indexOf('drop(c)', start))
  assert.ok(block.indexOf('preflightSelection') < block.indexOf('enrollSelection'))
  assert.match(block, /preflight\.allowed/)
  assert.match(block, /preflight\.decisionTrace/)
  assert.match(page, /MobileAcademicDecisionCard/)
})
