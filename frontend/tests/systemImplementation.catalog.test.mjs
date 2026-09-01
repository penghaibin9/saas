import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'

const catalog = fs.readFileSync(new URL('../src/modules/system/systemManagementCatalog.js', import.meta.url), 'utf8')
const routes = fs.readFileSync(new URL('../src/modules/system/system.routes.js', import.meta.url), 'utf8')
const workspace = fs.readFileSync(new URL('../src/modules/system/views/SystemImplementationWorkspaceView.vue', import.meta.url), 'utf8')
const legacyView = fs.readFileSync(new URL('../src/modules/system/views/SystemImplementationView.vue', import.meta.url), 'utf8')

test('implementation center exposes eight real menu leaves and routes', () => {
  assert.equal((catalog.match(/key: 'sys-implementation',/g) || []).length, 1)
  const leaves = [
    'sys-implementation-overview', 'sys-implementation-wizard', 'sys-implementation-presets',
    'sys-implementation-standards',
    'sys-implementation-mapping', 'sys-implementation-installed', 'sys-implementation-changes',
    'sys-implementation-acceptance'
  ]
  for (const key of leaves) assert.match(catalog, new RegExp(key))

  const pageKeys = ['overview', 'wizard', 'presets', 'standards', 'data-mapping', 'installed', 'changes', 'acceptance']
  for (const key of pageKeys) assert.match(routes, new RegExp(`implementation/${key}`))
  assert.equal((routes.match(/SystemImplementationWorkspaceView\.vue/g) || []).length, 1)
  assert.equal((routes.match(/SystemImplementationView\.vue/g) || []).length, 6)
  assert.equal((routes.match(/NationalStandardsView\.vue/g) || []).length, 1)
})

test('all implementation routes have backend permission keys', () => {
  const permissionMatches = routes.match(/systemAdmin\.implementation\.[a-z.]+/g) || []
  assert.equal(new Set(permissionMatches).size >= 7, true)
})

test('implementation workspace clears an applied preview and never reports stale install work', () => {
  assert.match(workspace, /preview && project\.status === 'PREVIEW_READY'/)
  assert.match(workspace, /this\.project\?\.status !== 'PREVIEW_READY'/)
  assert.match(workspace, /this\.preview = null\s+this\.idempotencyKey = ''/)
})

test('implementation center reuses canonical teacher imports for business relations', () => {
  assert.match(legacyView, /dataExchangeApi\.list\(\{ jobType: 'IMPORT', status: 'SUCCEEDED', keyword: 'IDENTITY_TEACHER'/)
  assert.match(legacyView, /discoverRelationsFromCompletedImport/)
  assert.match(legacyView, /复用已完成的教师导入/)
  assert.doesNotMatch(legacyView, /请输入(?:教师)?导入(?:任务|批次)(?:编号|ID)/)
})

test('implementation acceptance evidence is human readable', () => {
  assert.match(legacyView, /checkEvidenceText\(c\)/)
  assert.match(legacyView, /affectedCountsText\(changeAnalysis\.affectedTableCounts\)/)
  assert.doesNotMatch(legacyView, /JSON\.stringify\(c\.evidence\)/)
  assert.doesNotMatch(legacyView, /JSON\.stringify\(changeAnalysis\.affectedTableCounts\)/)
})
