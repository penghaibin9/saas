import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

// Exercise the actual component methods with isolated API responses; no database writes.
function createView(file, api = {}) {
  const source = readFileSync(new URL(`../src/modules/studentAffairs/views/${file}.vue`, import.meta.url), 'utf8')
  const names = []
  const script = parse(source).descriptor.script.content
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, imports) => {
      names.push(...imports.split(',').map(s => s.trim())); return ''
    })
    .replace(/import\s+(\w+)\s+from\s+['"][^'"]+['"]/g, (_, name) => { names.push(name); return '' })
    .replace('export default', 'return')
  const component = new Function(...names, script)(...names.map(name => name === 'studentAffairsApi' ? api : name === 'toast' ? { success() {}, error() {} } : {}))
  const view = component.data()
  for (const [name, fn] of Object.entries(component.methods)) view[name] = fn.bind(view)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(view, name, { get: fn.bind(view) })
  return view
}

test('evaluation sends period/status and pagination to the server, and reports failed lists', async () => {
  let query
  const view = createView('eval/CounselorEvalView', {
    getEvalIndicators: async () => ({ code: 0, data: { items: [] } }),
    getCounselorEvals: async q => { query = q; return { code: 403, message: '无权查看' } }
  })
  view.filters = { periodCode: ' 2026-1 ', status: 'DRAFT' }
  view.pagination.page = 4
  await view.load()
  assert.deepEqual(query, { periodCode: '2026-1', status: 'DRAFT', page: 4, pageSize: 20 })
  assert.equal(view.pageState, 'error')
  assert.equal(view.errorMessage, '无权查看')
})

test('switching score records preserves separate unsaved input and does not mutate listed scores', () => {
  const view = createView('eval/CounselorEvalView')
  view.indicators = [{ indicatorId: '9007199254740993' }]
  view.scoreForm.counselorKey = 'unsaved-new'
  const record = { evalId: '9007199254740999', periodCode: '2026', counselorKey: 'T1', scores: { '9007199254740993': 70 }, remark: '保留说明' }
  view.openScore(record)
  view.scoreForm.scores['9007199254740993'] = 85
  view.openScore()
  assert.equal(view.scoreForm.counselorKey, 'unsaved-new')
  view.openScore(record)
  assert.equal(view.scoreForm.scores['9007199254740993'], 85)
  assert.equal(record.scores['9007199254740993'], 70)
  assert.equal(view.scoreForm.remark, '保留说明')
})

test('failed score save retains form and remark; successful retry clears only the saved draft', async () => {
  let fail = true
  let body
  const view = createView('eval/CounselorEvalView', {
    upsertCounselorEval: async data => { body = data; return fail ? { code: 409, message: '已发布不可修改' } : { code: 0 } }
  })
  view.load = () => {}
  view.indicators = [{ indicatorId: '1' }]
  view.openScore({ evalId: '8', periodCode: '2026', counselorKey: 'T1', scores: { '1': 88 }, remark: '原备注' })
  await view.saveScore()
  assert.equal(view.scoreError, '已发布不可修改')
  assert.equal(view.scoreVisible, true)
  assert.equal(body.remark, '原备注')
  fail = false
  await view.saveScore()
  assert.equal(view.scoreVisible, false)
  assert.equal(view.scoreKey, 'new')
  assert.equal(view.scoreDrafts['8'], undefined)
})

test('archive selection ignores the earlier batch response', async () => {
  let resolveOld
  const view = createView('ArchiveManageView', {
    getArchiveBatch: id => id === 'A' ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ code: 0, data: { batchId: 'B', packages: [{ packageId: 'B-1' }] } })
  })
  view.current = { batchId: 'A' }
  const old = view.reload()
  view.current = { batchId: 'B' }
  await view.reload()
  resolveOld({ code: 0, data: { batchId: 'A', packages: [{ packageId: 'A-1' }] } })
  await old
  assert.equal(view.current.batchId, 'B')
  assert.equal(view.packages[0].packageId, 'B-1')
})

test('archive errors remain visible instead of an empty success screen', async () => {
  const view = createView('ArchiveManageView', { getArchiveBatches: async () => ({ code: 500, message: '加载失败' }) })
  await view.loadBatches()
  assert.equal(view.listLoading, false)
  assert.equal(view.listError, '加载失败')
})

test('clearing a package selection discards its pending response', async () => {
  let resolve
  const view = createView('StudentArchivePackageView', { getArchiveBatch: () => new Promise(r => { resolve = r }) })
  view.selBatch = '9007199254740999'
  const old = view.loadBatch()
  view.selBatch = ''
  await view.loadBatch()
  resolve({ code: 0, data: { packages: [{ packageId: 'old' }] } })
  await old
  assert.deepEqual(view.packages, [])
  assert.equal(view.batchLoading, false)
  assert.equal(view.pkgLabel('GENERATING'), '生成中')
  assert.equal(view.pkgLabel('PENDING_SUPPLEMENT'), '生成失败，待处理')
})
