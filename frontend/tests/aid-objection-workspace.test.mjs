import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/modules/studentAffairs/views/aid/AidObjectionView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
function method(name, next) {
  const start = source.indexOf(`    async ${name}`), end = source.indexOf(`\n    ${next}`, start)
  assert.ok(start >= 0 && end > start)
  return source.slice(source.indexOf('{', start + `    async ${name}`.length) + 1, end).replace(/\n {4}\},$/, '')
}
const load = new AsyncFunction('studentAffairsApi', method('load()', 'setStatus'))
const review = new AsyncFunction('reviewAidObjectionVersioned', 'toast', '{ reason }', method('submitReview({ reason })', 'levelLabel'))
test('independent page controls use server totals; a failed objection list is not presented as empty', async () => {
  const vm = { loadSeq: 0, objStatus: 'CLOSED', publicityPage: { page: 2, pageSize: 10 }, objectionPage: { page: 11, pageSize: 20 } }
  const calls = []
  const api = { getAidApplications: async p => { calls.push(p); return { code: 0, data: { items: [], total: 305 } } }, getAidObjections: async p => { calls.push(p); return { code: 0, data: { items: [{ objectionId: '201' }], total: p.status === 'SUBMITTED' ? 75 : 400 } } } }
  await load.call(vm, api)
  assert.equal(vm.publicityPage.total, 305); assert.equal(vm.objectionPage.total, 400)
  assert.equal(calls[0].page, 2); assert.equal(calls[1].page, 11)
  assert.deepEqual(vm.statusCounts, { SUBMITTED: 75, CLOSED: 400 })
  api.getAidObjections = async () => ({ code: 500, message: '服务暂不可用' })
  await load.call(vm, api)
  assert.match(vm.errorMessage, /服务暂不可用/); assert.equal(vm.loading, false)
})
test('review sends the observed version once and retains the decision when the server rejects it', async () => {
  let resolve; const calls = [], messages = []
  const vm = { acting: '', revDlg: { visible: true, objectionId: '7', result: 'OVERRULED', version: 4 }, load: () => assert.fail('failed review must not silently reload') }
  const api = (...args) => { calls.push(args); return new Promise(r => { resolve = r }) }
  const toast = { error: message => messages.push(message), success: () => {} }
  const first = review.call(vm, api, toast, { reason: '已核实申请信息' })
  await review.call(vm, api, toast, { reason: '已核实申请信息' })
  assert.deepEqual(calls, [['7', 'OVERRULED', '已核实申请信息', 4]])
  resolve({ code: 409, message: '记录已更新，请刷新核对' }); await first
  assert.equal(vm.revDlg.visible, true); assert.equal(vm.acting, '')
  assert.match(messages[0], /记录已更新/)
})
