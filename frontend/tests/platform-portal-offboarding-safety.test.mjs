import test from 'node:test'
import assert from 'node:assert/strict'
import { setImmediate } from 'node:timers'
import { optionsInstance, deferred } from './platform-workspace-test-support.mjs'
const ID = '1000000000000000003'
const modules = ['dashboard','profile','orientation','campusService','academic','internship','graduation','employment','messages']
const features = ['upload','export','proofDownload','profileCorrection','messageReceipt','materialCenter','workItems','aiAssistant']
const cfg = () => ({ enabled: true, portalName: '学校门户', portalUrl: '/portal/', package: { code: 'standard' }, modules: Object.fromEntries(modules.map(k => [k, true])), features: Object.fromEntries(features.map(k => [k, k !== 'aiAssistant'])) })
const ui = { normalizeUiError: (e, o) => ({ userMessage: e?.message || o.fallback }), safeEnumLabel: o => o.dictionary[o.value] || o.unknownLabel }
const portal = api => optionsInstance('../src/modules/platform/components/StudentPortalConfigPanel.vue', { tenantId: ID }, { ...ui, studentPortalConfigApi: api, URL })
const preview = () => ({ tenantId: ID, effectiveState: { version: 4 }, counts: { legalHoldFileCount: 0, activeFileJobCount: 0 }, registry: { complete: true }, blockers: [], activeJobId: null })
const job = () => ({ tenantId: ID, jobId: '11', state: 'RETENTION', cancellable: true, finalExportSha256: 'a'.repeat(64), retentionUntil: '2020-01-01T00:00:00Z' })
const offboard = (api = {}) => optionsInstance('../src/modules/platform/components/TenantOffboardingPanel.vue', { tenantId: ID, tenant: {}, tenant360: {} }, { platformStatusLabel: x => x, platformSecurityOpsApi: { previewTenantOffboarding: async () => preview(), getTenantOffboarding: async () => null, getMfaStatus: async () => ({ enabled: false }), ...api }, clearTimeout, setTimeout, window: { confirm: () => true } })

test('portal read failure blocks both saving and restoring defaults', async () => {
  let writes = 0
  const { state } = portal({ get: async () => { throw new Error('数据库暂不可用') }, save: async () => { writes++ } })
  await state.load(); state.restore(); await state.save()
  assert.equal(state.form, null); assert.equal(state.ready, false); assert.equal(writes, 0); assert.equal(state.loadError, '数据库暂不可用')
})
for (const bad of [null, {}, { ...cfg(), modules: {} }, { ...cfg(), features: [] }, { ...cfg(), package: { code: 'unknown' } }, { ...cfg(), enabled: 'false' }]) {
  test('incomplete portal response never becomes a default form: ' + JSON.stringify(bad).slice(0, 40), async () => {
    const { state } = portal({ get: async () => bad }); await state.load(); assert.equal(state.ready, false); assert.equal(state.form, null)
  })
}
test('portal saves a frozen body and renders the server-constrained response', async () => {
  let sent
  const response = cfg(); response.features.export = false
  const { state } = portal({ get: async () => cfg(), save: async (id, body) => { sent = { id, body }; return response } })
  await state.load(); state.form.portalName = '修改后的名称'; await state.save()
  assert.equal(sent.id, ID); assert.equal(sent.body.portalName, '修改后的名称'); assert.equal(state.form.features.export, false)
  assert.equal(state.dirty, false); assert.equal(state.saving, false); assert.ok(state.msg.includes('服务器返回值'))
})
test('portal duplicate click produces exactly one save', async () => {
  let writes = 0; const pending = deferred()
  const { state } = portal({ get: async () => cfg(), save: () => { writes++; return pending.promise } })
  await state.load(); state.form.enabled = false
  const a = state.save(), b = state.save(); assert.equal(writes, 1)
  pending.resolve({ ...cfg(), enabled: false }); await Promise.all([a, b]); assert.equal(state.dirty, false)
})
test('portal timeout is not retryable until explicit readback and acknowledgement', async () => {
  let writes = 0
  const { state } = portal({ get: async () => cfg(), save: async () => { writes++; throw new Error('timeout') } })
  await state.load(); state.form.enabled = false; await state.save(); await state.save(); assert.equal(writes, 1)
  assert.equal(state.uncertain, true); state.finishVerification(); assert.equal(state.uncertain, true)
  await state.load(); assert.equal(state.uncertain, true); assert.equal(state.inspected, true)
  state.finishVerification(); assert.equal(state.uncertain, false)
})
test('portal late read cannot cross a reused school object', async () => {
  const pending = deferred(); let reads = 0
  const { state } = portal({ get: () => ++reads === 1 ? pending.promise : Promise.resolve({ ...cfg(), portalName: '学校乙' }) })
  const first = state.load(); state.tenantId = '7'; await state.load(); pending.resolve(cfg()); await first
  assert.equal(state.form.portalName, '学校乙'); assert.equal(state.loading, false)
})
test('portal late write cannot overwrite another school after route reuse', async () => {
  const pending = deferred()
  const { state, definition } = portal({ get: async () => cfg(), save: () => pending.promise })
  await state.load(); state.form.enabled = false; const writing = state.save()
  state.tenantId = '7'; definition.watch.tenantId.call(state); await new Promise(resolve => setImmediate(resolve))
  pending.resolve({ ...cfg(), enabled: false }); await writing; assert.equal(state.form.enabled, true); assert.equal(state.msg, '')
})
test('portal unload invalidates reads and warns about unsaved work', async () => {
  const pending = deferred(); const { state, definition } = portal({ get: () => pending.promise })
  const read = state.load(); definition.beforeUnmount.call(state); pending.resolve(cfg()); await read; assert.equal(state.ready, false)
})
test('unsafe numeric school identifiers never produce an API read', async () => {
  let reads = 0; const { state } = portal({ get: async () => { reads++; return cfg() } })
  state.tenantId = Number(ID); await state.load(); assert.equal(reads, 0); assert.equal(state.ready, false)
})
for (const value of [undefined, null, '', false, -1, 1.5, 'bad', 1]) {
  test('offboarding missing or positive legal-hold evidence blocks purge: ' + String(value), async () => {
    const p = preview(); p.counts.legalHoldFileCount = value
    const { state } = offboard({ previewTenantOffboarding: async () => p, getTenantOffboarding: async () => job() })
    await state.load(); assert.equal(state.purgePrechecksPass, false); assert.equal(state.canExecutePurge, false)
  })
}
test('offboarding complete zero counts permit only prechecks, not unauthenticated execution', async () => {
  const { state } = offboard({ getTenantOffboarding: async () => job() }); await state.load()
  assert.equal(state.purgePrechecksPass, true); assert.equal(state.canExecutePurge, false)
})
test('active file jobs, unknown blockers or nonboolean registry completeness block prechecks', async () => {
  for (const change of [p => { p.counts.activeFileJobCount = null }, p => { p.counts.activeFileJobCount = 1 }, p => { delete p.blockers }, p => { p.registry.complete = 'true' }, p => { p.blockers = [{ code: 'UNCLASSIFIED' }] }]) {
    const p = preview(); change(p); const { state } = offboard({ previewTenantOffboarding: async () => p, getTenantOffboarding: async () => job() })
    await state.load(); assert.equal(state.purgePrechecksPass, false)
  }
})
test('offboarding read exception clears stale task data', async () => {
  const { state } = offboard({ previewTenantOffboarding: async () => { throw new Error('offline') } })
  state.job = job(); state.preview = preview(); await state.load()
  assert.equal(state.job, null); assert.equal(state.preview, null); assert.equal(state.ready, false); assert.equal(state.canStartNew, false)
})
test('offboarding wrong-school task or preview must not unlock actions', async () => {
  for (const api of [{ getTenantOffboarding: async () => ({ ...job(), tenantId: '7' }) }, { previewTenantOffboarding: async () => ({ ...preview(), tenantId: '7' }) }, { previewTenantOffboarding: async () => ({ ...preview(), effectiveState: {} }) }]) {
    const { state } = offboard(api); await state.load(); assert.equal(state.ready, false); assert.ok(state.error)
  }
})
test('offboarding latest read wins across school switches', async () => {
  const first = deferred(); let n = 0
  const { state } = offboard({ previewTenantOffboarding: () => ++n === 1 ? first.promise : Promise.resolve({ ...preview(), tenantId: '7' }) })
  const read = state.load(); state.tenantId = '7'; await state.load(); first.resolve(preview()); await read
  assert.equal(state.preview.tenantId, '7'); assert.equal(state.loading, false)
})
test('reversible offboarding request is single-shot and preserves expected version', async () => {
  const pending = deferred(); let writes = 0, body
  const { state } = offboard({ requestTenantOffboarding: (id, input) => { assert.equal(id, ID); writes++; body = input; return pending.promise } })
  await state.load(); state.requestForm.reason = '学校确认终止服务并进行数据交付'
  const a = state.requestOffboarding(), b = state.requestOffboarding(); assert.equal(writes, 1); assert.equal(body.expectedVersion, 4)
  pending.resolve({ ...job(), state: 'FROZEN_READONLY' }); await Promise.all([a, b]); assert.equal(state.working, false)
})
test('uncertain reversible offboarding request is blocked until readback', async () => {
  let writes = 0; const { state } = offboard({ requestTenantOffboarding: async () => { writes++; throw new Error('timeout') } })
  await state.load(); state.requestForm.reason = '学校确认终止服务并进行数据交付'
  await state.requestOffboarding(); await state.requestOffboarding(); assert.equal(writes, 1); assert.equal(state.uncertain, true)
  await state.load(); assert.equal(state.uncertain, true); assert.equal(state.inspected, true)
})
test('late cancellation does not clear the new school draft or emit changed', async () => {
  const pending = deferred(); const { state, calls } = offboard({ getTenantOffboarding: async () => job(), cancelTenantOffboarding: () => pending.promise })
  await state.load(); state.cancelReason = '学校决定继续使用'; const writing = state.cancelOffboarding()
  state.tenantId = '7'; state.epoch++; state.cancelReason = '学校乙原因'; pending.resolve({ ...job(), state: 'CANCELLED' }); await writing
  assert.equal(state.cancelReason, '学校乙原因'); assert.equal(calls.length, 0)
})
test('detail route guards protect portal and offboarding just like rules', () => {
  for (const [tab, ref] of [['studentPortal', 'portalWorkspace'], ['offboarding','offboardingWorkspace']]) {
    const { state } = optionsInstance('../src/modules/platform/views/control/PlatformControlTenantDetail.vue', { tab, $refs: { [ref]: { protectNavigation: true, busy: false } } })
    state.switchTab('brand'); assert.equal(state.tab, tab); assert.ok(state.pendingRulesNavigation)
  }
})

test('offboarding unload invalidates late replies and destroys temporary grants', () => {
  const { state, definition } = offboard()
  state.mfaGrant = { accessToken: 'test-only-not-a-session', expiresAt: Date.now() + 1000 }
  state.mfaCode = 'unused'
  const epoch = state.epoch
  definition.beforeUnmount.call(state)
  assert.equal(state.epoch, epoch + 1)
  assert.equal(state.mfaGrant, null)
  assert.equal(state.mfaCode, '')
})
