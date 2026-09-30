import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/teacher/affairs/activity/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function mount(api) {
  let generation = 1
  const def = new Function('affairsContractApi', 'currentSessionGeneration', 'normalizeError', 'toast', script)(api, () => generation, e => ({ text: e.message }), () => {})
  const vm = { ...def.data(), ...def.methods }
  Object.defineProperty(vm, 'participantSummary', { get: () => def.computed.participantSummary.call(vm) })
  return { vm, def, switchAccount: () => { generation++ } }
}
const result = (ids, total = 23) => ({ items: ids.map(id => ({ signupId: id, signupStatus: 'ENROLLED' })), total, summary: { total: 22, checkedIn: 11 } })

test('roster loads server pages and summary is not computed from the loaded page', async () => {
  const calls = []
  const { vm } = mount({ getTeacherActivityParticipants: async (id, params) => { calls.push({ id, ...params }); return result(params.page === 1 ? ['1', '2'] : ['3']) } })
  await vm.openActivity({ activityId: '12' })
  assert.equal(vm.participantSummary.checkedIn, 11)
  await vm.loadParticipants(true)
  assert.deepEqual(calls, [{ id: '12', page: 1, pageSize: 20 }, { id: '12', page: 2, pageSize: 20 }])
  assert.equal(vm.participants.length, 3)
})

test('switching activities discards late roster and prevents duplicate next-page calls', async () => {
  const slow = deferred(); let calls = 0
  const { vm } = mount({ getTeacherActivityParticipants: (_id, { page }) => { calls++; return page === 2 ? slow.promise : Promise.resolve(result(['new'])) } })
  await vm.openActivity({ activityId: 'old' })
  const pending = vm.loadParticipants(true); await vm.loadParticipants(true)
  await vm.openActivity({ activityId: 'new' })
  slow.resolve(result(['old'])); await pending
  assert.equal(calls, 3); assert.deepEqual(vm.participants.map(x => x.signupId), ['new'])
})

test('close, unload and account switch discard participant responses', async () => {
  for (const mode of ['close', 'unload', 'account']) {
    const slow = deferred(); const { vm, def, switchAccount } = mount({ getTeacherActivityParticipants: () => slow.promise })
    const pending = vm.openActivity({ activityId: '12' })
    if (mode === 'close') vm.closeDetail(); else if (mode === 'unload') def.onUnload.call(vm); else switchAccount()
    slow.resolve(result(['secret'])); await pending
    assert.deepEqual(vm.participants, [])
  }
})

test('failed and malformed rosters remain explicit errors and do not confirm', async () => {
  for (const response of [null, { items: [] }]) {
    const { vm } = mount({ getTeacherActivityParticipants: async () => response })
    await vm.openActivity({ activityId: '12' }); assert.ok(vm.detailError); assert.equal(vm.participantLoading, false)
    vm.rosterSummary.checkedIn = 3
    vm.confirmRoster() // no uni modal is available; the error must stop confirmation.
  }
})
