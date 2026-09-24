import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const realApi = await readFile(new URL('../src/services/realApi.js', import.meta.url), 'utf8')
const studentApi = await readFile(new URL('../src/services/studentApi.js', import.meta.url), 'utf8')
const page = await readFile(new URL('../src/pages/student/academic-affairs/selection.vue', import.meta.url), 'utf8')

test('student selection uses the dedicated DROP preflight before canonical drop', () => {
  assert.match(realApi, /acadSelectionDropPreflight/)
  assert.match(studentApi, /preflightDropSelection/)
  const start = page.indexOf('async runDrop(captured)')
  const block = page.slice(start, page.indexOf('\n    startWrite(captured)', start))
  assert.ok(start >= 0)
  assert.ok(block.indexOf('preflightDropSelection') < block.indexOf('dropSelection'))
  assert.match(block, /matchesDropPreflight/)
  assert.match(page, /String\(preflight\.selectionRecordId \|\| ''\) === captured\.selectionRecordId/)
  assert.match(block, /reconcileWrite/)
})
