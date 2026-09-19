import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('../src/modules/academicAffairs/views/AaStatsOverviewView.vue', import.meta.url),
  'utf8'
)

test('workload detail keeps the selected term filter', () => {
  const handlerStart = source.lastIndexOf('viewWorkloadDetail(row)')
  assert.notEqual(handlerStart, -1, 'workload detail handler must exist')
  const handler = source.slice(handlerStart, source.indexOf('async openExport()', handlerStart))
  const loaderStart = source.indexOf('async loadDetail()')
  assert.notEqual(loaderStart, -1, 'shared detail loader must exist')
  const loader = source.slice(loaderStart, handlerStart)
  const paramsStart = source.indexOf('baseParams()')
  const params = source.slice(paramsStart, source.indexOf('async loadTab()', paramsStart))

  assert.match(handler, /detailRoute\(\{ teacherKey: String\(row\.teacherKey\) \}\)/)
  assert.match(loader, /getStatsWorkloadDetail\(\{[^}]*teacherKey: this\.workloadTeacherKey/)
  assert.match(loader, /\.\.\.this\.baseParams\(\)/)
  assert.match(params, /termId: this\.appliedFilters\.termId \|\| undefined/)
  assert.match(params, /collegeId: this\.appliedFilters\.collegeId \|\| undefined/)
})
