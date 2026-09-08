import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { isConflict, captureConflict, emptyConflict } from '../src/modules/internship/composables/conflictGuard.js'

const source = fs.readFileSync(new URL('../src/modules/internship/views/GuidanceVisitView.vue', import.meta.url), 'utf8')
const script = parse(source).descriptor.script.content
  .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?ActionReceipt \},/, '')
  .replace('export default', 'return')
function setup(api) {
  const def = new Function('guidanceVisitApi', 'emptyConflict', 'isConflict', 'captureConflict', 'canCode', 'toast', script)(api, emptyConflict, isConflict, captureConflict, () => true, { success() {}, error() {} })
  const vm = { ...def.data(), batchStore: { selectedBatchId: '1' }, $route: { query: {} } }
  for (const [name, fn] of Object.entries(def.methods)) vm[name] = fn.bind(vm)
  return vm
}

test('tab switch rejects the previous list response', async () => {
  let finish
  const vm = setup({ getGuidances: () => new Promise(resolve => { finish = resolve }),
    getVisitPlans: async () => ({ code: 0, data: { list: [{ id: 'plan' }], total: 1 } }) })
  const old = vm.load()
  vm.tab = 'visit-plan'; await vm.load()
  finish({ code: 0, data: { list: [{ id: 'guidance' }], total: 99 } }); await old
  assert.equal(vm.rows[0].id, 'plan'); assert.equal(vm.total, 1)
})

test('same ID in different record kinds cannot replace the current detail', async () => {
  let finish
  const vm = setup({ getGuidanceDetail: () => new Promise(resolve => { finish = resolve }),
    getVisitPlanDetail: async () => ({ code: 0, data: { id: '8', objective: '巡访目标' } }) })
  vm.selectedId = '8'
  const old = vm.loadDetail('8')
  vm.tab = 'visit-plan'; vm.resetDetail(); await vm.loadDetail('8')
  finish({ code: 0, data: { id: '8', topic: '旧指导' } }); await old
  assert.equal(vm.detail.data.objective, '巡访目标')
  assert.equal(vm.detail.data.topic, undefined)
})

test('statistics failure clears old numbers and ignores a previous batch response', async () => {
  let finish
  const vm = setup({ getGuidanceStats: (_threshold, params) => params.batchId === '1'
    ? new Promise(resolve => { finish = resolve }) : Promise.resolve({ code: 1, message: '统计暂不可用' }) })
  vm.guidanceStats = { studentCount: 10 }
  const old = vm.loadStats()
  assert.equal(vm.guidanceStats, null)
  vm.batchStore.selectedBatchId = '2'; await vm.loadStats()
  finish({ code: 0, data: { studentCount: 10 } }); await old
  assert.equal(vm.guidanceStats, null); assert.equal(vm.statsError, '统计暂不可用')
})

test('communication and visit-plan rows use their real object fields', () => {
  const vm = setup({})
  vm.tab = 'communication'
  assert.equal(vm.recordTitle({ summary: '确认下周指导安排' }), '确认下周指导安排')
  assert.equal(vm.recordMeta({ communicationTypeLabel: '电话沟通', contactName: '测试联系人' }), '电话沟通 · 测试联系人')
  vm.tab = 'visit-plan'
  assert.equal(vm.recordTitle({ enterpriseName: '测试企业' }), '测试企业')
  assert.equal(vm.recordMeta({ ownerName: '测试教师', planDate: '2026-09-10' }), '测试教师 · 2026-09-10')
})

test('switching the record while a decision is pending prevents late UI writes', async () => {
  let finish
  const vm = setup({ voidGuidance: () => new Promise(resolve => { finish = resolve }) })
  vm.selectedId = '8'
  vm.pending = { kind: 'void', id: '8', expectedVersion: 1 }
  const old = vm.onConfirm({ reason: '测试撤销原因' })
  vm.resetDetail(); vm.selectedId = '9'
  finish({ code: 0, data: { id: '8' } }); await old
  assert.equal(vm.selectedId, '9'); assert.equal(vm.lastReceipt, null)
  assert.equal(vm.cd.submitting, false)
})


test('conflict blocks repeat submission and keeps the version originally reviewed', async () => {
  let writes = 0, finish
  const vm = setup({ voidGuidance: async () => { writes++; return { code: 409001 } },
    getGuidanceDetail: () => new Promise(resolve => { finish = resolve }) })
  vm.selectedId = '8'; vm.pending = { kind: 'void', id: '8', expectedVersion: 1 }
  const original = vm.onConfirm({ reason: '保留这段撤销原因' })
  await Promise.resolve()
  assert.equal(vm.conflict.active, true)
  await vm.onConfirm({ reason: '不得重复发出' }); assert.equal(writes, 1)
  finish({ code: 0, data: { id: '8', version: 2, status: 'NORMAL' } }); await original
  assert.equal(vm.pending.expectedVersion, 1)
  assert.equal(vm.conflict.kept, '保留这段撤销原因')
  assert.equal(vm.conflict.stale, false)
  await vm.onConfirm({ reason: '仍不得使用旧确认框重提' }); assert.equal(writes, 1)
})

test('failed conflict refresh remains blocked and reports unavailable current state', async () => {
  const vm = setup({ voidGuidance: async () => ({ code: 409001 }),
    getGuidanceDetail: async () => ({ code: 1, message: '详情读取失败' }) })
  vm.selectedId = '8'; vm.pending = { kind: 'void', id: '8', expectedVersion: 1 }
  await vm.onConfirm({ reason: '保留处理原因' })
  assert.equal(vm.conflict.active, true); assert.equal(vm.conflict.stale, true)
  assert.equal(vm.pending.expectedVersion, 1)
})

test('a denied permission cannot issue the pending decision', async () => {
  let writes = 0
  const vm = setup({ voidGuidance: async () => { writes++ } })
  vm.selectedId = '8'; vm.pending = { kind: 'void', id: '8', expectedVersion: 1 }
  vm.canBtn = () => false
  await vm.onConfirm({ reason: '测试原因' }); assert.equal(writes, 0)
})


test('successful withdrawal preserves its receipt after clearing the selected record', async () => {
  const vm = setup({ voidGuidance: async () => ({ code: 0, data: { id: '8', status: 'VOIDED', version: 2 } }) })
  vm.selectedId = '8'; vm.pending = { kind: 'void', id: '8', expectedVersion: 1 }
  vm.batchStore.withBatchQuery = q => ({ ...q, batchId: '1' })
  vm.$router = { replace() {} }; vm.load = () => {}; vm.loadStats = () => {}
  await vm.onConfirm({ reason: '保留撤销回执' })
  assert.equal(vm.selectedId, '')
  assert.equal(vm.lastReceipt.id, '8'); assert.equal(vm.lastReceipt.status, 'VOIDED')
  assert.equal(vm.lastReceipt.version, 2)
})


test('new visit plan carries batch, company and schedule and opens the created detail', async () => {
  let payload, opened
  const vm = setup({ createVisitPlan: async body => { payload = body; return { code: 0, data: { id: '9007199254740999', status: 'DRAFT', version: 1 } } } })
  vm.planForm = { enterpriseId: '99', enterpriseName: '测试企业', objective: '核对指导安排', planDate: '2026-09-15', method: 'ONSITE', location: '会议室' }
  vm.showCreatedRecord = id => { opened = id }; vm.reload = () => {}
  await vm.submitVisitPlan()
  assert.equal(payload.batchId, '1'); assert.equal(payload.enterpriseId, '99')
  assert.equal(payload.planDate, '2026-09-15'); assert.equal(payload.location, '会议室')
  assert.equal(opened, '9007199254740999'); assert.equal(vm.lastReceipt.status, 'DRAFT')
})

test('changing context during plan creation prevents late navigation and receipt changes', async () => {
  let finish, writes = 0
  const vm = setup({ createVisitPlan: () => { writes++; return new Promise(resolve => { finish = resolve }) } })
  vm.planForm.objective = '核对指导安排'
  const old = vm.submitVisitPlan()
  await vm.submitVisitPlan(); assert.equal(writes, 1)
  vm.resetCreateDialogs(); vm.tab = 'guidance'
  finish({ code: 0, data: { id: '8' } }); await old
  assert.equal(vm.lastReceipt, null); assert.equal(vm.planDlg.visible, false)
})

test('communication failure keeps entered contact, summary and result for correction', async () => {
  let payload
  const vm = setup({ createCommunication: async body => { payload = body; return { code: 1, message: '请选择有效企业' } } })
  vm.commForm = { enterpriseId: '8', internshipId: '9', summary: '核对安排', communicationType: 'PHONE', contactName: '测试联系人', result: '下周再次沟通' }
  await vm.submitCommunication()
  assert.equal(payload.batchId, '1'); assert.equal(payload.contactName, '测试联系人')
  assert.equal(vm.commForm.result, '下周再次沟通'); assert.equal(vm.commDlg.error, '请选择有效企业')
  assert.equal(vm.commDlg.submitting, false)
})
