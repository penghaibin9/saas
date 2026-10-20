import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { academicRouteState } from '../src/modules/academicAffairs/academicFlowContext.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue', import.meta.url), 'utf8')
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const studentId = '9007199254740993002'
const deferral = (extra = {}) => ({ deferralId: '9007199254740993001', batchId: '101', studentId, status: 'PENDING',
  reason: '材料待补齐', requestedUntil: null, reviewNote: '', reviewedAt: null, ...extra })
const exception = (extra = {}) => ({ exceptionId: '9007199254740993003', batchId: '101', studentId, status: 'OPEN',
  exceptionType: 'OTHER', description: '材料缺失', resolutionNote: '', resolvedAt: null, ...extra })
function page(api = {}) {
  const writes = [], reads = [], reloads = [], notices = []
  let officialDeferral = deferral(), officialException = exception()
  const sandbox = { matchPermission, academicRouteState, toast: { error() {}, success: value => notices.push(value) },
    academicAffairsApi: {
      applyRegistrationDeferral: async (batch, body) => { writes.push(['apply', batch, body]); officialDeferral = deferral({ reason: body.reason }); return { code: 0, data: officialDeferral } },
      reviewRegistrationDeferral: async (id, body) => { writes.push(['review', id, body]); officialDeferral = deferral({ status: body.action === 'APPROVE' ? 'APPROVED' : 'REJECTED', reviewNote: body.note }); return { code: 0, data: officialDeferral } },
      resolveRegistrationException: async (id, note) => { writes.push(['resolve', id, note]); officialException = exception({ status: 'RESOLVED', resolutionNote: note }); return { code: 0, data: officialException } },
      getRegistrationDeferrals: async query => { reads.push(['deferral', query]); return { code: 0, data: { list: [officialDeferral], total: 1 } } },
      getRegistrationExceptions: async query => { reads.push(['exception', query]); return { code: 0, data: { list: [officialException], total: 1 } } },
      ...api
    } }
  for (const name of source.match(/components:\s*{([\s\S]*?)}/)[1].split(',').map(value => value.trim()).filter(Boolean)) sandbox[name] = {}
  vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?$/gm, '').replace('export default', 'component ='), sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, batchId: '101', tab: 'deferral', ctx: { permissionPatterns: [
    'academicAffairs.registration.deferral.apply', 'academicAffairs.registration.deferral.approve', 'academicAffairs.registration.deferral.view',
    'academicAffairs.registration.exception.resolve', 'academicAffairs.registration.exception.view'
  ] } }
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  state.defer.rows = [deferral()]; state.exc.rows = [exception()]
  state.loadCurrentTab = () => {}
  state.loadDeferrals = async () => { reloads.push(['deferral', state.batchId]); state.queueVersions.defer++ }
  state.loadExceptions = async () => { reloads.push(['exception', state.batchId]); state.queueVersions.exc++ }
  return { state, writes, reads, reloads, notices, component }
}
function openApply(state) {
  state.openDeferralApply(); Object.assign(state.deferDrawer, { studentId, reason: '材料待补齐', requestedUntil: '2026-09-20' })
}
function resolve(state, reason = '已补齐材料') {
  state.tab = 'exception'; state.askResolveException(state.exc.rows[0]); return state.onResolveConfirm({ reason })
}

test('deferral creation freezes identifiers and body and confirms the exact official row', async () => {
  const { state, writes, reads, notices } = page(); openApply(state); state.defer.status = 'REJECTED'
  await state.submitDeferralApply()
  assert.equal(writes[0][1], '101'); assert.equal(writes[0][2].studentId, studentId)
  assert.equal(writes[0][2].requestedUntil, '2026-09-20')
  assert.deepEqual(JSON.parse(JSON.stringify(reads)), [['deferral', { batchId: '101', page: 1, pageSize: 100 }]])
  assert.equal(state.registrationWrite.receipt.objectId, deferral().deferralId)
  assert.equal(state.registrationWrite.receipt.status, 'PENDING'); assert.equal(state.deferDrawer.visible, false)
  assert.equal(state.registrationWrite.pending, null); assert.equal(notices.length, 0)
})

test('deferral approval and rejection send the captured exact ID and read their actual status', async () => {
  for (const action of ['APPROVE', 'REJECT']) {
    const { state, writes } = page(); state.askDeferralReview(state.defer.rows[0], action)
    if (action === 'APPROVE') await state.onConfirm(); else await state.onDeferRejectConfirm({ reason: '材料仍不完整' })
    assert.equal(writes[0][1], deferral().deferralId); assert.equal(writes[0][2].action, action)
    assert.equal(state.registrationWrite.receipt.status, action === 'APPROVE' ? 'APPROVED' : 'REJECTED')
    assert.equal(state.registrationWrite.receipt.commandConfirmed, true)
  }
})

test('exception resolution sends the original object and reason without claiming registration eligibility changed', async () => {
  const { state, writes, reads } = page(); await resolve(state)
  assert.equal(writes[0][1], exception().exceptionId); assert.equal(writes[0][2], '已补齐材料')
  assert.equal(reads[0][1].batchId, '101'); assert.equal(reads[0][1].status, undefined)
  assert.equal(state.registrationWrite.receipt.status, 'RESOLVED'); assert.equal(state.resolveDialog.visible, false)
})

test('in-flight creation rejects double clicks and drawer close', async () => {
  const reply = deferred(); let writes = 0
  const { state } = page({ applyRegistrationDeferral: () => { writes++; return reply.promise } }); openApply(state)
  const pending = state.submitDeferralApply(); await state.submitDeferralApply(); state.closeDeferralApply()
  assert.equal(writes, 1); assert.equal(state.deferDrawer.visible, true)
  reply.resolve({ code: 0, data: deferral() }); await pending
  assert.equal(state.registrationWrite.busy, false)
})

test('new batch or identity invalidates an earlier deferral form without writing', async () => {
  for (const change of [state => { state.batchId = '202' }, state => { state.ctx.role = 'other' }]) {
    const { state, writes } = page(); openApply(state); change(state); await state.submitDeferralApply()
    assert.equal(writes.length, 0); assert.equal(state.deferDrawer.reason, '材料待补齐')
  }
})

test('changed row evidence, page or scope cannot dispatch an old review confirmation', async () => {
  for (const change of [state => { state.defer.rows[0].status = 'REJECTED' }, state => { state.defer.rows[0].reason = '已变化' },
    state => { state.queueVersions.defer++ }, state => { state.ctx.role = 'other' }, state => { state.batchId = '202' }]) {
    const { state, writes } = page(); state.askDeferralReview(state.defer.rows[0], 'APPROVE'); change(state); await state.onConfirm()
    assert.equal(writes.length, 0)
  }
})

test('changed exception evidence invalidates the captured resolution dialog', async () => {
  const { state, writes } = page(); state.tab = 'exception'; state.askResolveException(state.exc.rows[0])
  state.exc.rows[0].status = 'RESOLVED'; await state.onResolveConfirm({ reason: '旧操作说明' })
  assert.equal(writes.length, 0)
})

test('late old-batch creation success leaves a later draft and queue alone', async () => {
  const reply = deferred(), { state, reloads, notices } = page({ applyRegistrationDeferral: () => reply.promise })
  openApply(state); const pending = state.submitDeferralApply(); state.batchId = '202'; state.onBatchChange()
  const other = { visible: true, studentId: 'other', reason: '新草稿', saving: false }; state.deferDrawer = other
  reply.resolve({ code: 0, data: deferral() }); await pending
  assert.equal(state.deferDrawer, other); assert.equal(other.visible, true); assert.equal(other.reason, '新草稿')
  assert.equal(reloads.length, 0); assert.equal(notices.length, 0)
})

test('403 clears only the original action queue and input, without success', async () => {
  for (const kind of ['apply', 'review', 'resolve']) {
    const apiName = { apply: 'applyRegistrationDeferral', review: 'reviewRegistrationDeferral', resolve: 'resolveRegistrationException' }[kind]
    const { state } = page({ [apiName]: async () => ({ code: 403001, message: '无权办理' }) })
    if (kind === 'apply') { openApply(state); await state.submitDeferralApply() }
    else if (kind === 'review') { state.askDeferralReview(state.defer.rows[0], 'REJECT'); await state.onDeferRejectConfirm({ reason: '保留的理由' }) }
    else await resolve(state)
    assert.equal(state[kind === 'resolve' ? 'exc' : 'defer'].rows.length, 0)
    assert.equal(state.registrationWrite.receipt, null); assert.equal(state.registrationWrite.pending, null)
    assert.equal(state.canRunRegistrationAction(kind === 'resolve' ? 'exception.resolve' : 'deferral.apply'), false)
    if (kind !== 'resolve') assert.equal(state.deferDrawer.reason, '')
  }
})

test('409 retains the reason and rereads the review queue before allowing a fresh confirmation', async () => {
  const { state, reloads } = page({ reviewRegistrationDeferral: async () => ({ code: 409001, message: '申请已由另一岗位处理' }) })
  state.askDeferralReview(state.defer.rows[0], 'REJECT'); const target = state.deferRejectDialog.target
  await state.onDeferRejectConfirm({ reason: '材料仍不完整' })
  assert.equal(state.deferRejectDialog.visible, true); assert.equal(state.registrationWrite.context.note, '材料仍不完整')
  assert.equal(state.registrationWrite.error, '申请已由另一岗位处理'); assert.equal(state.registrationWrite.receipt, null)
  assert.equal(reloads.length, 1); assert.equal(state.registrationTargetCurrent(target), false)
})

test('apply conflict retains all original form fields', async () => {
  const { state } = page({ applyRegistrationDeferral: async () => ({ code: 409001, message: '已有待审申请' }) })
  openApply(state); await state.submitDeferralApply()
  assert.equal(state.deferDrawer.reason, '材料待补齐'); assert.equal(state.deferDrawer.requestedUntil, '2026-09-20')
  assert.equal(state.deferDrawer.formError, '已有待审申请'); assert.equal(state.deferDrawer.visible, true)
})

test('a creation timeout without an ID stays locked across batch and tab changes', async () => {
  let writes = 0
  const { state, reads } = page({ applyRegistrationDeferral: async () => { writes++; return { code: 503001 } } })
  openApply(state); await state.submitDeferralApply(); state.switchTab('exception'); state.batchId = '202'; state.onBatchChange()
  state.switchTab('deferral'); state.openDeferralApply(); await state.submitDeferralApply()
  assert.equal(writes, 1); assert.equal(reads.length, 0); assert.ok(state.registrationWrite.pending)
  assert.equal(state.registrationWrite.pending.batchId, '101'); assert.equal(state.registrationWrite.pending.objectId, '')
})

test('a lost review response reads the known ID but cannot turn another observed approval into this command success', async () => {
  let writes = 0
  const { state, reads } = page({ reviewRegistrationDeferral: async () => { writes++; return { code: 503001 } },
    getRegistrationDeferrals: async query => { reads.push(['deferral', query]); return { code: 0, data: { list: [deferral({ status: 'APPROVED' })], total: 1 } } } })
  state.askDeferralReview(state.defer.rows[0], 'APPROVE'); await state.onConfirm()
  assert.equal(reads[0][1].status, undefined); assert.equal(state.registrationWrite.receipt.status, 'APPROVED')
  assert.equal(state.registrationWrite.receipt.commandConfirmed, false); assert.ok(state.registrationWrite.pending)
  state.askDeferralReview(state.defer.rows[0], 'APPROVE'); await state.onConfirm(); assert.equal(writes, 1)
})

test('network errors and incomplete or wrong-object replies remain unknown for exception resolution', async () => {
  for (const response of [() => { throw new Error('network') }, () => ({}), () => ({ code: 503 }), () => ({ code: 0, data: {} }),
    () => ({ code: 0, data: exception({ studentId: 'wrong', status: 'RESOLVED' }) })]) {
    const { state } = page({ resolveRegistrationException: async () => response() }); await resolve(state)
    assert.ok(state.registrationWrite.pending); assert.equal(state.registrationWrite.receipt?.commandConfirmed, false)
    assert.equal(state.registrationWrite.busy, false)
  }
})

test('denied official readback retains the known ID lock and clears the original exception queue', async () => {
  const { state } = page({ getRegistrationExceptions: async () => ({ code: 403001 }) })
  await resolve(state)
  assert.equal(state.exc.rows.length, 0); assert.equal(state.resolveDialog.visible, false)
  assert.equal(state.registrationWrite.receipt, null); assert.equal(state.registrationWrite.pending.objectId, exception().exceptionId)
  assert.equal(state.registrationWrite.pending.denied, true); assert.equal(state.canRunRegistrationAction('exception.resolve'), false)
})

test('formal record lookup remains bounded and a known successful receipt can be verified later', async () => {
  let reads = 0, found = false
  const otherRows = Array.from({ length: 100 }, (_, index) => exception({ exceptionId: String(index) }))
  const { state } = page({ getRegistrationExceptions: async () => { reads++; return { code: 0, data: { list: found ? [exception({ status: 'RESOLVED' })] : otherRows, total: 10000 } } } })
  await resolve(state); assert.equal(reads, 5); assert.ok(state.registrationWrite.pending)
  assert.equal(state.registrationWrite.receipt, null); found = true
  assert.equal(await state.verifyRegistrationAction(), true); assert.equal(reads, 6); assert.equal(state.registrationWrite.pending, null)
})

test('an identity switch during official readback cannot reveal the old result', async () => {
  const reply = deferred(), { state } = page({ getRegistrationExceptions: () => reply.promise })
  const pending = resolve(state); await Promise.resolve(); state.ctx.role = 'another'; state.invalidateEligibilityContext()
  reply.resolve({ code: 0, data: { list: [exception({ status: 'RESOLVED' })], total: 1 } }); await pending
  assert.equal(state.registrationWrite.receipt, null); assert.ok(state.registrationWrite.pending)
  assert.equal(state.canReadRegistrationAction(state.registrationWrite.pending), false)
})

test('original command permissions and required reasons cannot be bypassed by direct handlers', async () => {
  const { state, writes } = page(); state.ctx.permissionPatterns = ['academicAffairs.registration.deferral.view', 'academicAffairs.registration.exception.view']
  state.openDeferralApply(); await state.submitDeferralApply(); state.askDeferralReview(state.defer.rows[0], 'APPROVE'); await state.onConfirm()
  await resolve(state); assert.equal(writes.length, 0)
})
