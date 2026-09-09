import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'

function workspace(api) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaStatsSnapshotWorkspace.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { academicStatsSnapshotApi: api, matchPermission, getPermissionPatterns: () => ['*'], toast: { success() {} } } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { contextFilters: {} }
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

test('a negative integrity result is never reported as verified', async () => {
  const state = workspace({ verify: async () => ({ integrityValid: false, immutable: true }) })
  state.detail = { snapshotId: '1' }
  await state.verifyDetail()
  assert.equal(state.verified['1'], false)
  assert.ok(state.detailError)
  assert.equal(state.verifying, false)
})
