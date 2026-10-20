import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { computed, effectScope, nextTick, ref, unref, watch } from 'vue'
import { projectStudentAffairsWall, wallPacket } from '../src/modules/studentAffairs/composables/studentAffairsWallProjection.js'
import { WALL_ROUTES } from '../src/modules/studentAffairs/config/studentAffairsWall.contract.js'

const source = fs.readFileSync(new URL('../src/modules/studentAffairs/composables/useStudentAffairsWallData.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export function', 'function')
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const ctx = key => ({ ctxKey: key, permissionPatterns: ['studentAffairs.dashboard.view', 'studentAffairs.stats.view', 'studentAffairs.leave.view', 'studentAffairs.student.view'] })
const dashboard = count => ({ code: 0, data: { scopeMode: 'SCOPED', summaryCards: [{ key: 'studentTotal', value: count }] } })
function setup(t, overrides = {}) {
  const scope = effectScope()
  const context = ref(ctx('school-a'))
  const stopHooks = []
  const api = { getDashboard: async () => dashboard(7), getStatsCockpit: async () => ({ code: 0, data: { domains: [{ key: 'dorm', status: 'OK', metrics: { totalBeds: 8, occupiedBeds: 6 } }] } }), getContext: async () => ({ code: 0, data: context.value }), ...overrides }
  const dependencies = { computed, ref, unref, watch, onMounted() {}, onBeforeUnmount(fn) { stopHooks.push(fn) }, studentAffairsApi: api, leaveApi: { stats: async () => ({ code: 0, data: { groupBy: 'TYPE', breakdown: [] } }) }, canCode: (value, permission) => value?.permissionPatterns?.includes(permission), WALL_ROUTES, projectStudentAffairsWall, wallPacket, window: { clearInterval() {} }, document: { removeEventListener() {} } }
  const useData = new Function(...Object.keys(dependencies), source + '\nreturn useStudentAffairsWallData')(...Object.values(dependencies))
  const state = scope.run(() => useData(context))
  t.after(() => { stopHooks.forEach(fn => fn()); scope.stop() })
  return { state, context, api }
}
const flush = async () => { for (let i = 0; i < 8; i++) await nextTick() }

test('switching context while loading starts a new request and discards the old response', async t => {
  const old = deferred()
  let count = 0
  const { state, context } = setup(t, { getDashboard: () => ++count === 1 ? old.promise : Promise.resolve(dashboard(2)) })
  const first = state.load()
  context.value = ctx('school-b')
  await flush()
  assert.equal(count, 2)
  assert.equal(state.snapshot.value.metrics.students.value, 2)
  assert.equal(state.loading.value, false)
  old.resolve(dashboard(999))
  await first
  assert.equal(state.snapshot.value.metrics.students.value, 2)
})

test('one failed source clears its stale numbers and preserves other successful sources', async t => {
  const { state, api } = setup(t)
  await state.load()
  assert.equal(state.snapshot.value.metrics.students.value, 7)
  api.getDashboard = async () => { throw new Error('offline') }
  await state.load()
  assert.equal(state.snapshot.value.metrics.students.value, null)
  assert.equal(state.snapshot.value.metrics.students.status, 'ERROR')
  assert.equal(state.snapshot.value.metrics.occupied.value, 6)
  assert.match(state.errorMessage.value, /暂不可用/)
  assert.equal(state.loading.value, false)
})

test('scope changes invalidate data even when the server context key is unchanged', async t => {
  const { state, context } = setup(t)
  await state.load()
  context.value = { ...ctx('school-a'), dataScope: { scopeType: 'NONE' } }
  await flush()
  assert.equal(state.snapshot.value.metrics.students.status, 'NO_SCOPE')
  assert.equal(state.snapshot.value.metrics.students.value, null)
})

test('unchanged authorized context resolves the real business route', async t => {
  const { state } = setup(t)
  assert.equal(await state.authorize('student'), '/admin/student/list')
})

test('missing permission context makes no data request, including development mode', async t => {
  let calls = 0
  const { state, context } = setup(t, { getDashboard: async () => { calls++; return dashboard(7) } })
  context.value = { ctxKey: 'school-b' }
  await flush()
  assert.equal(calls, 0)
  assert.equal(state.snapshot.value.metrics.students.status, 'RESTRICTED')
})

test('permission response from an old context cannot authorize drilldown', async t => {
  const pending = deferred()
  const { state, context } = setup(t, { getContext: () => pending.promise })
  const navigation = state.authorize('student')
  context.value = ctx('school-b')
  pending.resolve({ code: 0, data: ctx('school-a') })
  assert.equal(await navigation, null)
})

test('network failure during drilldown remains recoverable without unhandled rejection', async t => {
  const { state } = setup(t, { getContext: async () => { throw new Error('offline') } })
  assert.equal(await state.authorize('student'), null)
  assert.match(state.errorMessage.value, /权限/)
})
