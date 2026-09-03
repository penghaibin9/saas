import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const [view, api] = await Promise.all([
  readFile(new URL('../src/modules/graduation/views/GraduationMaterialCenterView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/modules/graduation/api/graduation-material-center.api.js', import.meta.url), 'utf8')
])

test('V6 material center restores the complete seven-field work context', () => {
  for (const key of ['batchId', 'tab', 'page', 'keyword', 'stage', 'reviewStatus', 'scanStatus']) {
    assert.ok(view.includes(key), `missing material-center query key ${key}`)
  }
  assert.match(view, /function buildRouteQuery\(overrides = \{\}\)/)
  assert.match(view, /function applyRouteState\(query = route\.query\)/)
  assert.match(view, /router\.replace\(\{ query: buildRouteQuery\(overrides\) \}\)/)
  assert.match(view, /watch\([\s\S]*\(\) => route\.query/)
  assert.match(view, /batchId: batchId\.value \? String\(batchId\.value\) : undefined/)
})

test('V6 material list history and reader requests are latest-wins and batch-bound', () => {
  for (const token of ['listToken', 'historyToken', 'readerToken', 'reviewToken']) {
    assert.ok(view.includes(token), `missing stale-read guard ${token}`)
  }
  assert.match(view, /token !== listToken \|\| !sameListSnapshot\(snapshot\)/)
  assert.match(view, /snapshot\.batchId === String\(batchId\.value \|\| ''\)/)
  assert.match(view, /token !== historyToken \|\| batchSnapshot !== String\(batchId\.value \|\| ''\)/)
  assert.match(view, /token !== readerToken \|\| batchSnapshot !== String\(batchId\.value \|\| ''\)/)
  assert.match(view, /onBeforeUnmount\([\s\S]*\+\+listToken[\s\S]*\+\+historyToken[\s\S]*\+\+readerToken[\s\S]*\+\+reviewToken/)
})

test('V6 preview keeps the existing ticket timeout size abort and scan gate instead of exposing permanent URLs', () => {
  assert.match(view, /const previewProvider = api\.createPreviewProvider\(\)/)
  assert.match(view, /:provider="previewProvider"/)
  assert.match(view, /target\?\.canPreview/)
  assert.match(view, /当前版本未通过安全门，禁止预览/)
  assert.ok(!view.includes('window.open('), 'material center must not open a permanent direct file URL')

  assert.match(api, /DEFAULT_MAX_PREVIEW_BYTES/)
  assert.match(api, /DEFAULT_PREVIEW_TIMEOUT_MS/)
  assert.match(api, /AbortController/)
  assert.match(api, /createPreviewTicket/)
  assert.match(api, /readyForBusiness/)
})

test('V6 material review freezes record canonical FileVersion expectedVersion batch and route', () => {
  assert.match(view, /function freezeReviewTarget\(row, action, reason\)/)
  assert.match(view, /materialId: String\(row\.materialId\)/)
  assert.match(view, /fileVersionId: String\(row\.currentVersionId\)/)
  assert.match(view, /expectedVersion: row\.version/)
  assert.match(view, /batchId: String\(batchId\.value\)/)
  assert.match(view, /routeQuery: buildRouteQuery\(\)/)
  assert.match(view, /api\.reviewMaterial\(target\.materialId, \{[\s\S]*fileVersionId: target\.fileVersionId,[\s\S]*expectedVersion: target\.expectedVersion,[\s\S]*action: target\.action,[\s\S]*comment: target\.reason/)
  assert.match(view, /async function readReviewTruth\(target, token\)/)
  assert.match(view, /api\.studentLibrary\(target\.gdStudentId, true\)/)
  assert.match(view, /latestStatus !== expectedStatus/)
  assert.match(view, /服务器材料台账尚未回读到目标状态/)
  assert.match(view, /onBeforeRouteLeave/)
  assert.match(view, /next\(false\)/)
})

test('V6 version timeline opens the exact selected immutable FileVersion in the same reader', () => {
  assert.match(view, /async function openHistoryVersion\(item\)/)
  assert.match(view, /const file = item\?\.file/)
  assert.match(view, /await openReader\(row, file, versions\)/)
  assert.match(view, /String\(versionKey\(item\)\) === String\(exactId\)/)
  assert.match(view, /readerState\.file\.isCurrent === false/)
})

test('V6 student deep links preserve batch source and precise return path', () => {
  assert.match(view, /function currentReturnTo\(\)/)
  assert.match(view, /name: 'graduation-student-detail'/)
  assert.match(view, /batchId: String\(batchId\.value\)/)
  assert.match(view, /source: 'material-center'/)
  assert.match(view, /returnTo: currentReturnTo\(\)/)
})

test('V6 every context-changing control is locked while review truth is in flight', () => {
  assert.match(view, /const commandLocked = computed\(\(\) => reviewing\.value \|\| Boolean\(reviewSnapshot\.value\)\)/)
  assert.match(view, /:disabled="loading \|\| commandLocked"/)
  assert.match(view, /:disabled="commandLocked"/)
  for (const method of ['changeTab', 'search', 'reset', 'goto', 'openReader', 'history', 'openStudent']) {
    assert.match(view, new RegExp(`function ${method}\\([\\s\\S]*?commandLocked\\.value`), `${method} must fail closed during a review command`)
  }
})
