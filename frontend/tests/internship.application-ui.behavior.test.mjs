import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { pickNextPending, anchorIndexOf } from '../src/modules/internship/composables/reviewQueue.js'
import { emptyConflict, captureConflict, isConflict } from '../src/modules/internship/composables/conflictGuard.js'

const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipApplicationReviewView.vue', import.meta.url), 'utf8')).descriptor.script.content
  .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?\},\r?\n/, '')
  .replace('export default', 'return')

function view(api = {}) {
  const batch = { selectedBatchId: '7', withBatchQuery: query => ({ ...query, batchId: '7' }) }
  const def = new Function('internshipApplicationApi', 'useInternshipBatchStore', 'emptyConflict', 'REJECT_APPLICATION', 'toast', 'pickNextPending', 'anchorIndexOf', 'captureConflict', 'isConflict', 'canCode', script)(api, () => batch, emptyConflict, [], { success() {} }, pickNextPending, anchorIndexOf, captureConflict, isConflict, ctx => ctx?.review === true)
  const calls = []
  const vm = { ...def.data(), $route: { path: '/admin/internship/applications', query: { id: '9007199254740997', type: 'SELF_ARRANGED', status: 'PENDING_REVIEW', keyword: '测试', page: '3', batchId: '7' } }, $router: { push: to => calls.push(to), replace: to => calls.push(to) } }
  for (const [name, method] of Object.entries(def.methods)) vm[name] = method.bind(vm)
  for (const [name, getter] of Object.entries(def.computed)) Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  vm.ctx = { review: true }
  return { vm, calls, batch }
}

function ready(api = {}) {
  const state = view(api)
  state.vm.drawer = { id: '31', visible: true, loading: false, error: '', data: { id: '31', studentName: '虚构学生', status: 'PENDING_REVIEW', version: 2, recordVersion: 4 } }
  state.vm.askReview('REJECT')
  return state
}

test('review freezes both versions and prevents a duplicate submission', async () => {
  let resolve; const requests = []
  const { vm } = ready({ review: (id, payload) => { requests.push({ id, payload }); return new Promise(done => { resolve = done }) } })
  vm.advanceAfterReview = async () => {}
  vm.drawer.data.version = 8; vm.drawer.data.recordVersion = 9
  const first = vm.submitReview({ reason: '请补齐证明材料' })
  await vm.submitReview({ reason: '请补齐证明材料' })
  assert.equal(requests.length, 1)
  assert.deepEqual(requests[0].payload, { action: 'REJECT', comment: '请补齐证明材料', expectedVersion: 2, recordExpectedVersion: 4 })
  resolve({ code: 0, data: { status: 'REJECTED' } }); await first
  assert.equal(vm.drawer.data.status, 'REJECTED'); assert.equal(vm.confirm.visible, false)
})

test('conflict cannot use fresh versions until the teacher explicitly acknowledges the latest record', async () => {
  const requests = []
  const { vm } = ready({
    review: async (id, payload) => { requests.push(payload); return requests.length === 1 ? { code: 409001, message: '记录已变化' } : { code: 0, data: { status: 'REJECTED' } } },
    getDetail: async () => ({ code: 0, data: { id: '31', status: 'PENDING_REVIEW', version: 7, recordVersion: 9 } })
  })
  vm.advanceAfterReview = async () => {}
  await vm.submitReview({ reason: '请补齐证明材料' })
  assert.equal(vm.conflict.active, true); assert.equal(vm.conflict.stale, false)
  assert.equal(vm.confirm.snapshot.expectedVersion, 2)
  await vm.submitReview({ reason: '请补齐证明材料' }); assert.equal(requests.length, 1)
  vm.acceptLatestReview(); assert.equal(requests.length, 1)
  await vm.submitReview({ reason: '请补齐证明材料' })
  assert.equal(requests[1].expectedVersion, 7); assert.equal(requests[1].recordExpectedVersion, 9)
  assert.equal(requests[1].comment, requests[0].comment)
})

test('an already processed application remains locked after conflict recovery', async () => {
  let writes = 0
  const { vm } = ready({ review: async () => { writes++; return { code: 409001 } }, getDetail: async () => ({ code: 0, data: { id: '31', status: 'APPROVED', version: 7 } }) })
  await vm.submitReview(); vm.acceptLatestReview(); await vm.submitReview()
  assert.equal(writes, 1); assert.equal(vm.conflict.active, true)
})

test('failed conflict reread preserves the block and offers a later reread', async () => {
  let reads = 0
  const { vm } = ready({ review: async () => ({ code: 409001 }), getDetail: async () => { if (++reads === 1) throw new Error('网络中断'); return { code: 0, data: { id: '31', status: 'PENDING_REVIEW', version: 7, recordVersion: 9 } } } })
  await vm.submitReview(); vm.acceptLatestReview()
  assert.equal(vm.conflict.stale, true); assert.equal(vm.confirm.snapshot.expectedVersion, 2)
  await vm.readReviewConflict(); assert.equal(vm.conflict.stale, false)
  assert.equal(vm.conflict.active, true); assert.equal(vm.confirm.snapshot.expectedVersion, 2)
})

test('a failed review keeps the confirmation open and exposes an inline error', async () => {
  const { vm } = ready({ review: async () => { throw new Error('网络中断') } })
  await vm.submitReview({ reason: '请补齐证明材料' })
  assert.equal(vm.confirm.visible, true); assert.equal(vm.confirm.submitting, false)
  assert.equal(vm.reviewError, '网络中断')
})

test('changing batch discards an old review result', async () => {
  let resolve, advances = 0
  const { vm, batch } = ready({ review: () => new Promise(done => { resolve = done }) })
  vm.advanceAfterReview = async () => { advances++ }
  const request = vm.submitReview()
  batch.selectedBatchId = '8'; vm.load = () => {}; vm.loadDetail = () => {}; vm.restoreLocation()
  const replacement = vm.confirm
  resolve({ code: 0, data: { status: 'REJECTED' } }); await request
  assert.equal(advances, 0); assert.equal(vm.confirm, replacement); assert.equal(vm.drawer.data, null)
})

test('lost review permission and unsupported actions cannot submit', async () => {
  let writes = 0
  const { vm } = ready({ review: async () => { writes++; return { code: 0 } } })
  vm.ctx.review = false; await vm.submitReview(); assert.equal(writes, 0)
  vm.confirm.visible = false; vm.askReview('APPROVE'); assert.equal(vm.confirm.visible, false)
  vm.ctx.review = true; vm.askReview('DELETE'); assert.equal(vm.confirm.visible, false)
})

test('queue read failure keeps the real review result and does not imply an empty queue', async () => {
  const { vm, calls } = ready({ review: async () => ({ code: 0, data: { id: '31', status: 'REJECTED' } }), getApplications: async () => { throw new Error('队列读取失败') } })
  await vm.submitReview({ reason: '请补齐证明材料' })
  assert.equal(vm.drawer.data.status, 'REJECTED'); assert.equal(vm.queueError, '队列读取失败')
  assert.equal(vm.confirm.visible, false); assert.equal(calls.length, 0)
})

test('direct application deep link restores its object and list context on initial load', () => {
  const { vm } = view(); let loaded
  vm.load = () => {}; vm.loadDetail = id => { loaded = id }
  vm.restoreLocation()
  assert.equal(vm.isDetail, true); assert.equal(loaded, '9007199254740997')
  assert.equal(vm.drawer.id, loaded); assert.equal(vm.page, 3); assert.equal(vm.applicationType, 'SELF_ARRANGED')
})

test('returning from application review retains filters and removes the detail ID', () => {
  const { vm, calls } = view(); vm.load = () => {}; vm.loadDetail = () => {}; vm.restoreLocation(); vm.backToList()
  assert.deepEqual(calls[0], { path: '/admin/internship/applications', query: { type: 'SELF_ARRANGED', status: 'PENDING_REVIEW', keyword: '测试', page: 3, batchId: '7' } })
})

test('a late application response cannot replace a newly opened object', async () => {
  let resolve
  const pending = new Promise(done => { resolve = done })
  const { vm } = view({ getDetail: () => pending })
  vm.drawer.id = 'old'
  const load = vm.loadDetail('old')
  vm.drawer = { id: 'new', data: { id: 'new' } }; vm.detailTicket++
  resolve({ code: 0, data: { id: 'old' } }); await load
  assert.equal(vm.drawer.data.id, 'new')
})

test('continuous review updates the deep link to the next exact application', async () => {
  const { vm, calls } = view(); vm.load = () => {}; vm.loadDetail = () => {}; vm.restoreLocation()
  vm.rows = [{ id: 'old', status: 'PENDING_REVIEW' }, { id: 'next', status: 'PENDING_REVIEW' }]
  vm.load = async () => { vm.rows = [{ id: 'next', status: 'PENDING_REVIEW' }] }
  await vm.advanceAfterReview('old')
  assert.equal(calls[0].query.id, 'next'); assert.equal(calls[0].query.page, 3); assert.equal(calls[0].query.batchId, '7')
})

test('failed detail loading clears previous object information', async () => {
  const { vm } = view({ getDetail: async () => ({ code: 403, message: '无权查看该申请' }) })
  vm.drawer = { id: 'denied', data: { studentName: '上一对象' } }
  await vm.loadDetail('denied')
  assert.equal(vm.drawer.data, null); assert.equal(vm.drawer.error, '无权查看该申请')
})
