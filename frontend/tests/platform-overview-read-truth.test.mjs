import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformControlOverview.vue', import.meta.url), 'utf8')
function instance(getOverview) {
  // Run the actual options/methods without a DOM. Full SFC/build/E2E remain separate gates.
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'globalThis.definition =')
  const context = vm.createContext({ platformControlApi: { getOverview },
    platformStatusLabel: value => value, presentAuditRecord: () => ({}),
    AppCard: {}, AppSectionHeader: {}, EmptyState: {}, ErrorState: {}, LoadingState: {}, ModulePageShell: {}, StatusTag: {} })
  vm.runInContext(script, context)
  const definition = context.definition
  const state = definition.data()
  for (const [key, method] of Object.entries(definition.methods)) state[key] = method.bind(state)
  for (const [key, getter] of Object.entries(definition.computed)) Object.defineProperty(state, key, { get: getter.bind(state) })
  state.unmount = definition.beforeUnmount.bind(state)
  return state
}
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('unknown and malformed metrics never become zero, blank or NaN', () => {
  const state = instance()
  for (const value of [null, undefined, '', ' ', false, {}, [], 'broken', -1, Infinity, NaN]) {
    assert.equal(state.formatCount(value), '未取得')
    assert.equal(state.formatStorage(value), '未取得')
  }
  assert.equal(state.formatCount(0), '0')
  assert.equal(state.formatCount('0'), '0')
  assert.equal(state.formatCount(1.5), '未取得')
  assert.equal(state.formatStorage(0), '0.00 MiB')
  assert.equal(state.formatStorage(1024 ** 3), '1.00 GiB')
})

test('missing lifecycle metrics are explicit in every summary card', () => {
  const state = instance()
  state.ov = {}
  assert.equal(state.statCards[0].value, '未取得')
  assert.ok(state.statCards[0].sub.includes('正式 未取得'))
  assert.equal(state.statCards[1].value, '未取得 / 未取得')
  assert.ok(!JSON.stringify(state.statCards).includes('undefined'))
})

test('missing source evidence is UNKNOWN even when complete is claimed', () => {
  const state = instance()
  state.ov = { dataQuality: { complete: true } }
  assert.equal(state.qualityRows.length, 6)
  assert.ok(state.qualityRows.every(row => row.status === 'UNKNOWN'))
  state.ov.dataQuality.sources = { tenantLifecycle: { status: 'OK' }, fileFoundation: { status: 'DEGRADED' } }
  assert.equal(state.qualityRows.length, 5)
  assert.equal(state.qualityRows.find(row => row.key === 'fileFoundation').status, 'DEGRADED')
})

test('a late success cannot overwrite the latest overview', async () => {
  const first = deferred(), second = deferred()
  let count = 0
  const state = instance(() => (++count === 1 ? first.promise : second.promise))
  const a = state.load(), b = state.load()
  second.resolve({ code: 0, data: { tenantTotal: 7 } })
  await b
  first.resolve({ code: 0, data: { tenantTotal: 99 } })
  await a
  assert.equal(state.ov.tenantTotal, 7)
  assert.equal(state.loading, false)
})

test('an older request cannot clear the loading state of a newer request', async () => {
  const first = deferred(), second = deferred()
  let count = 0
  const state = instance(() => (++count === 1 ? first.promise : second.promise))
  const a = state.load(), b = state.load()
  first.resolve({ code: 0, data: { tenantTotal: 99 } })
  await a
  assert.equal(state.loading, true)
  assert.equal(state.ov, null)
  second.resolve({ code: 0, data: { tenantTotal: 7 } })
  await b
  assert.equal(state.loading, false)
})

test('a failed refresh clears old data and exposes a retryable error', async () => {
  let count = 0
  const state = instance(async () => {
    if (++count === 1) return { code: 0, data: { tenantTotal: 7 } }
    throw new Error('网络连接失败')
  })
  await state.load()
  assert.ok(state.loadedAt)
  await state.load()
  assert.equal(state.ov, null)
  assert.equal(state.loadedAt, '')
  assert.equal(state.error, '网络连接失败')
  assert.equal(state.loading, false)
})

test('a business failure never keeps the prior data', async () => {
  const state = instance(async () => ({ code: 403, message: '无查看权限' }))
  state.ov = { tenantTotal: 7 }
  await state.load()
  assert.equal(state.ov, null)
  assert.equal(state.error, '无查看权限')
  assert.equal(state.loading, false)
})

test('an empty success payload becomes an explicit error', async () => {
  for (const data of [null, undefined, [], 'invalid']) {
    const state = instance(async () => ({ code: 0, data, message: 'ok' }))
    await state.load()
    assert.equal(state.ov, null)
    assert.ok(state.error.includes('未取得'))
    assert.equal(state.loading, false)
  }
})

test('unmount invalidates an in-flight result', async () => {
  const pending = deferred()
  const state = instance(() => pending.promise)
  const request = state.load()
  state.unmount()
  pending.resolve({ code: 0, data: { tenantTotal: 7 } })
  await request
  assert.equal(state.ov, null)
  assert.equal(state.loadedAt, '')
})

test('the workspace distinguishes an unavailable list from an empty list', () => {
  for (const name of ['expiringTenants', 'abnormalTenants', 'recentAudits']) {
    assert.ok(source.includes(`!Array.isArray(ov.${name})`))
    assert.ok(source.includes(`v-else-if="!ov.${name}.length"`))
  }
  assert.match(source, /<button type="button"[^>]*:disabled="loading"[^>]*@click="load"/)
  assert.match(source, /aria-live="polite"/)
})
