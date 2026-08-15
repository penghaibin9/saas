import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const api = await readFile(new URL('../src/services/portalApi.js', import.meta.url), 'utf8')
const view = await readFile(new URL('../src/views/academic/StudentSelectionView.vue', import.meta.url), 'utf8')

test('student PC preflights before enroll and renders backend decision trace', () => {
  assert.match(api, /academicSelectionPreflight/)
  const start = view.indexOf('async function enroll(course)')
  const block = view.slice(start, view.indexOf('async function drop', start))
  assert.ok(block.indexOf('academicSelectionPreflight') < block.indexOf('academicEnroll'))
  assert.match(block, /preflight\?\.allowed/)
  assert.match(block, /preflight\?\.decisionTrace/)
  assert.match(view, /AcademicDecisionTraceCard/)
})
