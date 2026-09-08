import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { isConflict } from '../src/modules/internship/composables/conflictGuard.js'

const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/internship/views/components/ScoreAppealWorkspace.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace(/ {2}components: \{[^\n]*\},/, '').replace('export default', 'return')
const record = (extra = {}) => ({ id: '9007199254740999', batchId: '1', version: 2, studentName: '测试学生', status: 'PENDING', scoreSnapshot: { scoreVersion: 3, totalScore: 0 }, currentScore: { id: '88', version: 3, status: 'PUBLISHED', totalScore: 0 }, ...extra })
function setup(api = {}, permission = () => true) {
  const events = [], guards = [], browser = { confirm: () => false, addEventListener() {}, removeEventListener() {} }
  const def = new Function('scoreApi', 'canCode', 'isConflict', 'window', script)(api, permission, isConflict, browser)
  const vm = { ...def.data(), appealId: record().id, batchId: '1', ctx: {}, $emit: (...event) => events.push(event), $nextTick: fn => fn(), $el: { querySelector: () => ({ focus() {} }) }, $router: { beforeEach: fn => { guards.push(fn); return () => {} } } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, fn] of Object.entries(def.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, def, events, guards, browser }
}
function choose(vm, decision = 'approve') { vm.record = record(); vm.decision = decision; vm.reason = '核对材料后的处理意见'; vm.openConfirmation() }

test('appeal workspace template compiles', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'ScoreAppealWorkspace.vue', id: 'score-appeal' }).errors, [])
})
test('detail request keeps large ID and rejects another batch', async () => {
  const ids = []
  const { vm } = setup({ getAppeal: async id => { ids.push(id); return { code: 0, data: record({ batchId: '2' }) } } })
  await vm.load(); assert.deepEqual(ids, ['9007199254740999']); assert.equal(vm.record, null); assert.match(vm.error, /不属于当前批次/)
})
test('late detail responses cannot replace new context or unmounted view', async () => {
  let finish
  const { vm, def } = setup({ getAppeal: () => new Promise(r => { finish = r }) })
  const first = vm.load(); vm.batchId = '2'; finish({ code: 0, data: record() }); await first; assert.equal(vm.record, null)
  const second = vm.load(); def.beforeUnmount.call(vm); finish({ code: 0, data: record({ batchId: '2' }) }); await second; assert.equal(vm.record, null)
})
test('permission denial blocks reads and decisions', async () => {
  const { vm } = setup({ getAppeal: () => assert.fail('must not read'), approveAppeal: () => assert.fail('must not write') }, () => false)
  await vm.load(); choose(vm); await vm.submit(); assert.equal(vm.pending, null); assert.match(vm.error, /权限/)
})
test('changed published score cannot be withdrawn through approval but allows an informed rejection', () => {
  const { vm } = setup(); vm.record = record({ currentScore: { version: 4, status: 'PUBLISHED' } }); vm.reason = '经核对后填写处理意见'; vm.decision = 'approve'; vm.openConfirmation(); assert.equal(vm.pending, null)
  vm.decision = 'reject'; vm.openConfirmation(); assert.equal(vm.pending.decision, 'reject'); assert.equal(vm.pending.expectedVersion, 2)
})
test('opinion requires five characters and confirmation captures its original version', () => {
  const { vm } = setup(); vm.record = record(); vm.reason = '短'; vm.decision = 'approve'; vm.openConfirmation(); assert.match(vm.submitError, /至少填写 5/); assert.equal(vm.confirmVisible, false)
  vm.reason = '足够长的处理意见'; vm.openConfirmation(); assert.equal(vm.pending.expectedVersion, 2); assert.equal(vm.pending.reason, '足够长的处理意见')
})
test('submission requires a valid explicit confirmation and rejects duplicate clicks', async () => {
  let finish, calls = 0
  const { vm } = setup({ approveAppeal: () => { calls++; return new Promise(r => { finish = r }) } }); choose(vm)
  const first = vm.submit(); await vm.submit(); assert.equal(calls, 1); finish({ code: 1, message: '接口失败' }); await first
  assert.equal(vm.reason, '核对材料后的处理意见'); assert.equal(vm.confirmVisible, true); assert.equal(vm.pending.expectedVersion, 2); assert.equal(vm.submitError, '接口失败')
})
test('conflict preserves opinion and original version and requires an explicit new decision', async () => {
  let calls = 0
  const { vm } = setup({ approveAppeal: async () => { calls++; return { code: 409001, message: '版本冲突' } }, getAppeal: async () => ({ code: 0, data: record({ version: 4 }) }) }); choose(vm)
  await vm.submit(); await vm.submit(); assert.equal(calls, 1); assert.equal(vm.conflict, true); assert.equal(vm.reason, '核对材料后的处理意见'); assert.equal(vm.pending.expectedVersion, 2)
  vm.acknowledgeLatest(); assert.equal(vm.pending, null); assert.equal(vm.decision, ''); assert.equal(vm.canSubmit, false)
})
test('successful decision remains completed even when readback fails', async () => {
  const { vm, events } = setup({ rejectAppeal: async () => ({ code: 0, data: { id: record().id, version: 3, scoreId: '88', scoreVersion: 3 } }), getAppeal: async () => ({ code: 1, message: '回读失败' }) }); choose(vm, 'reject')
  await vm.submit(); assert.equal(vm.completed, true); assert.equal(vm.receipt.actionLabel, '申诉已驳回'); assert.equal(vm.error, '回读失败'); assert.equal(vm.canSubmit, false); assert.equal(vm.dirty, false); assert.equal(events[0][0], 'handled')
})
test('old decision completion cannot mutate a switched identity', async () => {
  let finish
  const { vm, def, events } = setup({ approveAppeal: () => new Promise(r => { finish = r }), getAppeal: async () => ({ code: 0, data: record() }) }); choose(vm)
  const first = vm.submit(); def.watch.ctx.handler.call(vm); finish({ code: 0, data: { id: record().id, version: 3 } }); await first
  assert.equal(vm.receipt, null); assert.deepEqual(events, []); assert.equal(vm.reason, '')
})
test('navigation protects unsaved opinions and allows leaving after durable success', () => {
  const { vm, def, guards, browser } = setup(); def.mounted.call(vm); vm.reason = '未提交意见'
  const from = { path: '/scores', fullPath: '/scores?appealId=8' }, to = { path: '/other', fullPath: '/other', query: {} }
  assert.equal(guards[0](to, from), false); browser.confirm = () => true; assert.equal(guards[0](to, from), true)
  vm.submitting = true; assert.equal(guards[0](to, from), false); vm.submitting = false; vm.completed = true; browser.confirm = () => assert.fail('saved decision should not prompt'); assert.equal(guards[0](to, from), true)
})
test('audit display excludes internal snapshot metadata', () => {
  const { vm } = setup(); vm.record = record({ trail: [{ kind: 'INTERNSHIP_SCORE_APPEAL_META', scoreId: '88' }, { action: 'APPROVE', operator: '测试老师', note: '真实处理意见', at: '2026-09-07' }] })
  assert.equal(vm.auditRecords.length, 1); assert.equal(vm.auditRecords[0].reason, '真实处理意见')
})
