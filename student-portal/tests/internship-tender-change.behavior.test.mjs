import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, reactive, ref, watch } from 'vue'
import { INTERNSHIP_TABS as tabs } from '../src/modules/internshipRecruitment/navigation.js'
const ctx = { hasData: true, batchId: '9007199254741001', recordId: '9007199254741002', status: 'READY' }
const target = { id: '9007199254741003', positionId: '9007199254741003', companyName: '目标企业', title: '目标岗位', canSelect: true }
const returned = { id: '9007199254741005', version: 2, changeType: 'CHANGE_ENTERPRISE', status: 'REJECTED', reason: '原事由需补充沟通情况', reviewComment: '请补充校企沟通记录' }
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
function page(t, api = {}) {
  let generation = 1
  const calls = [], notices = [], lifecycle = {}, scope = effectScope()
  const deps = {
    tabs, computed, reactive, ref, watch,
    onMounted: fn => { lifecycle.mount = fn }, onBeforeUnmount: fn => { lifecycle.unmount = fn },
    useUiStore: () => ({ notify: value => notices.push(value) }), usePortalConfigStore: () => ({}), useSessionStore: () => ({}),
    useRoute: () => ({ query: {} }), useRouter: () => ({ replace() {}, push() {} }),
    currentSessionGeneration: () => generation,
    portalApi: {}, fileSdk: {}, scanState() {}, scanFilesReady() {}, refreshScanFiles() {}, systemPrompt() {},
    internshipCoreApi: {
      changeTargets: async (...args) => { calls.push(['targets', ...args]); return { items: [target], hasMore: false } },
      changes: async (...args) => { calls.push(['history', ...args]); return { items: [returned], hasMore: false } },
      applyChange: async body => { calls.push(['create', body]); return { id: 'new', version: 0, status: 'PENDING' } },
      resubmitChange: async (id, body) => { calls.push(['resubmit', id, body]); return { id, version: 3, status: 'PENDING' } },
      withdrawChange: async (id, body) => { calls.push(['withdraw', id, body]); return { id, version: 3, status: 'WITHDRAWN' } }, ...api
    }
  }
  const script = parse(fs.readFileSync(new URL('../src/views/internship/InternshipView.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '')
  const names = ['my', 'changeForm', 'changeTargets', 'changeTargetLoading', 'changeSelectedTarget', 'changeEditing', 'changeBusy', 'changeError', 'changeReceipt', 'changes', 'loadChangeTargets', 'selectChangeTarget', 'changeTypePicked', 'editChange', 'cancelChangeEditing', 'submitChange', 'withdrawChange', 'loadChanges', 'resetSourceStates']
  const vm = scope.run(() => new Function(...Object.keys(deps), script + '\nreturn {' + names.join(',') + '}')(...Object.values(deps)))
  t.after(() => { lifecycle.unmount?.(); scope.stop() }); vm.my.value = { ...ctx }
  return { vm, calls, notices, lifecycle, logout: () => generation++ }
}

test('电脑换企业使用权威岗位，补正保持原单编号和原版本', async t => {
  const { vm, calls } = page(t)
  vm.editChange(returned); await Promise.resolve()
  vm.changeForm.targetPositionId = target.positionId; vm.selectChangeTarget()
  vm.changeForm.reason = '补充岗位调整与校企沟通情况'
  await vm.submitChange()
  const sent = calls.find(call => call[0] === 'resubmit')
  assert.equal(sent[1], returned.id); assert.equal(sent[2].expectedVersion, 2)
  assert.equal(sent[2].targetPositionId, target.positionId); assert.equal(sent[2].batchId, ctx.batchId)
  assert.equal(calls.filter(call => call[0] === 'create').length, 0)
  assert.equal(calls.find(call => call[0] === 'targets')[2], 'CHANGE_ENTERPRISE')
  assert.equal(vm.changeReceipt.value.id, returned.id)
})

test('冲突和重复点击保留输入、目标及原版本', async t => {
  const request = deferred(); let count = 0
  const { vm } = page(t, { resubmitChange: () => { count++; return request.promise } })
  vm.editChange(returned); await Promise.resolve(); vm.changeForm.targetPositionId = target.positionId; vm.selectChangeTarget()
  const sending = vm.submitChange(); await vm.submitChange(); request.reject({ bizCode: 'DATA_CONFLICT', message: 'RAW_INTERNAL' }); await sending
  assert.equal(count, 1); assert.equal(vm.changeEditing.value.version, 2); assert.equal(vm.changeForm.reason, returned.reason)
  assert.equal(vm.changeSelectedTarget.value.positionId, target.positionId); assert.equal(vm.changeReceipt.value, null)
  assert.ok(vm.changeError.value.includes('原版本已保留')); assert.ok(!vm.changeError.value.includes('RAW_INTERNAL'))
})

test('切批次使迟到岗位、历史与提交失效', async t => {
  const targets = deferred(), submit = deferred(), history = deferred()
  const { vm } = page(t, { changeTargets: () => targets.promise, changes: () => history.promise, applyChange: () => submit.promise })
  const reading = vm.loadChangeTargets(), listing = vm.loadChanges()
  vm.changeSelectedTarget.value = target; vm.changeForm.reason = '申请调整岗位与沟通情况'; vm.changeForm.targetPositionId = target.positionId
  const sending = vm.submitChange(); vm.resetSourceStates(); vm.my.value = { ...ctx, batchId: 'other' }; vm.changeForm.reason = '新批次草稿'
  targets.resolve({ items: [target] }); history.resolve({ items: [returned] }); submit.resolve({ id: 'old', status: 'PENDING', version: 0 })
  await Promise.all([reading, listing, sending])
  assert.deepEqual(vm.changeTargets.value, []); assert.deepEqual(vm.changes.value, [])
  assert.equal(vm.changeReceipt.value, null); assert.equal(vm.changeForm.reason, '新批次草稿')
})

test('新账号与已卸载页面不能接纳旧目标查询', async t => {
  const pending = deferred(); const { vm, logout, lifecycle } = page(t, { changeTargets: () => pending.promise })
  const reading = vm.loadChangeTargets(); logout(); lifecycle.unmount(); pending.resolve({ items: [target] }); await reading
  assert.deepEqual(vm.changeTargets.value, [])
})

test('自主实习不夹带旧岗位，历史状态不会显示原枚举', async t => {
  const { vm, calls } = page(t)
  vm.changeForm.changeType = 'SELF_ARRANGED'; vm.changeForm.reason = '申请转为自主联系实习安排'
  vm.changeForm.targetEnterpriseName = '自主企业'; vm.changeForm.targetPositionName = '自主岗位'
  vm.changeSelectedTarget.value = target; await vm.submitChange()
  const body = calls.find(call => call[0] === 'create')[1]
  assert.equal(body.targetPositionId, undefined); assert.equal(body.targetEnterpriseName, '自主企业')
  assert.equal(vm.changes.value[0].statusLabel, '已退回，请补正')
})

test('换单位原单查询在途取消补正，候选正常收尾且没有加载死锁', async t => {
  const pending = deferred(); const { vm } = page(t, { changeTargets: () => pending.promise })
  vm.editChange(returned); assert.equal(vm.changeTargetLoading.value, true)
  vm.cancelChangeEditing(); assert.equal(vm.changeForm.changeType, 'CHANGE_ENTERPRISE')
  pending.resolve({ items: [target] }); await Promise.resolve(); await Promise.resolve()
  assert.equal(vm.changeTargetLoading.value, false); assert.equal(vm.changeTargets.value.length, 1)
})

test('历史实习不发起、补正或撤回变更', async t => {
  const { vm, calls } = page(t)
  vm.my.value.historyMode = true; vm.changeForm.reason = '历史记录不应提交新变更'; vm.changeSelectedTarget.value = target
  vm.editChange(returned); await vm.submitChange(); await vm.withdrawChange(returned)
  assert.equal(vm.changeEditing.value, null); assert.equal(calls.length, 0)
})
