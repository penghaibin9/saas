import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/modules/studentAffairs/views/FundingWorkbenchView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const body = source.split('async runAction(call, okMsg) {')[1].split('\n    }\n  }\n}')[0]
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const run = new AsyncFunction('call', 'okMsg', 'toast', body)
const toast = { success() {}, error() {} }

test('publicity step navigates to the guarded publicity workspace instead of offering an early confirmation', () => {
  const actions = new Function('FUND_NODES', source.split('detailActions() {')[1].split('\n    }\n  },')[0])
  const vm = { selected: { status: 'PUBLICITY' }, dialog: { visible: false }, goPublicity() { this.opened = true } }
  const available = actions.call(vm, ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'SCHOOL_REVIEW'])
  assert.deepEqual(available.map(x => x.key), ['publicityProgress'])
  const act = new Function('key', source.split('onAction(key) {')[1].split('\n    },')[0])
  act.call(vm, 'publicityProgress')
  assert.equal(vm.opened, true)
  assert.equal(vm.dialog.visible, false)
  act.call(vm, 'publicityConfirm')
  assert.equal(vm.dialog.visible, false)
})

test('approval summary cannot erase the statement; authoritative detail is reloaded after queue refresh', async () => {
  const calls = [], vm = { acting: false, selected: { applicationId: '1', statement: '学生已补充的说明', version: 3 },
    async loadApplications() { calls.push('list'); assert.equal(this.selected.statement, '学生已补充的说明') },
    async reloadDetail() { calls.push('detail'); this.selected = { applicationId: '1', statement: '服务端最新说明', status: 'PUBLICITY', version: 4 } } }
  assert.equal(await run.call(vm, async () => ({ code: 0, data: { applicationId: '1', status: 'PUBLICITY', version: 4 } }), '已通过', toast), true)
  assert.deepEqual(calls, ['list', 'detail'])
  assert.equal(vm.selected.statement, '服务端最新说明')
  assert.equal(vm.acting, false)
})

test('saved approval followed by a read failure remains successful and never repeats the command', async () => {
  let writes = 0
  const vm = { acting: false, selected: { applicationId: '1' }, loadApplications: async () => { throw new Error('offline') } }
  assert.equal(await run.call(vm, async () => { writes++; return { code: 0 } }, '已通过', toast), true)
  assert.equal(writes, 1); assert.equal(vm.acting, false)
  assert.match(vm._lastErr, /办理已完成.*不要重复提交/)
})

test('network failure unlocks the action and retains the current detail', async () => {
  const selected = { applicationId: '1', statement: '原说明' }, vm = { acting: false, selected }
  assert.equal(await run.call(vm, async () => { throw new Error('网络断开') }, '', toast), false)
  assert.equal(vm.selected, selected); assert.equal(vm.acting, false)
  assert.equal(vm._lastErr, '网络断开')
  vm.acting = true
  assert.equal(await run.call(vm, () => assert.fail('duplicate request'), '', toast), false)
})
