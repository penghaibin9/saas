import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/AttendanceView.vue', import.meta.url), 'utf8')).descriptor.script.content
  .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?ActionReceipt \},\r?\n/, '')
  .replace('export default', 'return')
function view(api = {}, downloads = {}) {
  const def = new Function('attendanceApi', 'emptyConflict', 'guidanceVisitApi', script)(api, () => ({}), downloads)
  const vm = { ...def.data(), batchStore: { selectedBatchId: '7' } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) if (key !== 'batchStore') Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  vm.changeMakeupRoute = def.watch['$route.query.makeupId'].handler.bind(vm)
  return vm
}
test('attendance exposes all returned rows without a separate three-record preview', async () => {
  const rows = Array.from({ length: 8 }, (_, id) => ({ id: String(id) }))
  const vm = view({ getCheckins: async () => ({ code: 0, data: { list: rows, total: 8 } }) })
  await vm.load(); assert.deepEqual(vm.rows, rows); assert.equal(vm.total, 8)
  assert.equal(vm.tableColumns.some(c => c.key === 'actions'), false)
})
test('late attendance response cannot overwrite a newer selected tab', async () => {
  let resolve
  const vm = view({ getCheckins: () => new Promise(done => { resolve = done }), getExceptions: async () => ({ code: 0, data: { list: [{ id: 'new' }], total: 1 } }) })
  const old = vm.load(); vm.tab = 'exceptions'; await vm.load()
  resolve({ code: 0, data: { list: [{ id: 'old' }], total: 50 } }); await old
  assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.total, 1); assert.equal(vm.tabTotals.checkins, null)
})


test('makeup detail navigation preserves exact identity and list context', () => {
  const vm = view(); const calls = []; vm.$route = { path: '/admin/internship/attendance', query: { panel: 'makeup-review', batchId: '7', page: '2', keyword: '测试' } }; vm.$router = { push: q => calls.push(q) }
  vm.openMakeupDetail({ id: '9007199254740999' }); assert.equal(calls[0].query.makeupId, '9007199254740999')
  vm.$route.query = calls[0].query; vm.closeMakeupDetail(false)
  assert.equal(calls[1].query.makeupId, undefined); assert.equal(calls[1].query.page, '2'); assert.equal(calls[1].query.keyword, '测试')
})

test('makeup confirmation cannot submit twice or resubmit a conflicted snapshot', async () => {
  const vm = view({ approveMakeup: () => assert.fail('must not approve') })
  vm.pending = { kind: 'approve', id: '1', expectedVersion: 1 }; vm.dlg.submitting = true
  await vm.onConfirm({ reason: '' }); vm.dlg.submitting = false; vm.conflict.active = true
  await vm.onConfirm({ reason: '' })
})

test('batch reset clears old makeup identity, receipt, counters and list page', async () => {
  const vm = view(); const calls = []
  vm.$route = { path: '/admin/internship/attendance', query: { panel: 'makeup-review', batchId: '8', makeupId: '1' } }; vm.$router = { replace: q => calls.push(q) }; vm.load = () => {}
  vm.makeupDetail = { visible: true, id: '1', data: { id: '1' } }; vm.pending = { id: '1' }; vm.lastReceipt = { id: '1' }; vm.tabTotals.checkins = 50; vm.page = 4
  vm.resetBatchView()
  assert.equal(vm.makeupDetail.data, null); assert.equal(vm.pending, null); assert.equal(vm.lastReceipt, null)
  assert.equal(vm.tabTotals.checkins, null); assert.equal(vm.page, 1); assert.equal(calls[0].query.makeupId, undefined)
})
test('makeup approval checks the makeup permission before preparing or submitting', async () => {
  const vm = view({ approveMakeup: () => assert.fail('must not submit') }); const checked = []
  vm.canBtn = code => { checked.push(code); return false }
  vm.openApprove({ id: '1', status: 'PENDING' }); assert.equal(vm.pending, null)
  vm.pending = { id: '1', kind: 'approve' }; await vm.onConfirm({ reason: '' })
  assert.deepEqual(checked, ['internship.makeup.review', 'internship.makeup.review'])
})


test('makeup attachment download cannot mark or replace a newly selected request', async () => {
  let finish
  const vm = view({ markMakeupEvidenceViewed: () => assert.fail('old download must not mark new selection') }, { downloadAttachment: () => new Promise(resolve => { finish = resolve }) })
  vm.makeupDetail.data = { id: 'old', attachment: { fileId: 'file', fileName: '证明' } }
  const downloading = vm.downloadMakeupEvidence()
  const current = { id: 'new', evidenceViewed: false }; vm.makeupDetail.data = current
  finish(); await downloading
  assert.equal(vm.makeupDetail.data, current)
})

test('late makeup evidence acknowledgement does not replace a new detail', async () => {
  let finish
  const vm = view({ markMakeupEvidenceViewed: () => new Promise(resolve => { finish = resolve }) }, { downloadAttachment: async () => {} })
  vm.makeupDetail.data = { id: 'old', attachment: { fileId: 'file' } }
  const downloading = vm.downloadMakeupEvidence(); await Promise.resolve()
  const current = { id: 'new', evidenceViewed: false }; vm.makeupDetail.data = current
  finish({ code: 0 }); await downloading
  assert.equal(vm.makeupDetail.data, current)
})


test('continuing makeup review opens the next evidence workspace before any decision', () => {
  const vm = view(); const next = { id: '9007199254740999' }; let opened
  vm.nextUp = { row: next, kind: 'reject' }; vm.openMakeupDetail = row => { opened = row }
  vm.openApprove = vm.openReject = () => assert.fail('must read next evidence first')
  vm.openNextUp(); assert.equal(opened, next); assert.equal(vm.nextUp, null)
})

test('makeup deep-link change closes the old decision and clears old object receipt', () => {
  const vm = view(); vm.pending = { id: 'old' }; vm.dlg.visible = true; vm.conflict.active = true
  vm.lastReceipt = { id: 'old' }; vm.loadMakeupDetail = () => {}
  vm.changeMakeupRoute('new')
  assert.equal(vm.pending, null); assert.equal(vm.dlg.visible, false); assert.equal(vm.lastReceipt, null)
  assert.equal(vm.makeupDetail.id, 'new')
})

test('reopening the same makeup does not accept a response from its previous workspace', async () => {
  let finish
  const vm = view({ getMakeupDetail: () => new Promise(resolve => { finish = resolve }) })
  vm.makeupDetail = { id: '1', data: null }; const old = vm.loadMakeupDetail('1')
  const current = { id: '1', data: { version: 2 } }; vm.makeupDetail = current
  finish({ code: 0, data: { version: 1 } }); await old
  assert.equal(vm.makeupDetail, current); assert.equal(current.data.version, 2)
})
