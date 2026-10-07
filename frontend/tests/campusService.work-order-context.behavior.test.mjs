import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const parsed = parse(readFileSync(new URL('../src/modules/campusService/views/WorkOrderView.vue', import.meta.url), 'utf8'))
assert.deepEqual(parsed.errors, [])
const script = parsed.descriptor.script.content.replace(/^import .*$/gm, '')
  .replace(/^ {2}components:.*$/m, '').replace('export default', 'return')
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const order = id => ({ order: { id, allowedActions: ['handle', 'complete'], version: 3 } })
function mount(api) {
  const def = new Function('workOrderApi', 'currentSessionGeneration', 'normalizeUiError', script)(api, () => 1, e => ({ pageState: 'error', userMessage: e.message }))
  const page = { ...def.data(), $route: { query: { recordId: 'A' } } }
  for (const [key, method] of Object.entries(def.methods)) page[key] = method.bind(page)
  Object.defineProperty(page, 'recordId', { get: () => def.computed.recordId.call(page) })
  return { page, def }
}

test('a saved previous work order cannot erase the next order draft or show its receipt', async () => {
  const save = deferred()
  const { page } = mount({ handle: () => save.promise, detail: async id => order(id) })
  page.detail = order('A'); page.note = 'First order processing note'
  const pending = page.submit(false)
  page.$route.query.recordId = 'B'; await page.loadDetail(); page.note = 'Unsaved draft for B'
  save.resolve(); await pending
  assert.equal(page.detail.order.id, 'B')
  assert.equal(page.note, 'Unsaved draft for B')
  assert.equal(page.notice, '')
  assert.equal(page.submitting, false)
})

test('a previous work order failure does not appear on the next order', async () => {
  const save = deferred()
  const { page } = mount({ handle: () => save.promise, detail: async id => order(id) })
  page.detail = order('A'); page.note = 'First order processing note'
  const pending = page.submit(false)
  page.$route.query.recordId = 'B'; await page.loadDetail()
  save.reject(new Error('Previous order conflict')); await pending
  assert.equal(page.actionError, '')
  assert.equal(page.submitting, false)
})

test('leaving detail invalidates the pending response even if the same order is reopened', async () => {
  const old = deferred(); let calls = 0
  const { page, def } = mount({ detail: () => ++calls === 1 ? old.promise : Promise.resolve(order('A-new')), list: async () => ({ items: [], total: 0 }) })
  const pending = page.loadDetail()
  page.$route.query = {}; def.watch['$route.query'].handler.call(page)
  old.resolve(order('A-old')); await pending
  assert.equal(page.detail, null)
  page.$route.query = { recordId: 'A' }; await page.loadDetail()
  assert.equal(page.detail.order.id, 'A-new')
})

test('successful current-order submission rereads its new server version', async () => {
  const { page } = mount({ handle: async () => ({}), detail: async id => ({ order: { ...order(id).order, version: 4 } }) })
  page.detail = order('A'); page.note = 'Current order processing note'
  await page.submit(false)
  assert.equal(page.detail.order.version, 4)
  assert.equal(page.note, '')
  assert.ok(page.notice)
})
