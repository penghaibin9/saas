import test from 'node:test'
import assert from 'node:assert/strict'
import * as rules from '../src/modules/platform/utils/tenantRuleDraft.mjs'
import { optionsInstance, deferred, plain, tenant } from './platform-workspace-test-support.mjs'

const path = '../src/modules/platform/components/TenantRulesWorkspace.vue'
const parentPath = '../src/modules/platform/views/control/PlatformControlTenantDetail.vue'
const id = tenant().tenantId
const projection = (version = 4, tenantId = id) => ({ tenantId, rules: { student: { studentNoRequired: true }, file: { uploadMaxSizeMb: 20, allowedFileTypes: ['pdf', 'docx'], unsupported: { nested: true } }, message: { name: '' } }, override: {}, overrideVersion: version })
function make(api = {}, dependencies = {}) {
  const out = optionsInstance(path, { tenant: tenant(), projection: projection() }, { platformControlHardeningApi: api, ...dependencies })
  out.state.initialize()
  return out
}
function edit(state) { state.draft.file.uploadMaxSizeMb = '30'; state.reason = '学校文件办理规则调整' }
const dataAfter = (request, version = request.expectedVersion + 1) => {
  const data = projection(version)
  for (const [group, fields] of Object.entries(request.rules)) { Object.assign(data.rules[group], fields); data.override[group] = { ...fields } }
  return data
}
const parent = (ref = {}) => optionsInstance(parentPath, { tab: 'rules', $refs: { rulesWorkspace: ref }, $route: { path: `/admin/platform/tenants/${id}`, fullPath: `/admin/platform/tenants/${id}?tab=rules`, params: { tenantId: id }, query: { tab: 'rules' } } })

for (const value of [null, undefined, true, false, '', ' ', '1.5', '-1', -1, NaN, Infinity, 1.5, {}, [], 9007199254740992]) {
  test(`untrusted rules version is rejected (${String(value)})`, () => assert.equal(rules.ruleVersion(value), null))
}
test('version zero is a valid first-write baseline', () => {
  const source = rules.rulesSnapshot(projection(0), id), draft = rules.editableDraft(source.rules)
  draft.student.studentNoRequired = false
  const request = rules.prepareRules(source, draft, '首次配置学校规则')
  assert.equal(request.expectedVersion, 0)
  assert.equal(rules.verifiedRulesReceipt(dataAfter(request), request).overrideVersion, 1)
})
test('school identity, source and version must all be present', () => {
  for (const data of [null, {}, { ...projection(), tenantId: '7' }, { ...projection(), tenantId: Number(id) }, { ...projection(), override: undefined }, { ...projection(), rules: [] }, { ...projection(), rules: { file: null } }]) assert.throws(() => rules.rulesSnapshot(data, id))
})
test('prototype keys are refused before draft or patch creation', () => {
  for (const document of ['{"__proto__":{"n":1}}', '{"file":{"constructor":1}}']) assert.throws(() => rules.rulesSnapshot({ ...projection(), rules: JSON.parse(document) }, id))
})
test('initial draft is detached and does not create changes for lists', () => {
  const source = projection(), snapshot = rules.rulesSnapshot(source, id), draft = rules.editableDraft(snapshot.rules)
  assert.equal(draft.file.allowedFileTypes, 'pdf\ndocx')
  assert.deepEqual(rules.ruleChanges(snapshot.rules, draft).changes, [])
  draft.file.uploadMaxSizeMb = 1
  assert.equal(source.rules.file.uploadMaxSizeMb, 20)
  assert.equal(snapshot.rules.file.uploadMaxSizeMb, 20)
})
test('only actual differences are submitted; inherited defaults stay inherited', () => {
  const { state } = make(); edit(state); state.review()
  assert.deepEqual(plain(state.prepared.rules), { file: { uploadMaxSizeMb: 30 } })
  assert.ok(!Object.hasOwn(state.prepared.rules, 'student'))
  assert.ok(!Object.hasOwn(state.prepared.rules.file, 'allowedFileTypes'))
  assert.deepEqual(plain(state.base.override), {})
})
test('integer input preserves zero and rejects empty, fractional, booleans and out-of-range values', () => {
  for (const value of ['', ' ', '1.2', '-1', true, 1000001, Infinity]) {
    const { state } = make(); edit(state); state.draft.file.uploadMaxSizeMb = value; state.review()
    assert.ok(state.delta.errors['file.uploadMaxSizeMb']); assert.equal(state.prepared, null)
  }
  const { state } = make(); edit(state); state.draft.file.uploadMaxSizeMb = '0'; state.review(); assert.equal(state.prepared.rules.file.uploadMaxSizeMb, 0)
})
test('file type lists remain arrays and unsupported structured values remain read-only', () => {
  const { state } = make(); edit(state); state.draft.file.allowedFileTypes = 'pdf, png\njpg，xlsx'; state.review()
  assert.deepEqual(plain(state.prepared.rules.file.allowedFileTypes), ['pdf', 'png', 'jpg', 'xlsx'])
  assert.equal(rules.ruleKind(state.base.rules.file.unsupported), 'readonly')
  assert.ok(!Object.hasOwn(state.prepared.rules.file, 'unsupported'))
})
test('structure tampering cannot become a replacement write', () => {
  const { state } = make(); edit(state); delete state.draft.student; state.review(); assert.equal(state.prepared, null)
})
test('numeric strings with no semantic change do not generate a write', () => {
  const { state } = make(); state.draft.file.uploadMaxSizeMb = '20'; state.reason = '没有实际修改的原因'; state.review(); assert.equal(state.prepared, null)
})
test('reason is required and immutable with the reviewed patch', () => {
  const { state } = make(); edit(state); state.reason = '短'; state.review(); assert.equal(state.phase, 'edit')
  state.reason = '五个字符的原因'; state.review(); assert.ok(Object.isFrozen(state.prepared)); assert.ok(Object.isFrozen(state.prepared.rules.file))
  assert.throws(() => { state.prepared.rules.file.uploadMaxSizeMb = 0 }, TypeError)
})
test('unchanged one-field toggle preserves its boolean type', () => {
  const { state } = make(); state.draft.student.studentNoRequired = false; state.reason = '学号填报要求调整'; state.review()
  assert.equal(state.prepared.rules.student.studentNoRequired, false)
})
test('search spans business groups without mutating a draft', () => {
  const { state } = make({}, { PLATFORM_RULE_GROUP_LABELS: { file: '文件规则' }, PLATFORM_RULE_LABELS: { uploadMaxSizeMb: '文件大小' } })
  state.search = '文件大小'; assert.equal(state.visibleFields.length, 1); assert.equal(state.visibleFields[0].path, 'file.uploadMaxSizeMb'); assert.equal(state.delta.changes.length, 0)
})
test('write permission is root-only and is rechecked after review', async () => {
  let root = true, writes = 0
  const { state } = make({ putRules: async () => { writes++ } }, { isPlatformRoot: () => root })
  edit(state); state.review(); root = false; await state.submit(); assert.equal(writes, 0)
})
test('missing or failed permission context never unlocks editing', () => {
  for (const deps of [{ getPermissionPatterns: () => null }, { getRbacLoadFailed: () => 'failed' }, { isPlatformRoot: () => false }]) {
    const { state } = make({}, deps); edit(state); state.review(); assert.equal(state.mayWrite(), false); assert.equal(state.prepared, null)
  }
})
test('the exact reviewed tenant, sparse body, version and reason reach the existing API', async () => {
  let args
  const { state } = make({ putRules: async (...values) => { args = values; return { code: 0, data: dataAfter(state.prepared) } } })
  edit(state); state.review(); await state.submit()
  assert.deepEqual(plain(args), [id, { file: { uploadMaxSizeMb: 30 } }, 4, '学校文件办理规则调整'])
  assert.equal(state.phase, 'saved'); assert.equal(state.base.overrideVersion, 5); assert.equal(state.protectNavigation, false)
})
test('edits between review and submit invalidate the prepared write', async () => {
  let writes = 0
  const { state } = make({ putRules: async () => { writes++ } }); edit(state); state.review(); state.reason = '核对后又更改了原因'; await state.submit()
  assert.equal(writes, 0); assert.equal(state.phase, 'edit'); assert.equal(state.prepared, null)
})
test('double clicking produces one write and cannot resubmit a success', async () => {
  const pending = deferred(); let writes = 0
  const { state } = make({ putRules: () => { writes++; return pending.promise } }); edit(state); state.review()
  const first = state.submit(), second = state.submit(); assert.equal(writes, 1); pending.resolve({ code: 0, data: dataAfter(state.prepared) }); await Promise.all([first, second])
  await state.submit(); assert.equal(writes, 1); assert.equal(state.busy, false)
})
for (const variant of ['null', 'wrong-tenant', 'same-version', 'jumped-version', 'missing-override', 'wrong-value']) {
  test(`invalid success receipt cannot display saved: ${variant}`, async () => {
    const { state } = make({ putRules: async () => {
      let data = dataAfter(state.prepared)
      if (variant === 'null') data = null
      if (variant === 'wrong-tenant') data.tenantId = '7'
      if (variant === 'same-version') data.overrideVersion = 4
      if (variant === 'jumped-version') data.overrideVersion = 6
      if (variant === 'missing-override') data.override = {}
      if (variant === 'wrong-value') data.rules.file.uploadMaxSizeMb = 20
      return { code: 0, data }
    } })
    edit(state); state.review(); await state.submit(); assert.equal(state.phase, 'uncertain'); assert.equal(state.protectNavigation, true)
  })
}
test('409 retains the old draft but never retries or auto-merges', async () => {
  let writes = 0, reads = 0
  const { state } = make({ putRules: async () => { writes++; return { code: 409001, bizCode: 'DATA_CONFLICT', message: '版本冲突' } } }, { platformControlApi: { getRules: async () => { reads++; return { code: 0, data: { ...projection(5), override: { student: { studentNoRequired: false } }, rules: { ...projection().rules, student: { studentNoRequired: false } } } } } } })
  edit(state); state.review(); await state.submit(); await state.submit(); assert.equal(writes, 1); assert.equal(reads, 0); assert.equal(state.phase, 'conflict')
  await state.inspectCurrent(); assert.equal(reads, 1); assert.equal(writes, 1); assert.equal(state.draft.file.uploadMaxSizeMb, '30')
  state.acceptLatest(); assert.equal(state.phase, 'edit'); assert.equal(state.base.overrideVersion, 5); assert.equal(state.draft.file.uploadMaxSizeMb, 20); assert.equal(state.draft.student.studentNoRequired, false); assert.equal(state.prepared, null)
})
test('timeout permits readback only; matching readback is not a success receipt', async () => {
  let writes = 0
  const { state } = make({ putRules: async () => { writes++; throw new Error('timeout') } }, { platformControlApi: { getRules: async () => ({ code: 0, data: dataAfter(state.prepared) }) } })
  edit(state); state.review(); await state.submit(); await state.inspectCurrent(); assert.equal(state.phase, 'uncertain'); assert.equal(state.readbackRows[0].matches, true)
  state.acceptLatest(); state.review(); await state.submit(); assert.equal(state.phase, 'uncertain'); assert.equal(writes, 1)
})
test('failed readback clears the previous inspection instead of showing stale confirmation', async () => {
  let reads = 0
  const { state } = make({ putRules: async () => ({ code: 500, message: 'unknown' }) }, { platformControlApi: { getRules: async () => ++reads === 1 ? { code: 0, data: projection(5) } : { code: 403, message: '读取被拒绝' } } })
  edit(state); state.review(); await state.submit(); await state.inspectCurrent(); assert.ok(state.latest); await state.inspectCurrent(); assert.equal(state.latest, null); assert.equal(state.error, '读取被拒绝')
})
test('older readback and cross-tenant readback cannot unlock a new draft', async () => {
  for (const data of [projection(3), projection(5, '7')]) {
    const { state } = make({ putRules: async () => ({ code: 409 }) }, { platformControlApi: { getRules: async () => ({ code: 0, data }) } })
    edit(state); state.review(); await state.submit(); await state.inspectCurrent(); assert.equal(state.latest, null); assert.ok(state.error)
  }
})
test('late write from school A is discarded after switching to B', async () => {
  const pending = deferred()
  const { state, definition } = make({ putRules: () => pending.promise }); edit(state); state.review(); const request = state.prepared; const writing = state.submit()
  state.tenant = tenant('7'); state.projection = projection(8, '7'); definition.watch['tenant.tenantId'].call(state)
  pending.resolve({ code: 0, data: dataAfter(request) }); await writing
  assert.equal(state.base.tenantId, '7'); assert.equal(state.base.overrideVersion, 8); assert.equal(state.phase, 'edit'); assert.equal(state.prepared, null)
})
test('unmount invalidates pending readback and clears in-memory change records', async () => {
  const pending = deferred()
  const { state, definition } = make({ putRules: async () => ({ code: 500 }) }, { platformControlApi: { getRules: () => pending.promise } })
  edit(state); state.review(); await state.submit(); const reading = state.inspectCurrent(); definition.beforeUnmount.call(state); pending.resolve({ code: 0, data: projection(5) }); await reading
  assert.equal(state.latest, null); assert.equal(state.prepared, null); assert.deepEqual(plain(state.draft), {})
})
test('completed change begins a fresh draft at returned server version', async () => {
  const { state } = make({ putRules: async () => ({ code: 0, data: dataAfter(state.prepared) }) }); edit(state); state.review(); await state.submit(); state.beginNext()
  assert.equal(state.phase, 'edit'); assert.equal(state.base.overrideVersion, 5); assert.equal(state.delta.changes.length, 0); assert.equal(state.reason, '')
})
test('beforeunload warns only when work is at risk', () => {
  const { state } = make(); let prevented = 0; const event = { preventDefault() { prevented++ } }
  state.beforeUnload(event); assert.equal(prevented, 0); edit(state); state.beforeUnload(event); assert.equal(prevented, 1); assert.equal(event.returnValue, '')
})
test('the parent has one rules writer owner and no native reason prompt', () => {
  const { source } = parent()
  assert.doesNotMatch(source, /saveRules|platformControlHardeningApi|window\.prompt/)
  assert.match(source, /<TenantRulesWorkspace[^>]*:projection="rulesProjection"/)
  assert.match(source, /rulesSnapshot\(data, tenantId\)/)
})
test('parent tab click preserves a protected draft until explicit leave', () => {
  const { state, calls } = parent({ protectNavigation: true, busy: false })
  state.switchTab('brand'); assert.equal(state.tab, 'rules'); assert.equal(calls.length, 0); assert.equal(state.pendingRulesNavigation.query.tab, 'brand')
})
test('query/id route reuse and full route leave both use the draft guard', () => {
  const { state, definition } = parent({ protectNavigation: true })
  const from = { fullPath: state.$route.fullPath }, to = { fullPath: '/admin/platform/tenants/7?tab=rules' }
  assert.equal(definition.beforeRouteUpdate.call(state, to, from), false)
  assert.equal(definition.beforeRouteLeave.call(state, { fullPath: '/admin/platform/tenants' }), false)
  assert.equal(definition.beforeRouteUpdate.call(state, from, from), true)
})
test('busy rule mutation cannot be left even when confirmation was previously opened', async () => {
  const { state, calls } = parent({ protectNavigation: true, busy: true }); state.pendingRulesNavigation = '/admin/platform/tenants'; await state.leaveRules(); assert.equal(calls.length, 0)
})
test('explicit leave bypass is scoped to that navigation and failure retains the draft', async () => {
  const { state } = parent({ protectNavigation: true, busy: false }); state.pendingRulesNavigation = '/admin/platform/tenants'
  state.$router.push = async () => { assert.equal(state.rulesLeaveApproved, true); return { type: 'blocked' } }
  await state.leaveRules(); assert.equal(state.rulesLeaveApproved, false); assert.ok(state.pendingRulesNavigation); assert.equal(state.$refs.rulesWorkspace.protectNavigation, true)
})
test('accepted leave clears its pending destination without performing any business write', async () => {
  const { state, calls } = parent({ protectNavigation: true, busy: false }); state.pendingRulesNavigation = '/admin/platform/tenants'; await state.leaveRules(); assert.equal(state.pendingRulesNavigation, null); assert.equal(calls[0][0], 'push')
})
test('rule tab read requires the real tenant id and complete override projection', async () => {
  const { state } = parent(); state.$refs = {}; state.platformControlApi = undefined
  const out = optionsInstance(parentPath, { ...state, tab: 'rules' }, { platformControlApi: { getRules: async () => ({ code: 0, data: { rules: { file: { n: 1 } }, overrideVersion: 0 } }) } })
  await out.state.loadTab('rules'); assert.equal(out.state.rulesProjection, null); assert.ok(out.state.tabError)
})

test('untouched list values are not normalized into unrequested overrides', () => {
  const base = { file: { labels: ['  literal  ', 'one,two', ''] } }
  const draft = rules.editableDraft(base)
  const delta = rules.ruleChanges(base, draft)
  assert.deepEqual(delta.changes, [])
  assert.deepEqual(delta.patch, {})
})
test('double leave confirmation schedules only one navigation', async () => {
  const pending = deferred(); let pushes = 0
  const { state } = parent({ protectNavigation: true, busy: false }); state.pendingRulesNavigation = '/admin/platform/tenants'
  state.$router.push = () => { pushes++; return pending.promise }
  const first = state.leaveRules(), second = state.leaveRules()
  assert.equal(pushes, 1); pending.resolve(undefined); await Promise.all([first, second]); assert.equal(state.rulesLeaveApproved, false)
})
