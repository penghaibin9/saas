import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as orders from '../src/modules/platform/utils/orderWorkspace.mjs'
import { optionsInstance, tenant } from './platform-workspace-test-support.mjs'

const views = ['PlatformControlOverview', 'PlatformControlTenants', 'PlatformControlOrders', 'PlatformControlTenantDetail']
for (const view of views) {
  test(`${view} uses the real empty-state props and explicit actions`, () => {
    const source = fs.readFileSync(new URL(`../src/modules/platform/views/control/${view}.vue`, import.meta.url), 'utf8')
    const states = [...source.matchAll(/<EmptyState\b([\s\S]*?)<\/EmptyState>/g)]
    assert.ok(states.length)
    for (const [, body] of source.matchAll(/<style\s+src="[^"]+">([\s\S]*?)<\/style>/g)) assert.equal(body.trim(), '')
    assert.doesNotMatch(source, /<EmptyState\b[^>]*(?:\s|:)text=/)
    for (const [, block] of states) {
      assert.match(block, /(?:^|\s|:)title=/)
      assert.match(block, /<template #actions>/)
    }
    for (const [, props] of source.matchAll(/<ErrorState\b([^>]+)\/>/g)) assert.match(props, /@back=/)
  })
}

test('clearing an order work-item filter also clears the local focus and reloads unchanged URL', async () => {
  const { state, calls } = optionsInstance('../src/modules/platform/views/control/PlatformControlOrders.vue', {}, orders)
  let reads = 0
  state.load = async () => { reads++ }
  state.focus = 'repair'; state.keywordInput = 'old'; state.statusInput = 'paid'; state.page = 3
  await state.clearScope()
  assert.equal(state.focus, 'all'); assert.equal(state.keywordInput, ''); assert.equal(state.statusInput, ''); assert.equal(state.page, 1)
  assert.equal(reads, 1); assert.equal(calls.length, 0)
})

test('clearing an order query preserves existing router-based fetch ownership', async () => {
  const { state, calls } = optionsInstance('../src/modules/platform/views/control/PlatformControlOrders.vue', { $route: { path: '/admin/platform/orders', query: { tenantId: tenant().tenantId } } }, orders)
  state.load = () => assert.fail('Router watcher owns the changed-query read')
  await state.clearScope()
  assert.equal(calls[0][1].path, '/admin/platform/orders')
  assert.deepEqual(Object.keys(calls[0][1].query), [])
})

test('lifecycle protects drafts, unresolved responses and cache recovery but releases a confirmed receipt', () => {
  const { state } = optionsInstance('../src/modules/platform/components/TenantLifecycleWorkspace.vue', { tenant: tenant(), tenant360: { version: 4 } })
  assert.equal(state.protectNavigation, false)
  state.choose('disable'); assert.equal(state.protectNavigation, true)
  state.phase = 'uncertain'; state.attempted = true; assert.equal(state.protectNavigation, true)
  state.receipt = { cacheRecoveryRequired: true }; assert.equal(state.protectNavigation, true)
  state.receipt = { cacheRecoveryRequired: false }; assert.equal(state.protectNavigation, false)
  state.busy = true; assert.equal(state.protectNavigation, true)
})

test('lifecycle beforeunload warns for unfinished work', () => {
  const { state } = optionsInstance('../src/modules/platform/components/TenantLifecycleWorkspace.vue', { tenant: tenant(), tenant360: {} })
  let prevented = 0; const event = { preventDefault() { prevented++ } }
  state.beforeUnload(event); assert.equal(prevented, 0)
  state.action = 'disable'; state.beforeUnload(event); assert.equal(prevented, 1); assert.equal(event.returnValue, '')
})

test('detail uses the active lifecycle ref as well as the existing rule guard', async () => {
  const { state, definition, calls } = optionsInstance('../src/modules/platform/views/control/PlatformControlTenantDetail.vue', { tab: 'info', $refs: { lifecycleWorkspace: { protectNavigation: true, busy: true } } })
  state.switchTab('brand'); assert.equal(state.tab, 'info'); assert.equal(calls.length, 0)
  assert.equal(definition.beforeRouteLeave.call(state, { fullPath: '/admin/platform/orders' }), false)
  await state.leaveRules(); assert.equal(calls.length, 0)
  state.$refs.lifecycleWorkspace.busy = false; await state.leaveRules(); assert.equal(calls[0][0], 'push')
})

test('overview does not bury a HIGH operational incident behind the school preview limit', () => {
  const { state } = optionsInstance('../src/modules/platform/views/control/PlatformControlOverview.vue', {}, { platformStatusLabel: value => value, presentAuditRecord: () => ({}) })
  state.ov = { abnormalTenants: [{ ...tenant(), status: 'expired' }], expiringTenants: [], operationalRisks: [{ level: 'HIGH', sourceCard: 'INCIDENT', text: 'High-priority incident' }] }
  assert.equal(state.priorityItems[0].key, 'risk-0'); assert.equal(state.priorityItems[1].title, tenant().tenantName)
})
