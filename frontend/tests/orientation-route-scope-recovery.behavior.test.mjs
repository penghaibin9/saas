import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { restoreOrientationBatch } from '../src/modules/orientation/routeContext.js'

const ok = (id) => ({ code: 0, data: { list: [{ id }], total: 1 } })
const pending = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const cases = [
  ['PaymentGreenChannelView', 'getPaymentStatusList'],
  ['OrientationQualificationView', 'getOrientationQualifications'],
  ['DormCheckinView', 'getDormitoryCheckinList']
]
function screen(name, api) {
  const text = readFileSync(new URL(`../src/views/admin/orientation/${name}.vue`, import.meta.url), 'utf8')
  const names = []
  const script = parse(text).descriptor.script.content
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, imports) => { names.push(...imports.split(',').map(value => value.trim())); return '' })
    .replace('export default', 'return')
  const messages = []
  const deps = { toast: { error: value => messages.push(value), success: value => messages.push(value) }, toLabelMap: () => ({}) }
  const component = new Function('api', ...names, script)(api, ...names.map(key => deps[key] || {}))
  const view = { $route: { path: '/admin/orientation/payment', query: { batchId: '9007199254740993', orientationStudentId: '7' } } }
  Object.assign(view, component.data.call(view))
  for (const [key, fn] of Object.entries(component.methods)) view[key] = fn.bind(view)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(view, key, { get: fn.bind(view) })
  return { view, component, messages, change: query => { view.$route.query = query; return component.watch.routeContextKey.handler.call(view) } }
}
for (const [name, method] of cases) {
  test(`${name}: query-only context switch clears student rows and dialogs before the next response`, async () => {
    const next = pending(), calls = []
    const state = screen(name, { [method]: args => { calls.push(args); return next.promise } })
    const v = state.view
    Object.assign(v, { rows: [{ id: 'old' }], total: 9, page: 4, filters: { keyword: '旧学生' }, auditVisible: true, credentialVisible: true, credential: { temporaryPassword: 'synthetic-only' } })
    const loading = state.change({ batchId: '9007199254740995' })
    assert.deepEqual(v.rows, []); assert.equal(v.total, 0); assert.equal(v.page, 1)
    assert.equal(calls[0].batchId, '9007199254740995'); assert.equal(calls[0].orientationStudentId, undefined)
    assert.equal(calls[0].keyword, '')
    if (name === 'OrientationQualificationView') { assert.equal(v.credential, null); assert.equal(v.credentialVisible, false) }
    else assert.equal(v.auditVisible, false)
    next.resolve(ok('new')); await loading
    assert.equal(v.rows[0].id, 'new'); assert.equal(v.loading, false)
  })
  for (const outcome of ['success', 'failure']) {
    test(`${name}: former student's late ${outcome} cannot replace current data`, async () => {
      const old = pending(); let count = 0
      const state = screen(name, { [method]: () => ++count === 1 ? old.promise : Promise.resolve(ok('new')) })
      const loading = state.view.load()
      await state.change({ batchId: '9007199254740993' })
      if (outcome === 'success') old.resolve(ok('old')); else old.reject(new Error('旧请求失败'))
      await loading
      assert.equal(state.view.rows[0].id, 'new'); assert.equal(state.view.error, ''); assert.equal(state.view.loading, false)
    })
  }
  test(`${name}: unmount invalidates pending reads and prevents follow-up loads`, async () => {
    const request = pending(); let calls = 0
    const state = screen(name, { [method]: () => { calls++; return request.promise } })
    const loading = state.view.load(); state.component.beforeUnmount.call(state.view)
    request.resolve(ok('old')); await loading; await state.view.load()
    assert.deepEqual(state.view.rows, []); assert.equal(calls, 1)
  })
  test(`${name}: failed current read is an error rather than empty success`, async () => {
    const state = screen(name, { [method]: async () => { throw new Error('本批次读取失败') } })
    await state.change({ batchId: '9', orientationStudentId: '8' })
    assert.equal(state.view.error, '本批次读取失败'); assert.deepEqual(state.view.rows, []); assert.equal(state.view.total, 0)
  })
  test(`${name}: context change is blocked while its formal write is in flight`, () => {
    const state = screen(name, {})
    Object.assign(state.view, { submitting: true, activating: true })
    const permitted = state.component.beforeRouteUpdate.call(state.view, { query: { batchId: '2' } }, { query: { batchId: '1' } })
    assert.equal(permitted, false); assert.equal(state.messages.length, 1)
  })
}
test('payment green tab uses the same scoped late-response protections', async () => {
  const calls = []
  const state = screen('PaymentGreenChannelView', { getGreenChannelApplications: async args => { calls.push(args); return ok('green') } })
  await state.change({ batchId: '8', orientationStudentId: '9', tab: 'green' })
  assert.equal(calls[0].orientationStudentId, '9'); assert.equal(state.view.rows[0].id, 'green')
})
test('a late credential reply cannot reveal a former student after the context was invalidated', async () => {
  const request = pending()
  const state = screen('OrientationQualificationView', { activateOrientationIdentity: () => request.promise, getOrientationQualifications: async () => ok('new') })
  Object.assign(state.view, { activateRow: { id: '7', version: 1 }, activateStudentNo: 'TEST-7', activateRequestId: 'test-request' })
  const saving = state.view.onActivateConfirm()
  await state.change({ batchId: '9', orientationStudentId: '8' })
  request.resolve({ code: 0, data: { initialCredential: { temporaryPassword: 'synthetic-only' } } }); await saving
  assert.equal(state.view.credential, null); assert.equal(state.view.credentialVisible, false); assert.deepEqual(state.messages, [])
})
test('restored workspace tabs drop the old student but explicit detail navigation retains it', () => {
  const storage = { getItem: () => '9007199254740995' }
  const source = '/admin/orientation/payment?batchId=1&orientationStudentId=7&tab=green'
  const restored = new URL(restoreOrientationBatch(source, storage, 'test-identity', true), 'https://example.invalid')
  assert.equal(restored.searchParams.get('batchId'), '9007199254740995')
  assert.equal(restored.searchParams.has('orientationStudentId'), false)
  assert.equal(restored.searchParams.get('tab'), 'green')
  assert.equal(restoreOrientationBatch(source, storage, 'test-identity'), source)
})
