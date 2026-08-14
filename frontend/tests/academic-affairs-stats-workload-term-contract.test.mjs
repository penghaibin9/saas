import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('../src/modules/academicAffairs/views/AaStatsOverviewView.vue', import.meta.url),
  'utf8'
)

test('workload detail keeps the selected term filter', () => {
  const start = source.indexOf('async viewWorkloadDetail(row)')
  assert.notEqual(start, -1, 'workload detail handler must exist')
  const block = source.slice(start, source.indexOf('async openExport()', start))

  assert.match(block, /getStatsWorkloadDetail\(\{[^}]*teacherKey: row\.teacherKey/)
  assert.match(block, /termId: this\.filters\.termId \|\| undefined/)
  assert.match(block, /collegeId: this\.filters\.collegeId \|\| undefined/)
})
