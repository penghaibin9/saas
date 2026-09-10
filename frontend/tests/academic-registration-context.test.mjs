import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { academicRouteState, createAcademicReturnStore } from '../src/modules/academicAffairs/academicFlowContext.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue', import.meta.url), 'utf8')
const student = (id, status = 'PENDING') => ({ studentId: id, realName: id, eligibilityStatus: status, registrationStatus: 'PENDING_REGISTER' })
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function page(query = {}, api = {}) {
  const calls = [], writes = []
  const ctx = { permissionPatterns: ['academicAffairs.registration.eligibility.verify', 'academicAffairs.registration.view'] }
  const sandbox = {
    matchPermission, academicRouteState, toast: { error() {}, success() {} },
    academicAffairsApi: {
      getContext: async () => ({ code: 0, data: ctx }),
      getRegistrationBatches: async () => ({ code: 0, data: { list: [{ batchId: '1', status: 'OPEN' }, { batchId: '2', status: 'OPEN' }] } }),
      getRegistrationEligibility: async (batch, args) => {
        calls.push({ batch, ...args })
        return { code: 0, data: { list: [student('first'), student('chosen')], total: 60 } }
      },
      verifyRegistrationEligibility: async (...args) => { writes.push(args); return { code: 503001 } },
      ...api
    }
  }
  for (const name of source.match(/components:\s*{([\s\S]*?)}/)[1].split(',').map(v => v.trim()).filter(Boolean)) sandbox[name] = {}
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '').replace('export default', 'component ='), sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods,
    $route: { path: '/admin/academic-affairs/registration-workbench', query: { ...query } },
    $router: {
      replace: async value => { state.$route.query = Object.fromEntries(Object.entries(value.query).filter(([, value]) => value !== undefined)) },
      push: value => { state.destination = value }
    }
  }
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => getter.call(state) })
  state.loadCurrentTab = () => { if (state.tab === 'eligibility') state.pendingRead = state.loadEligibility() }
  return { state, calls, writes, start: async () => { await component.created.call(state); await state.pendingRead } }
}

test('switching tabs preserves the selected student, filters and page but cancels confirmation', async () => {
  const { state, start } = page({ batchId: '1', studentId: 'chosen', tab: 'eligibility', keyword: '姓名', status: 'PENDING', page: '2', pageSize: '10' })
  await start(); state.askEligible(state.selectedEligRow)
  state.switchTab('exception'); state.switchTab('eligibility'); await state.pendingRead
  assert.equal(state.selectedEligId, 'chosen'); assert.equal(state.selectedEligRow.studentId, 'chosen')
  assert.equal(state.$route.query.studentId, 'chosen'); assert.equal(state.$route.query.keyword, '姓名')
  assert.equal(state.elig.pagination.page, 2); assert.equal(state.elig.pagination.pageSize, 10)
  assert.equal(state.pendingAction, null); assert.equal(state.confirm.visible, false)
  state.selectEligibilityRow(state.elig.rows[0]); await state.syncEligibilityRoute()
  assert.equal(state.$route.query.studentId, 'first')
})

test('changing batch replaces old object/page query and survives a refresh', async () => {
  const { state, start } = page({ batchId: '1', studentId: 'chosen', tab: 'eligibility', page: '3', status: 'PENDING' })
  await start(); state.batchId = '2'; state.onBatchChange(); await state.pendingRead
  assert.equal(state.$route.query.batchId, '2'); assert.equal(state.$route.query.page, '1')
  assert.equal(state.$route.query.studentId, 'first')
  const refreshed = page(state.$route.query); await refreshed.start()
  assert.equal(refreshed.state.batchId, '2'); assert.equal(refreshed.state.selectedEligId, 'first')
  assert.equal(refreshed.state.elig.pagination.page, 1)
})

test('formal registration return restores exact student, keyword, status and pagination through the real return store', async () => {
  const p = page({ batchId: '1', studentId: 'chosen', tab: 'eligibility', page: '2', pageSize: '10', keyword: '姓名', status: 'ELIGIBLE' })
  await p.start(); const state = p.state
  const memory = new Map(), storage = { getItem: key => memory.get(key), setItem: (key, value) => memory.set(key, value) }
  const returns = createAcademicReturnStore(storage, { token: () => 'return-test' })
  state.academicFlow = { captureReturn: () => returns.remember(state.$route, 'same-identity') }
  await state.goRegistrationList()
  assert.equal(state.destination.path, '/admin/academic-affairs/registration/1')
  const saved = returns.resolve(state.destination.query.returnToken, 'same-identity')
  const restored = page(Object.fromEntries(new URL(saved.path, 'http://localhost').searchParams)); await restored.start()
  assert.deepEqual(restored.calls[0], { batch: '1', keyword: '姓名', status: 'ELIGIBLE', page: 2, pageSize: 10 })
  assert.equal(restored.state.selectedEligId, 'chosen'); assert.equal(restored.state.elig.error, '')
})

test('an explicit next page releases the old deep-link target and cancels its confirmation', async () => {
  const { state, start, writes } = page({ batchId: '1', studentId: 'chosen' }, {
    getRegistrationEligibility: async (batch, args) => ({ code: 0, data: { list: [student(args.page === 1 ? 'chosen' : 'next-page')], total: 40 } })
  })
  await start(); state.askEligible(state.selectedEligRow)
  await state.onEligPage(2); await state.onConfirm()
  assert.equal(state.selectedEligId, 'next-page'); assert.equal(state.elig.error, '')
  assert.equal(state.$route.query.page, '2'); assert.equal(state.$route.query.studentId, 'next-page'); assert.equal(writes.length, 0)
})

test('changing a filter starts page one and does not revive an earlier object confirmation', async () => {
  const calls = []
  const { state, start, writes } = page({ batchId: '1', studentId: 'chosen', page: '3' }, {
    getRegistrationEligibility: async (batch, args) => {
      calls.push(args)
      return { code: 0, data: { list: [student(args.keyword ? 'filtered' : 'chosen')], total: 60 } }
    }
  })
  await start(); state.askEligible(state.selectedEligRow); state.elig.keyword = '新筛选'
  await state.loadEligibility(); await state.onConfirm()
  assert.equal(calls[1].page, 1); assert.equal(state.selectedEligId, 'filtered'); assert.equal(state.elig.error, '')
  assert.equal(state.$route.query.keyword, '新筛选'); assert.equal(state.$route.query.page, '1'); assert.equal(writes.length, 0)
})

test('an absent deep-linked student remains explicit across an empty response and retry', async () => {
  let reads = 0
  const { state, start } = page({ batchId: '1', studentId: 'missing' }, {
    getRegistrationEligibility: async () => ({ code: 0, data: { list: ++reads === 1 ? [] : [student('other')], total: 1 } })
  })
  await start(); assert.equal(state.selectedEligId, 'missing'); assert.equal(state.selectedEligRow, null)
  await state.loadEligibility()
  assert.equal(state.selectedEligId, 'missing'); assert.equal(state.selectedEligRow, null); assert.ok(state.elig.error)
})

test('switching queues preserves an unknown write lock', async () => {
  const { state, start, writes } = page({ batchId: '1', studentId: 'chosen' })
  await start(); state.askEligible(state.selectedEligRow); await state.onConfirm()
  assert.equal(writes.length, 1); assert.ok(state.eligUnknown)
  state.switchTab('exception'); state.switchTab('eligibility'); await state.pendingRead
  state.elig.keyword = 'new'; await state.loadEligibility(); state.askEligible(state.selectedEligRow); await state.onConfirm()
  assert.equal(writes.length, 1); assert.equal(state.eligUnknown.studentId, 'chosen')
})

test('without registration.view the eligibility role cannot open formal registration', async () => {
  const { state, start } = page({ batchId: '1' }); await start()
  state.ctx.permissionPatterns = ['academicAffairs.registration.eligibility.verify']
  await state.goRegistrationList(); assert.equal(state.destination, undefined)
})

test('changing the selected object while URL synchronization is pending prevents navigation', async () => {
  const { state, start } = page({ batchId: '1', studentId: 'chosen' }); await start()
  const pending = deferred()
  state.$route.query.page = '99'; state.$router.replace = () => pending.promise
  const navigation = state.goRegistrationList()
  state.selectEligibilityRow(state.elig.rows[0]); pending.resolve(); await navigation
  assert.equal(state.destination, undefined)
})
