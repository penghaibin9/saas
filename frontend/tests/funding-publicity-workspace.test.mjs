import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/modules/studentAffairs/views/funding/FundingPublicityView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
function method(name, next) {
  const start = source.indexOf(`    async ${name}`), end = source.indexOf(`\n    ${next}`, start)
  assert.ok(start >= 0 && end > start)
  return source.slice(source.indexOf('{', start + `    async ${name}`.length) + 1, end).replace(/\n {4}\},$/, '')
}
const load = new AsyncFunction('studentAffairsApi', method('load()', 'openScan'))
const submit = new AsyncFunction('studentAffairsApi', 'toast', method('submitConfirmation()', 'typeLabel'))
const data = (items, total, statusCounts = {}) => ({ code: 0, data: { items, total, statusCounts } })
test('publicity preserves server totals and newer scope results when requests finish out of order', async () => {
  const pending = [], vm = { loadSeq: 0, page: 2, pageSize: 20, batchId: '9' }
  const api = { getFundingApplications: p => new Promise(resolve => pending.push({ p, resolve })) }
  const first = load.call(vm, api); vm.batchId = '10'
  const second = load.call(vm, api)
  pending[1].resolve(data([{ applicationId: '88' }], 301, { COUNSELOR_REVIEW: 4, GRANTED: 2 })); await second
  pending[0].resolve(data([], 0)); await first
  assert.equal(pending[0].p.page, 2); assert.equal(pending[0].p.pageSize, 20)
  assert.equal(vm.total, 301); assert.equal(vm.items[0].applicationId, '88'); assert.equal(vm.statusCounts.COUNSELOR_REVIEW, 4)
  assert.equal(vm.loading, false)
})
test('an emptied last page returns to an existing page and query failure stays an error', async () => {
  const vm = { loadSeq: 0, page: 3, pageSize: 20 }, pages = []
  const api = { getFundingApplications: async p => { pages.push(p.page); return data(p.page === 3 ? [] : [{ applicationId: '40' }], 40) } }
  vm.load = () => load.call(vm, api)
  await vm.load(); assert.deepEqual(pages, [3, 2]); assert.equal(vm.items[0].applicationId, '40')
  api.getFundingApplications = async () => { throw new Error('网络暂不可用') }
  await vm.load(); assert.match(vm.errorMessage, /网络暂不可用/); assert.equal(vm.loading, false)
})
test('publicity confirmation freezes the reviewed batch, reports partial failures and prevents duplicate submission', async () => {
  let resolve; const calls = [], vm = { busy: false, batchId: 'new', dialog: { visible: true, kind: 'scan', batchId: 'reviewed' }, load: async () => {} }
  const api = { scanFundingPublicity: id => { calls.push(id); return new Promise(r => { resolve = r }) } }
  const first = submit.call(vm, api, { error: assert.fail }); await submit.call(vm, api, { error: assert.fail })
  assert.deepEqual(calls, ['reviewed']); resolve({ code: 0, data: { count: 2, quotaConflict: 1, skippedAppeal: 3 } }); await first
  assert.match(vm.scanResult, /已确认 2 人/); assert.match(vm.scanResult, /额度冲突 1 人/)
  assert.equal(vm.dialog.visible, false); assert.equal(vm.busy, false)
})
test('a single confirmation retains the inspected version and stays open after conflict', async () => {
  const vm = { busy: false, dialog: { visible: true, kind: 'single', row: { applicationId: '12', version: 7, allowedActions: ['PUBLICITY_CONFIRM'] } }, load: assert.fail }
  const errors = []
  await submit.call(vm, { confirmFundingPublicity: async (...args) => { assert.deepEqual(args, ['12', 7]); return { code: 409, message: '申请已有变化' } } }, { error: e => errors.push(e) })
  assert.equal(vm.dialog.visible, true); assert.equal(vm.busy, false); assert.match(errors[0], /已有变化/)
})
