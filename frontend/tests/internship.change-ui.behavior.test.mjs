import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { emptyConflict, isConflict, captureConflict } from '../src/modules/internship/composables/conflictGuard.js'

const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/ChangeRequestListView.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?AppButton \},/, '').replace('export default', 'return')
function setup(api = {}) {
  const def = new Function('internshipApi', 'emptyConflict', 'isConflict', 'captureConflict', 'REJECT_CHANGE', 'toast', script)(api, emptyConflict, isConflict, captureConflict, [], { error() {}, success() {} })
  const targets = []
  const vm = { ...def.data(), canReview: true, batchStore: { selectedBatchId: '1', withBatchQuery: q => ({ ...q, batchId: '1' }) },
    $route: { query: {}, fullPath: '/changes' }, $router: { replace: target => targets.push(target), push: target => targets.push(target) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  Object.defineProperty(vm, 'approvalBlockers', { get: () => def.computed.approvalBlockers.call(vm) })
  return { vm, def, targets }
}
function selected(vm) {
  vm.selectedId = '9007199254740999'
  vm.detail.data = { id: vm.selectedId, status: 'PENDING', version: 2, recordVersion: 4, recordVersionSnapshot: 4, studentName: '测试学生', changeTypeLabel: '换岗' }
  vm.openReview(vm.detail.data, 'APPROVE')
}

test('change workspace template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'ChangeRequestListView.vue', id: 'change-ui' }).errors, [])
})

test('late list and same-ID detail cannot replace a newer batch', async () => {
  let finishList, finishDetail
  const { vm } = setup({ getChangeRequests: () => new Promise(r => { finishList = r }), getChangeRequestDetail: () => new Promise(r => { finishDetail = r }) })
  vm.selectedId = '8'; const list = vm.load(), detail = vm.loadDetail('8')
  vm.batchStore.selectedBatchId = '2'; vm.resetDetail(); vm.rows = [{ id: 'new' }]
  finishList({ code: 0, data: { list: [{ id: 'old' }], total: 50 } }); finishDetail({ code: 0, data: { id: '8' } })
  await list; await detail; assert.equal(vm.rows[0].id, 'new'); assert.equal(vm.detail.data, null)
})

test('search and page deep links retain batch and large selected IDs', () => {
  const { vm, targets } = setup(); vm.load = () => {}
  vm.$route.query = { panel: 'all', page: '3', keyword: '测试', id: '9007199254740999', batchId: '1' }
  vm.applyQuery(); assert.equal(vm.pagination.page, 3); assert.equal(vm.filters.status, ''); assert.equal(vm.filters.keyword, '测试')
  vm.onPageChange({ page: 4 }); const query = targets.at(-1).query
  assert.equal(query.page, '4'); assert.equal(query.keyword, '测试'); assert.equal(query.id, '9007199254740999'); assert.equal(query.batchId, '1')
})

test('server target blockers and changed record snapshot prevent approval but allow rejection', () => {
  const { vm } = setup(); selected(vm); vm.pending = null
  vm.detail.data.recordVersion = 5
  vm.detail.data.targetPosition = { sameBatch: false, capacityAvailable: false, blockers: ['目标企业准入失效'] }
  assert.ok(vm.approvalBlockers.includes('目标企业准入失效'))
  vm.openReview(vm.detail.data, 'APPROVE'); assert.equal(vm.pending, null)
  vm.openReview(vm.detail.data, 'REJECT'); assert.equal(vm.pending.action, 'REJECT')
})

test('conflict keeps original application and record versions, preserves text and blocks retry', async () => {
  let finish; let writes = 0
  const { vm } = setup({ reviewChangeRequest: async (_id, payload) => { writes++; assert.equal(payload.expectedVersion, 2); assert.equal(payload.recordExpectedVersion, 4); return { code: 409001 } },
    getChangeRequestDetail: () => new Promise(r => { finish = r }) })
  selected(vm); const submit = vm.onConfirm({ reason: '已核对目标岗位' }); await Promise.resolve()
  assert.equal(vm.conflict.active, true); await vm.onConfirm({ reason: '不应重复提交' }); assert.equal(writes, 1)
  finish({ code: 0, data: { id: vm.selectedId, status: 'PENDING', version: 3, recordVersion: 5, recordVersionSnapshot: 5 } }); await submit
  assert.equal(vm.pending.expectedVersion, 2); assert.equal(vm.pending.recordExpectedVersion, 4); assert.equal(vm.conflict.kept, '已核对目标岗位')
})

test('old review result cannot clear a newly selected record or display its receipt', async () => {
  let finish
  const { vm } = setup({ reviewChangeRequest: () => new Promise(r => { finish = r }) }); selected(vm)
  const submit = vm.onConfirm({ reason: '' }); vm.resetDetail(); vm.selectedId = 'new'
  finish({ code: 0, data: { status: 'APPROVED' } }); await submit
  assert.equal(vm.selectedId, 'new'); assert.equal(vm.lastReceipt, null)
})

test('failed queue refresh keeps current object and never reports queue complete', async () => {
  const { vm } = setup({ getChangeRequests: async () => ({ code: 1, message: '加载失败' }) }); selected(vm)
  await vm.advanceAfterReview(vm.selectedId)
  assert.equal(vm.selectedId, '9007199254740999'); assert.equal(vm.doneHint, false)
})

test('queue readback cannot advance a selection made while the list is loading', async () => {
  let finish
  const { vm } = setup({ getChangeRequests: () => new Promise(r => { finish = r }) }); selected(vm)
  const refresh = vm.advanceAfterReview(vm.selectedId); vm.selectedId = 'new'
  finish({ code: 0, data: { list: [{ id: 'next', status: 'PENDING' }], total: 1 } }); await refresh
  assert.equal(vm.selectedId, 'new'); assert.equal(vm.doneHint, false)
})

test('double submit, missing review permission and short rejection do not send requests', async () => {
  const { vm } = setup({ reviewChangeRequest: () => assert.fail('unexpected write') }); selected(vm)
  vm.cd.submitting = true; await vm.onConfirm({ reason: '' })
  vm.cd.submitting = false; vm.canReview = false; await vm.onConfirm({ reason: '' })
  vm.canReview = true; vm.pending.action = 'REJECT'; await vm.onConfirm({ reason: '短' })
})
