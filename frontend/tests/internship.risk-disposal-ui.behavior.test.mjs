import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { isConflict, captureConflict, emptyConflict } from '../src/modules/internship/composables/conflictGuard.js'
const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/RiskDisposalView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?ActionReceipt, AppInlineAlert \},/, '').replace('export default', 'return')
function setup(riskApi = {}, complaintApi = {}, fileSdk = {}) {
  const def = new Function('riskApi', 'complaintApi', 'emptyConflict', 'isConflict', 'captureConflict', 'canCode', 'toast', 'fileSdk', script)(riskApi, complaintApi, emptyConflict, isConflict, captureConflict, () => true, { success() {}, error() {} }, fileSdk)
  const vm = { ...def.data(), batchStore: { selectedBatchId: '1' }, $route: { query: {} } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  return { vm, def }
}
test('risk disposal template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'RiskDisposalView.vue', id: 'disposal-ui' }).errors, [])
})
test('switching to complaint mode cannot show the old risk list or same-ID detail', async () => {
  let finishList, finishDetail
  const { vm } = setup({ getRisks: () => new Promise(r => { finishList = r }), getRiskDetail: () => new Promise(r => { finishDetail = r }) },
    { getComplaints: async () => ({ code: 0, data: { list: [{ id: '8', complaintNo: 'C8' }], total: 1 } }), getComplaintDetail: async () => ({ code: 0, data: { id: '8', complaintNo: 'C8' } }) })
  vm.selectedId = '8'; const oldList = vm.load(), oldDetail = vm.loadDetail('8')
  vm.complaintMode = true; await vm.load(); await vm.loadDetail('8')
  finishList({ code: 0, data: { list: [{ id: '8', riskCode: 'OLD' }], total: 99 } }); finishDetail({ code: 0, data: { id: '8', riskCode: 'OLD' } })
  await oldList; await oldDetail
  assert.equal(vm.rows[0].complaintNo, 'C8'); assert.equal(vm.total, 1); assert.equal(vm.detail.complaintNo, 'C8')
})
test('conflict preserves original decision version and blocks retry while refreshing', async () => {
  let finish, writes = 0
  const { vm } = setup({ follow: async () => { writes++; return { code: 409001 } }, getRiskDetail: () => new Promise(r => { finish = r }) })
  vm.selectedId = '8'; vm.pending = { id: '8', mode: 'risk', kind: 'follow', expectedVersion: 1 }
  const first = vm.onConfirm({ reason: '本次跟进内容' }); await Promise.resolve()
  assert.equal(vm.conflict.active, true); await vm.onConfirm({ reason: '不应重复' }); assert.equal(writes, 1)
  finish({ code: 0, data: { id: '8', version: 2, statusLabel: '跟进中' } }); await first
  assert.equal(vm.pending.expectedVersion, 1); assert.equal(vm.conflict.kept, '本次跟进内容')
})
test('failed queue refresh cannot claim remaining records have all been processed', async () => {
  const { vm } = setup(); vm.selectedId = '8'; vm.rows = [{ id: '8' }]
  vm.load = async () => { vm.error = '加载失败'; vm.rows = [] }
  vm.clearSelection = () => assert.fail('must retain current record')
  await vm.afterClose('8'); assert.equal(vm.queueDone, false)
})
test('complaint detail uses its own fields and respects masking', () => {
  const { vm, def } = setup(); vm.complaintMode = true
  vm.detail = { complaintNo: 'C8', contentMasked: true, content: '', conclusion: '', followupResult: '', statusLabel: '调查中' }
  const items = def.computed.summaryItems.call(vm)
  assert.equal(items.find(i => i.label === '投诉编号').value, 'C8')
  assert.equal(items.find(i => i.label === '投诉内容').value, '当前权限不可查看')
  assert.equal(items.some(i => i.label === '风险标题'), false)
})


test('risk list query preserves empty status overrides, page, selected object and batch', () => {
  const { vm } = setup(); let target
  vm.$route.query = { id: '9007199254740999', stage: 'pending', page: '3', batchId: '1' }
  vm.batchStore.withBatchQuery = q => ({ ...q, batchId: '1' })
  vm.$router = { replace: value => { target = value } }; vm.load = () => {}
  vm.page = 3; vm.statusFilter = ''; vm.keyword = '测试'
  vm.syncListQuery()
  assert.equal(target.query.id, '9007199254740999'); assert.equal(target.query.page, '3')
  assert.equal(target.query.status, ''); assert.equal(target.query.batchId, '1')
  vm.$route.query = target.query; vm.applyPanel('pending')
  assert.equal(vm.statusFilter, ''); assert.equal(vm.keyword, '测试'); assert.equal(vm.page, 3)
})

test('masked complaint evidence is never requested; preview errors stay local', async () => {
  let calls = 0
  const { vm } = setup({}, {}, { preview: async () => { calls++; throw new Error('无权查看材料') } })
  vm.complaintMode = true; vm.detail = { evidenceFileId: '8', evidenceMasked: true }
  await vm.previewEvidence(); assert.equal(calls, 0)
  vm.detail.evidenceMasked = false; await vm.previewEvidence()
  assert.equal(calls, 1); assert.equal(vm.evidenceError, '无权查看材料'); assert.equal(vm.evidenceLoading, false)
})

test('an old preview failure does not overwrite the newly selected record', async () => {
  let reject
  const { vm } = setup({}, {}, { preview: () => new Promise((_resolve, fail) => { reject = fail }) })
  vm.complaintMode = true; vm.detail = { id: '8', evidenceFileId: 'file8' }
  const old = vm.previewEvidence(); vm.resetDecision(); vm.detail = { id: '9' }
  reject(new Error('旧材料失败')); await old
  assert.equal(vm.evidenceError, ''); assert.equal(vm.evidenceLoading, false)
})
