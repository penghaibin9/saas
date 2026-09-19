import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'

function workspace(api) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const claims = { tenantId: 'test-school', userId: 'test-user', currentRoleCode: 'ACADEMIC_ADMIN' }
  const sandbox = { dependencies: { academicStatsSnapshotApi: api, academicIdentity, currentUserFromToken: () => claims, matchPermission, getPermissionPatterns: () => ['*'], toast: { success() {} } } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { contextFilters: {}, ctx: {}, _component: component, _claims: claims }
  Object.assign(state, component.data.call(state), component.methods)
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return state
}

test('snapshot list consumes the shared client unwrapped response, including empty schools', async () => {
  const state = workspace({ list: async () => ({ list: [], total: 0 }) })
  await state.load()
  assert.equal(state.error, '')
  assert.equal(state.loadedOnce, true)
  assert.equal(state.pagination.total, 0)
  state.rows = [{ snapshotId: 'previous' }]
  await state.load()
  assert.equal(state.rows.length, 0)
})

test('snapshot failures remain errors and clear stale rows', async () => {
  const state = workspace({ list: async () => { throw new Error('无权查看该范围') } })
  state.rows = [{ snapshotId: 'previous' }]
  await state.load()
  assert.equal(state.error, '无权查看该范围')
  assert.equal(state.rows.length, 0)
  assert.equal(state.loading, false)
})

test('snapshot creation opens the returned immutable object and uses server verification', async () => {
  const snapshot = { snapshotId: '9007199254740993123', immutable: true, payload: { count: 2 }, payloadHash: 'server-hash' }
  let openedId, verifiedId
  const state = workspace({
    create: async () => snapshot,
    list: async () => ({ list: [snapshot], total: 1 }),
    detail: async id => { openedId = id; return snapshot },
    verify: async id => { verifiedId = id; return { integrityValid: true, immutable: true } }
  })
  state.createForm.reason = '学期统计留档验收'
  state.confirmCreate()
  await state.submitCreate()
  assert.equal(state.createError, '')
  assert.equal(openedId, snapshot.snapshotId)
  assert.equal(state.detail.payloadHash, 'server-hash')
  assert.equal(state.saving, false)
  await state.verifyDetail()
  assert.equal(verifiedId, snapshot.snapshotId)
  assert.equal(state.verified[snapshot.snapshotId], true)
  assert.equal(state.detailError, '')
})

test('confirmation freezes the shown scope even when the underlying form changes', async () => {
  let sent
  const snapshot = { snapshotId: '901', immutable: true }
  const state = workspace({ create: async body => { sent = body; return snapshot }, list: async () => ({ list: [], total: 0 }), detail: async () => snapshot })
  state.createForm = { snapshotType: 'OVERVIEW', termId: '9007199254740993123', collegeId: 'college-a', majorId: '', reason: '核对学期末的正式统计' }
  state.confirmCreate()
  assert.ok(state.confirmationMessage.includes('9007199254740993123'))
  state.createForm.termId = 'other-term'
  state.createForm.reason = '不同原因'
  await state.submitCreate()
  assert.equal(sent.termId, '9007199254740993123')
  assert.equal(sent.reason, '核对学期末的正式统计')
})

test('an unconfirmed or changed-identity command cannot create a snapshot', async () => {
  let writes = 0
  const state = workspace({ create: async () => { writes++ } })
  state.createForm.reason = '本学期统计留档'
  await state.submitCreate()
  assert.equal(writes, 0)
  state.confirmCreate()
  state._claims.userId = 'another-user'
  await state.submitCreate()
  assert.equal(writes, 0)
  assert.match(state.createError, /身份或权限已变化/)
})

test('a failed detail keeps its exact ID available for retry', async () => {
  const ids = []
  const state = workspace({ detail: async id => { ids.push(id); throw new Error('网络中断') } })
  await state.openDetail({ snapshotId: '9007199254740993123' })
  state.reloadDetail()
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.deepEqual(ids, ['9007199254740993123', '9007199254740993123'])
})

test('late detail responses cannot overwrite a new object or a closed drawer', async () => {
  const pending = []
  const state = workspace({ detail: id => new Promise(resolve => pending.push({ id, resolve })) })
  const first = state.openDetail({ snapshotId: 'a' }), second = state.openDetail({ snapshotId: 'b' })
  pending[1].resolve({ snapshotId: 'b' }); await second
  pending[0].resolve({ snapshotId: 'a' }); await first
  assert.equal(state.detail.snapshotId, 'b')
  const third = state.openDetail({ snapshotId: 'c' })
  state.closeDetail()
  pending[2].resolve({ snapshotId: 'c' }); await third
  assert.equal(state.detail, null)
  assert.equal(state.detailVisible, false)
})

test('a mismatched detail and late verification never certify another snapshot', async () => {
  let finish
  const state = workspace({ detail: async () => ({ snapshotId: 'other' }), verify: () => new Promise(resolve => { finish = resolve }) })
  await state.openDetail({ snapshotId: 'selected' })
  assert.equal(state.verified.selected, false)
  state.detail = { snapshotId: 'a' }
  const pending = state.verifyDetail()
  state.closeDetail()
  state.detail = { snapshotId: 'b' }
  finish({ integrityValid: true, immutable: true }); await pending
  assert.equal(state.verified.b, undefined)
  assert.equal(state.verified.a, undefined)
})

test('a newer list request wins and malformed paging is an error, not an empty school', async () => {
  const pending = []
  const state = workspace({ list: () => new Promise(resolve => pending.push(resolve)) })
  const first = state.load(), second = state.load()
  pending[1]({ list: [{ snapshotId: 'new' }], total: 1 }); await second
  pending[0]({ list: [{ snapshotId: 'old' }], total: 1 }); await first
  assert.equal(state.rows[0].snapshotId, 'new')
  const third = state.load()
  pending[2]({}); await third
  assert.match(state.error, /回执不完整/)
})

test('a negative integrity result is never reported as verified', async () => {
  const state = workspace({ verify: async () => ({ integrityValid: false, immutable: true }) })
  state.detail = { snapshotId: '1' }
  await state.verifyDetail()
  assert.equal(state.verified['1'], false)
  assert.ok(state.detailError)
  assert.equal(state.verifying, false)
})
