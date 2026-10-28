import test from 'node:test'
import assert from 'node:assert/strict'
import { createPlanBulkExport } from '../../admin-web/src/modules/internship/composables/planBulkExport.js'
const row = id => ({ id: String(id), planTitle: `计划${id}`, planNo: `P-${id}` })
const page = (items, hasMore = false) => ({ code: 0, data: { items, hasMore } })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function harness(overrides = {}) {
  const downloads = [], calls = []
  const bulk = createPlanBulkExport({ canExport: () => true, loadPage: async () => page([row(1), row(2)]),
    exportFile: async (format, ids) => { calls.push({ format, ids }); return { code: 0, data: { contentBase64: 'JVBERg==', filename: 'plans.pdf', mediaType: 'application/pdf' } } },
    download: data => downloads.push(data), ...overrides })
  return { bulk, s: bulk.state, downloads, calls }
}
test('selection persists across pages and search without numeric ID conversion', async () => {
  const h = harness({ loadPage: async ({ page: p }) => page(p === 1 ? [row('9007199254740993')] : [row(2)]) })
  await h.bulk.load(1); h.bulk.toggle(h.s.rows[0]); await h.bulk.load(2); h.bulk.toggle(h.s.rows[0])
  h.s.keyword = '新检索'; await h.bulk.search()
  assert.deepEqual(h.s.selected.map(x => x.id), ['9007199254740993', '2'])
  await h.bulk.exportSelected('pdf'); assert.equal(h.downloads.length, 1)
  assert.deepEqual(h.calls[0].ids, ['9007199254740993', '2'])
})
test('duplicate export clicks result in a single request and download', async () => {
  const gate = deferred(); let count = 0
  const h = harness({ exportFile: () => { count++; return gate.promise } })
  await h.bulk.load(); h.bulk.toggle(h.s.rows[0])
  const pending = h.bulk.exportSelected('pdf'); await h.bulk.exportSelected('pdf'); await h.bulk.exportSelected('xlsx')
  assert.equal(count, 1)
  gate.resolve({ code: 0, data: { contentBase64: 'JVBERg==', filename: 'p.pdf', mediaType: 'application/pdf' } })
  await pending; assert.equal(h.downloads.length, 1)
})
test('failed export retains selection, shows real error and does not download', async () => {
  const h = harness({ exportFile: async () => ({ code: 1, message: '计划已删除或无权访问' }) })
  await h.bulk.load(); h.bulk.toggle(h.s.rows[0]); await h.bulk.exportSelected('pdf')
  assert.equal(h.downloads.length, 0); assert.equal(h.s.selected.length, 1)
  assert.match(h.s.exportError, /无权/); assert.equal(h.s.exporting, '')
})
test('context change while exporting discards old response and selection', async () => {
  const gate = deferred(); const h = harness({ exportFile: () => gate.promise })
  await h.bulk.load(); h.bulk.toggle(h.s.rows[0]); const pending = h.bulk.exportSelected('pdf')
  h.bulk.reset(); gate.resolve({ code: 0, data: { contentBase64: 'JVBERg==', filename: 'p.pdf', mediaType: 'application/pdf' } })
  await pending; assert.equal(h.downloads.length, 0); assert.equal(h.s.selected.length, 0)
})
test('late list response cannot overwrite newer search results', async () => {
  const gate = deferred(); let count = 0
  const h = harness({ loadPage: () => ++count === 1 ? gate.promise : Promise.resolve(page([row(2)])) })
  const pending = h.bulk.load(); await h.bulk.load(); gate.resolve(page([row(1)])); await pending
  assert.deepEqual(h.s.rows.map(x => x.id), ['2'])
})
test('unmount and permission revocation prevent in-flight downloads', async () => {
  for (const destroy of [true, false]) {
    let allowed = true; const gate = deferred()
    const h = harness({ canExport: () => allowed, exportFile: () => gate.promise })
    await h.bulk.load(); h.bulk.toggle(h.s.rows[0]); const pending = h.bulk.exportSelected('pdf')
    if (destroy) h.bulk.destroy(); else allowed = false
    gate.resolve({ code: 0, data: { contentBase64: 'JVBERg==', filename: 'p.pdf', mediaType: 'application/pdf' } })
    await pending; assert.equal(h.downloads.length, 0)
  }
})
test('selection limit is enforced atomically and current-page removal is isolated', async () => {
  const h = harness({ loadPage: async ({ page: p }) => page(Array.from({ length: 50 }, (_, i) => row((p - 1) * 50 + i + 1)), true) })
  await h.bulk.load(1); h.bulk.togglePage(); await h.bulk.load(2); h.bulk.togglePage()
  assert.equal(h.s.selected.length, 100)
  await h.bulk.load(3); h.bulk.togglePage(); assert.equal(h.s.selected.length, 100)
  h.bulk.toggle(h.s.rows[0]); assert.equal(h.s.selected.length, 100)
  await h.bulk.load(1); h.bulk.togglePage(); assert.equal(h.s.selected.length, 50)
  assert(h.s.selected.every(x => Number(x.id) > 50))
})
test('list failure is not an empty-success state and blocks stale export', async () => {
  let fail = false; const h = harness({ loadPage: async () => fail ? { code: 1, message: '权限服务异常' } : page([row(1)]) })
  await h.bulk.load(); h.bulk.toggle(h.s.rows[0]); fail = true; await h.bulk.load()
  assert.match(h.s.error, /权限服务/); assert.equal(h.s.rows.length, 0); assert.equal(h.s.selected.length, 1)
  await h.bulk.exportSelected('pdf'); assert.equal(h.calls.length, 0)
})
test('wrong MIME or URL response cannot download arbitrary content', async () => {
  for (const data of [{}, { contentBase64: 'x', filename: 'x.html', mediaType: 'text/html' },
    { contentBase64: 'JVBERg==', filename: 'p.pdf', mediaType: 'application/pdf', url: 'https://invalid.example/' }]) {
    const h = harness({ exportFile: async () => ({ code: 0, data }) })
    await h.bulk.load(); h.bulk.toggle(h.s.rows[0]); await h.bulk.exportSelected('pdf')
    assert.equal(h.downloads.length, 0); assert.match(h.s.exportError, /返回异常/)
  }
})
test('no permission means no list request', async () => {
  let calls = 0; const h = harness({ canExport: () => false, loadPage: async () => { calls++; return page([]) } })
  await h.bulk.load(); assert.equal(calls, 0); assert.equal(h.s.selected.length, 0)
})
