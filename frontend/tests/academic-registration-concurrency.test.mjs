import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { academicReturnPath } from '../src/modules/academicAffairs/academicFlowContext.js'
import { academicStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'

const source = name => readFileSync(new URL(`../src/modules/academicAffairs/${name}`, import.meta.url), 'utf8')
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function panel(api = {}, extra = {}, path = 'components/AaRegistrationBulkPanel.vue') {
  const script = source(path).match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`).replace('export default', 'component =')
  const sandbox = { dependencies: { matchPermission, academicStatusLabel, rosterRegistrationConvenienceApi: api, academicAffairsApi: api, toast: { info() {}, error() {}, success() {} } } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, batchId: 'batch-a', batchState: 'OPEN', ctx: { permissionPatterns: ['academicAffairs.registration.manage'], dataScope: { scope: 'SCHOOL' } }, $route: { query: {} }, $router: { push() {}, replace() {} }, $emit() {}, ...extra }
  for (const [name, value] of Object.entries(component.computed)) { const get = typeof value === 'function' ? value : value.get; Object.defineProperty(state, name, { get: () => get.call(state) }) }
  return state
}
function api(request) {
  const script = source('api/roster-registration-convenience.api.js').replace(/^import .*$/gm, '').replace('export const rosterRegistrationConvenienceApi =', 'api =')
  const sandbox = { request }; vm.runInNewContext(script, sandbox); return sandbox.api
}
function ready(state, token = 'preview-a') {
  state.selectedIds = ['student-a']; state.preview = { batchId: state.batchId, previewToken: token, ready: 1 }
  state.previewSignature = state.selectionSignature; state.reviewed = true
}

test('candidate response from the old batch cannot replace the new batch', async () => {
  const old = deferred()
  const state = panel({ getCandidates: id => id === 'batch-a' ? old.promise : Promise.resolve({ code: 0, data: { list: [{ studentId: 'new' }], total: 1 } }) })
  const pending = state.load(); state.batchId = 'batch-b'; await state.load()
  old.resolve({ code: 0, data: { list: [{ studentId: 'old' }], total: 1 } }); await pending
  assert.equal(state.rows[0].studentId, 'new')
})

test('changing the selected students invalidates an in-flight preview', async () => {
  const reply = deferred(); const state = panel({ previewBulkRegistration: () => reply.promise })
  state.selectedIds = ['student-a']; const pending = state.makePreview(); state.selectedIds = ['student-b']
  reply.resolve({ code: 0, data: { batchId: 'batch-a', ready: 1, previewToken: 'old' } }); await pending
  assert.equal(state.preview, null)
})

test('confirmed registration uses only the reviewed token and emits one write', async () => {
  const reply = deferred(), writes = []
  const state = panel({ confirmBulkRegistration: (...args) => { writes.push(args); return reply.promise } })
  state.load = async () => {}; ready(state)
  const pending = state.apply(); await state.apply()
  assert.deepEqual(writes, [['batch-a', 'preview-a']]); assert.equal(state.preview, null)
  reply.resolve({ code: 0, data: { batchId: 'batch-a', selected: 1, succeeded: 1, failed: 0, items: [{ studentId: 'student-a', ok: true }] } }); await pending
  assert.equal(state.result.succeeded, 1)
})

test('read-only role and changed batch cannot dispatch an earlier confirmation', async () => {
  let writes = 0; const state = panel({ confirmBulkRegistration: async () => { writes++; return { code: 0 } } })
  ready(state); state.batchId = 'batch-b'; await state.apply()
  state.batchId = 'batch-a'; ready(state); state.ctx.permissionPatterns = ['academicAffairs.registration.view']; await state.apply()
  assert.equal(writes, 0)
})

test('a conflict without whole-command zero-write evidence retains the pending command', async () => {
  const state = panel({ confirmBulkRegistration: async () => ({ code: 409001, bizCode: 'DATA_CONFLICT', message: '名单已变化' }) })
  ready(state); await state.apply()
  assert.equal(state.preview, null); assert.equal(state.unknownReceipt.batchId, 'batch-a'); assert.equal(state.commandError, '名单已变化')
})

test('a transport failure remains unknown and blocks automatic re-preview', async () => {
  let previews = 0
  const state = panel({ confirmBulkRegistration: async () => ({ code: 503002, bizCode: 'REQUEST_TIMEOUT' }), previewBulkRegistration: async () => { previews++; return { code: 0 } } })
  ready(state); await state.apply(); await state.makePreview()
  assert.equal(state.unknownReceipt.batchId, 'batch-a'); assert.equal(previews, 0)
})

test('mismatched success is unknown, and partial success preserves item failures', async () => {
  const state = panel({ confirmBulkRegistration: async () => ({ code: 0, data: { batchId: 'wrong', succeeded: 1, failed: 0 } }) })
  ready(state); await state.apply(); assert.equal(state.unknownReceipt.batchId, 'batch-a')
  const partial = panel({ confirmBulkRegistration: async () => ({ code: 0, data: { batchId: 'batch-a', selected: 2, succeeded: 1, failed: 1, items: [{ studentId: 'student-a', ok: false, message: '资格已变化' }, { studentId: 'student-b', ok: true, message: '注册成功' }] } }) })
  partial.load = async () => {}; ready(partial); partial.selectedIds.push('student-b'); partial.previewSignature = partial.selectionSignature; await partial.apply()
  assert.equal(partial.result.failed, 1); assert.equal(partial.result.items[0].message, '资格已变化')
})

test('API keeps large student identifiers exact and never takes a token from another preview', async () => {
  const calls = []; const helper = api(async (path, options) => { calls.push({ path, ...options }); return { previewToken: options.body.studentIds?.[0] || 'ok' } })
  await helper.previewBulkRegistration('same-batch', ['1000000000000033669'])
  await helper.previewBulkRegistration('same-batch', ['different-student'])
  await helper.confirmBulkRegistration('same-batch', 'first-reviewed-token')
  assert.equal(calls[0].body.studentIds[0], '1000000000000033669')
  assert.equal(calls[2].body.previewToken, 'first-reviewed-token')
  const rejected = await helper.confirmBulkRegistration('same-batch', ['not-a-token'])
  assert.notEqual(rejected.code, 0); assert.equal(calls.length, 3)
})

test('batch close binds its original object, checks permission and dispatches once', async () => {
  const reply = deferred(), writes = []
  const state = panel({ closeRegistrationBatch: id => { writes.push(id); return reply.promise } }, {}, 'views/AaRegistrationBatchListView.vue')
  state.load = async () => {}
  const row = { batchId: 'confirmed', batchName: '原批次', status: 'OPEN' }
  state.askClose(row); assert.equal(state.confirm.visible, false)
  state.ctx.permissionPatterns = ['academicAffairs.registration.archive.manage']; state.askClose(row); row.batchId = 'changed'
  const pending = state.onConfirm(); await state.onConfirm(); assert.deepEqual(writes, ['confirmed'])
  reply.resolve({ code: 0 }); await pending
})

test('batch detail captures a return token and the return path keeps registration type and page', () => {
  let destination
  const state = panel({}, { academicFlow: { captureReturn: () => 'saved' }, $router: { push: value => { destination = value } } }, 'views/AaRegistrationBatchListView.vue')
  state.goDetail({ batchId: 'batch-a' }); assert.equal(destination.query.returnToken, 'saved')
  assert.equal(academicReturnPath({ path: '/admin/academic-affairs/registration', query: { type: 'ENROLL', page: '2' } }), '/admin/academic-affairs/registration?type=ENROLL&page=2')
})
