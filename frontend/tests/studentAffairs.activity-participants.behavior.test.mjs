import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const parsed = parse(readFileSync(new URL('../src/modules/studentAffairs/views/activity/ActivityWorkbenchView.vue', import.meta.url), 'utf8'))
assert.deepEqual(parsed.errors, [])
const script = parsed.descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '')
  .replace(/ {2}components: \{[\s\S]*?\n {2}\},/, '  components: {},').replace('export default', 'return')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function mount(api) {
  let generation = 1
  const def = new Function('studentAffairsApi', 'currentSessionGeneration', 'normalizeUiError', script)(api, () => generation, e => ({ pageState: 'error', userMessage: e.message || '加载失败' }))
  const vm = { ...def.methods }; Object.assign(vm, def.data.call(vm))
  return { vm, def, switchAccount: () => { generation++ } }
}
const result = id => ({ code: 0, data: { items: [{ signupId: id }], total: 42 } })

test('PC roster passes pagination to the authority and retains server total', async () => {
  const calls = []; const { vm } = mount({ getActivityParticipants: async (id, params) => { calls.push({ id, ...params }); return result('1') } })
  await vm.openParticipants({ activityId: '12', activityName: '测试活动' }); vm.pv.page = 2; await vm.loadParticipants()
  assert.deepEqual(calls, [{ id: '12', page: 1, pageSize: 20 }, { id: '12', page: 2, pageSize: 20 }]); assert.equal(vm.pv.total, 42)
})
test('PC activity switches and newer requests discard the previous roster', async () => {
  const slow = deferred(); let calls = 0
  const { vm } = mount({ getActivityParticipants: () => ++calls === 1 ? slow.promise : Promise.resolve(result('new')) })
  const old = vm.openParticipants({ activityId: 'old' }); await vm.openParticipants({ activityId: 'new' })
  slow.resolve(result('old')); await old; assert.equal(vm.pv.list[0].signupId, 'new')
})
test('PC closed drawer, disposed page and account switch do not receive late names', async () => {
  for (const mode of ['close', 'dispose', 'account']) {
    const slow = deferred(); const { vm, def, switchAccount } = mount({ getActivityParticipants: () => slow.promise })
    const pending = vm.openParticipants({ activityId: '12' })
    if (mode === 'close') vm.pv.visible = false; else if (mode === 'dispose') def.beforeUnmount.call(vm); else switchAccount()
    slow.resolve(result('old')); await pending; assert.deepEqual(vm.pv.list, [])
  }
})
test('PC roster failure is not presented as empty', async () => {
  const { vm } = mount({ getActivityParticipants: async () => ({ code: 403002, message: '该活动不在您的范围内' }) })
  await vm.openParticipants({ activityId: '12' }); assert.equal(vm.pv.state, 'error'); assert.ok(vm.pv.error)
})
