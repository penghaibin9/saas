import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { academicRouteState } from '../src/modules/academicAffairs/academicFlowContext.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue', import.meta.url), 'utf8')
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const student = (id = '1000000000000063602') => ({ studentId: id, realName: '隔离学生', eligibilityStatus: 'PENDING', registrationStatus: 'PENDING_REGISTER' })
function page(api = {}) {
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '')
    .replace('export default', 'component =')
  const sandbox = { academicAffairsApi: api, matchPermission, academicRouteState, formatDateTime, toast: { error() {}, success() {} } }
  const componentNames = source.match(/components:\s*{([\s\S]*?)}/)[1].split(',').map(name => name.trim()).filter(Boolean)
  for (const name of componentNames) sandbox[name] = {}
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods,
    batchId: '1', batches: [{ batchId: '1', status: 'OPEN' }, { batchId: '2', status: 'OPEN' }],
    ctx: { permissionPatterns: ['academicAffairs.registration.eligibility.verify'] } }
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => getter.call(state) })
  state.elig.rows = [student()]; state.selectEligibilityRow(state.elig.rows[0])
  return { state, component }
}

test('old-batch replies cannot replace the current eligibility queue', async () => {
  const old = deferred()
  const { state } = page({ getRegistrationEligibility: (batch) => batch === '1' ? old.promise : Promise.resolve({ code: 0, data: { list: [student('new')], total: 1 } }) })
  const pending = state.loadEligibility(); state.batchId = '2'; await state.loadEligibility()
  old.resolve({ code: 0, data: { list: [student('old')], total: 1 } }); await pending
  assert.equal(state.selectedEligId, 'new'); assert.equal(state.elig.loading, false)
})

test('a slower search in the same batch cannot overwrite the newer filter', async () => {
  const old = deferred()
  const { state } = page({ getRegistrationEligibility: (batch, query) => query.keyword === 'old' ? old.promise : Promise.resolve({ code: 0, data: { list: [student('new')], total: 1 } }) })
  state.elig.keyword = 'old'; const pending = state.loadEligibility()
  state.elig.keyword = 'new'; await state.loadEligibility()
  old.resolve({ code: 0, data: { list: [student('old')], total: 1 } }); await pending
  assert.equal(state.selectedEligId, 'new')
})

test('batch, role, selection and refreshed evidence changes invalidate confirmation', async () => {
  for (const change of [s => { s.batchId = '2' }, s => { s.ctx.permissionPatterns = [] },
    s => { s.selectedEligId = 'other' }, s => { s.elig.rows[0].eligibilityCheckedAt = 'changed' }]) {
    let writes = 0
    const { state } = page({ verifyRegistrationEligibility: async () => { writes++; return { code: 0 } } })
    state.askEligible(state.elig.rows[0]); change(state); await state.onConfirm()
    assert.equal(writes, 0)
  }
})

test('a late response after unmount cannot disclose the prior queue', async () => {
  const reply = deferred(); const { state, component } = page({ getRegistrationEligibility: () => reply.promise })
  const pending = state.loadEligibility(); component.beforeUnmount.call(state)
  reply.resolve({ code: 0, data: { list: [student('late')], total: 1 } }); await pending
  assert.notEqual(state.elig.rows[0].studentId, 'late')
})

test('verification freezes exact identifiers and allows only one in-flight command', async () => {
  const reply = deferred(), writes = []
  const { state } = page({ verifyRegistrationEligibility: (...args) => { writes.push(args); return reply.promise } })
  state.loadEligibility = async () => {}
  state.askEligible(state.elig.rows[0]); const pending = state.onConfirm()
  state.askEligible(state.elig.rows[0]); await state.onConfirm()
  assert.equal(writes.length, 1); assert.equal(writes[0][0], '1'); assert.equal(writes[0][1], '1000000000000063602')
  reply.resolve({ code: 0, data: { registrationId: 'record', studentId: writes[0][1], eligibilityStatus: 'ELIGIBLE' } }); await pending
  assert.equal(state.eligReceipt.registrationId, 'record'); assert.equal(state.eligSubmitting, false)
})

test('ineligible drawer cannot write the same student into another batch', async () => {
  let writes = 0; const { state } = page({ verifyRegistrationEligibility: async () => { writes++; return { code: 0 } } })
  state.openIneligible(state.elig.rows[0]); state.eligDrawer.note = '已核对材料'; state.batchId = '2'
  await state.submitIneligible(); assert.equal(writes, 0); assert.equal(state.eligDrawer.note, '已核对材料')
})

test('409 preserves the ineligible input and official reason without a success receipt', async () => {
  const { state } = page({ verifyRegistrationEligibility: async () => ({ code: 409001, message: '批次已关闭' }) })
  state.openIneligible(state.elig.rows[0]); state.eligDrawer.note = '已核对材料'; await state.submitIneligible()
  assert.equal(state.eligDrawer.visible, true); assert.equal(state.eligDrawer.note, '已核对材料')
  assert.equal(state.eligDrawer.formError, '批次已关闭'); assert.equal(state.eligReceipt, null)
})

test('403 clears the displayed sensitive object', async () => {
  const { state } = page({ verifyRegistrationEligibility: async () => ({ code: 403001, message: '无权核验' }) })
  state.askEligible(state.elig.rows[0]); await state.onConfirm()
  assert.equal(state.selectedEligRow, null); assert.equal(state.elig.rows.length, 0)
})

test('timeout reads formal facts but cannot automatically replay verification', async () => {
  let writes = 0, reads = 0
  const { state } = page({ verifyRegistrationEligibility: async () => { writes++; return { code: 503001 } } })
  state.loadEligibility = async () => { reads++ }
  state.askEligible(state.elig.rows[0]); await state.onConfirm()
  state.askEligible(state.elig.rows[0]); await state.onConfirm()
  assert.equal(writes, 1); assert.equal(reads, 1); assert.equal(state.eligUnknown.batchId, '1')
})

test('incomplete or mismatched success is unknown instead of a fabricated receipt', async () => {
  for (const data of [{}, { registrationId: 'record', studentId: 'wrong', eligibilityStatus: 'ELIGIBLE' }]) {
    const { state } = page({ verifyRegistrationEligibility: async () => ({ code: 0, data }) })
    state.loadEligibility = async () => {}
    state.askEligible(state.elig.rows[0]); await state.onConfirm()
    assert.ok(state.eligUnknown); assert.equal(state.eligReceipt, null)
  }
})

test('failed list reads clear old rows and leave a retryable error', async () => {
  const { state } = page({ getRegistrationEligibility: async () => { throw new Error('网络不可用') } })
  await state.loadEligibility()
  assert.equal(state.selectedEligRow, null); assert.equal(state.elig.rows.length, 0)
  assert.equal(state.elig.loading, false); assert.equal(state.elig.error, '网络不可用')
})

test('continuing registration captures the exact eligibility batch, student and page for return', async () => {
  const { state } = page(); let saved, destination
  state.ctx.permissionPatterns.push('academicAffairs.registration.view')
  state.elig.pagination.page = 3
  state.$route = { query: { tab: 'eligibility' } }
  state.$router = { replace: async value => { state.$route.query = value.query }, push: value => { destination = value } }
  state.academicFlow = { captureReturn: () => { saved = state.$route.query; return 'return-1' } }
  await state.goRegistrationList()
  assert.equal(saved.batchId, '1'); assert.equal(saved.studentId, '1000000000000063602'); assert.equal(saved.page, '3')
  assert.equal(destination.path, '/admin/academic-affairs/registration/1'); assert.equal(destination.query.returnToken, 'return-1')
})

test('restoring an absent explicit student does not silently select another candidate', () => {
  const { state } = page()
  state.$route = { query: { studentId: 'missing' } }; state.selectedEligId = 'missing'
  state.reconcileSelectedEligibility()
  assert.equal(state.selectedEligRow, null); assert.equal(state.selectedEligId, 'missing'); assert.ok(state.elig.error)
})

test('unknown or missing eligibility states never open or execute verification', async () => {
  for (const status of ['UNKNOWN', '', null, undefined]) {
    let writes = 0
    const { state } = page({ verifyRegistrationEligibility: async () => { writes++; return { code: 0 } } })
    const row = state.elig.rows[0]
    row.eligibilityStatus = status
    assert.match(state.objectStatusText(row), /待确认/)
    assert.match(state.objectBlockText(row), /暂停/)
    assert.equal(state.knownEligibilityState(row), false)
    state.askEligible(row)
    state.openIneligible(row)
    assert.equal(state.confirm.visible, false)
    assert.equal(state.eligDrawer.visible, false)
    assert.equal(await state.verifyEligibilityTarget(state.captureEligibilityTarget(row), { result: 'ELIGIBLE' }), false)
    assert.equal(writes, 0)
  }
})

test('qualification evidence does not infer materials, roster revision or freshness from a successful result', () => {
  const { state } = page()
  state.elig.rows[0].eligibilityStatus = 'ELIGIBLE'
  state.elig.rows[0].eligibilityCheckedAt = '2026-09-08T07:44:59Z'
  state.selectedEligRow = state.elig.rows[0]
  const evidence = state.registrationEvidence
  for (const title of ['当前名单版本', '材料与事实依据', '证据新鲜度']) {
    assert.equal(evidence.find(item => item.title === title).type, 'warning')
  }
  assert.equal(state.registrationSteps[3].complete, false)
  state.selectedEligRow.eligibilityStatus = 'INELIGIBLE'
  assert.match(state.objectReasonText(state.selectedEligRow), /实际原因/)
  assert.doesNotMatch(state.objectReasonText(state.selectedEligRow), /补齐材料/)
})
