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
  assert.match(view, /buildRouteQuery\(overrides = \{\}\)/)
  assert.match(view, /applyRouteState\(query = route\.query\)/)
  assert.match(view, /router\.replace\(\{ query: buildRouteQuery/)
})

test('V6 material list history and reader requests are latest-wins and batch-bound', () => {
  for (const token of ['listToken', 'historyToken', 'readerToken']) {
    assert.ok(view.includes(token), `missing stale-read guard ${token}`)
  }
  assert.match(view, /token !== listToken/)
  assert.match(view, /snapshot\.batchId !== String\(batchId\.value/)
  assert.match(view, /token !== historyToken \|\| batchSnapshot !== String\(batchId\.value/)
  assert.match(view, /token !== readerToken \|\| batchSnapshot !== String\(batchId\.value/)
})

test('V6 preview keeps the existing ticket timeout size abort and scan gate instead of exposing permanent URLs', () => {
  assert.match(view, /const previewProvider = api\.createPreviewProvider\(\)/)
  assert.match(view, /:preview-provider="previewProvider"/)
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
  assert.match(view, /materialId: String\(row\.materialId\)/)
  assert.match(view, /fileVersionId: String\(row\.currentVersionId\)/)
  assert.match(view, /expectedVersion: row\.version/)
  assert.match(view, /batchId: String\(batchId\.value\)/)
  assert.match(view, /routeQuery: buildRouteQuery\(\)/)
  assert.match(view, /api\.reviewMaterial\(target\.materialId, \{ fileVersionId: target\.fileVersionId, expectedVersion: target\.expectedVersion, action: target\.action, comment: target\.reason \}\)/)
  assert.match(view, /await load\(\)/)
  assert.match(view, /beforeRouteLeave/)
  assert.match(view, /next\(false\)/)
})

test('V6 version timeline opens the exact selected immutable FileVersion in the same reader', () => {
  assert.match(view, /async function openHistoryVersion\(item\)/)
  assert.match(view, /const file = item\?\.file/)
  assert.match(view, /await openReader\(row, file, historyVersions\.value\)/)
  assert.match(view, /String\(versionKey\(item\)\) === String\(exactId\)/)
  assert.match(view, /readerState\.file\.isCurrent === false/)
})

test('V6 student deep links preserve batch source and precise return path', () => {
  assert.match(view, /name: 'graduation-student-detail'/)
  assert.match(view, /batchId: String\(batchId\.value\)/)
  assert.match(view, /source: 'material-center'/)
  assert.match(view, /returnTo: currentReturnTo\(\)/)
})
