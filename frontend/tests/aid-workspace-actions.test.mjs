import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const base = '../src/modules/studentAffairs/views/'
const read = path => readFileSync(new URL(base + path, import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
function method(source, name, next) {
  const start = source.indexOf(`    async ${name}`)
  const end = source.indexOf(`\n    ${next}`, start)
  assert.ok(start >= 0 && end > start)
  return source.slice(source.indexOf('{', start) + 1, end).replace(/\n {4}\},$/, '')
}
const publish = new AsyncFunction('studentAffairsApi', 'toast', 'row', method(read('aid/AidBatchView.vue'), 'publish(row)', 'statusLabel'))
const publicityLoad = new AsyncFunction('studentAffairsApi', method(read('aid/AidPublicityView.vue'), 'load()', 'async scan'))
const batchesLoad = new AsyncFunction('studentAffairsApi', method(read('AidWorkbenchView.vue'), 'loadBatches()', 'onBatchChange'))

test('draft publication sends the observed version once, and uncertainty never auto-publishes again', async () => {
  let resolve
  const calls = [], messages = []
  const vm = { publishingId: '', saving: false, load: async () => calls.push('reload') }
  const api = { publishAidBatch: (...args) => { calls.push(args); return new Promise(r => { resolve = r }) } }
  const toast = { success: text => messages.push(text), error: text => messages.push(text) }
  const row = { batchId: '5', version: 3 }
  const first = publish.call(vm, api, toast, row)
  await publish.call(vm, api, toast, row)
  assert.deepEqual(calls, [['5', 3]])
  resolve({ code: 0 }); await first
  assert.deepEqual(calls, [['5', 3], 'reload'])
  assert.equal(vm.publishingId, '')
  api.publishAidBatch = async () => { throw new Error('offline') }
  await publish.call(vm, api, toast, row)
  assert.match(messages.at(-1), /刷新核对/)
  assert.equal(vm.publishingId, '')
})

test('publicity cards show server totals beyond 200 and use unknown instead of zero for a failed metric', async () => {
  const vm = { loadSeq: 0, pagination: { page: 3, pageSize: 20 } }
  const calls = []
  await publicityLoad.call(vm, { getAidApplications: async params => {
    calls.push(params)
    return params.level === 'DIFFICULT' ? { code: 500 } : { code: 0, data: { total: params.level ? 350 : 700, items: [{ applyId: '1' }] } }
  } })
  assert.equal(vm.pagination.total, 700)
  assert.deepEqual(vm.levelTotals, { SPECIAL: 350, DIFFICULT: null })
  assert.equal(vm.loading, false)
  assert.equal(calls[1].pageSize, 1)
  assert.equal(calls[2].pageSize, 1)
})

test('a historical record opens its actual batch even outside the first picker page, and never falls back after denial', async () => {
  const calls = []
  const vm = { batchId: '101', loadApplications: async () => calls.push('applications:101'), consumeRouteIntent() {} }
  const api = {
    getAidBatches: async () => ({ code: 0, data: { items: [{ batchId: '200', status: 'OPEN' }] } }),
    getAidBatch: async id => { calls.push(id); return { code: 0, data: { batchId: id } } }
  }
  await batchesLoad.call(vm, api)
  assert.deepEqual(calls, ['101', 'applications:101'])
  assert.equal(vm.batchId, '101')
  assert.equal(vm.batches.at(-1).batchId, '101')
  calls.length = 0
  vm.pagination = { total: 3 }
  api.getAidBatch = async () => ({ code: 403, message: '该批次不可见' })
  await batchesLoad.call(vm, api)
  assert.equal(vm.batchId, '101')
  assert.deepEqual(calls, [])
  assert.deepEqual(vm.list, [])
  assert.match(vm.listError, /不可见/)
})
