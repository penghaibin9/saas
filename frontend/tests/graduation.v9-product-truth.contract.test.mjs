import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const layout = fs.readFileSync(new URL('../src/modules/graduation/views/AdminGraduationLayout.vue', import.meta.url), 'utf8')
const batchStrip = fs.readFileSync(new URL('../src/modules/graduation/views/_shared/GraduationBatchStrip.vue', import.meta.url), 'utf8')

// Exercise the real Options API functions without starting Vue or making API
// requests. Dependencies are injected; lifecycle hooks never run automatically.
function optionsFrom(source, bindings = {}) {
  const script = source.match(/<script\b[^>]*>([\s\S]*?)<\/script>/)?.[1]
  assert.ok(script, 'the component must retain its Options API script')
  const body = script.replace(/^\s*import[^\n]*$/gm, '')
    .replace(/export\s+default\s+/, 'globalThis.componentOptions = ')
  const sandbox = {
    BasePortalLayout: {}, LoadingState: {}, EmptyState: {}, AppInlineAlert: {},
    GraduationBatchStrip: {}, GraduationExtensionAdminPanel: {}, StatusTag: {},
    graduationPickerAdapters: {},
    matchPermission() { throw new Error('permission algorithm must not be replaced by this harness') },
    useGraduationBatchStore() { throw new Error('unexpected store initialization') },
    graduationApi: {}, router: {},
    ...bindings
  }
  vm.runInNewContext(body, sandbox, { timeout: 1000 })
  assert.ok(sandbox.componentOptions?.computed)
  assert.ok(sandbox.componentOptions?.methods)
  return sandbox.componentOptions
}

test('G10 graduation module shell removes repeated intro without hiding valid business tabs', () => {
  assert.doesNotMatch(layout, /gd-page-intro/)
  assert.doesNotMatch(layout, /mp-tabs \.mp-tab:nth-child\(8\)/)
  assert.match(layout, /class="gd-batch-context"/)
  assert.match(layout, /<GraduationBatchStrip class="gd-batch-bar" \/>/)
  assert.match(layout, /class="gd-business-view"/)
})

test('G10 keeps fail-closed permission and data-scope projection', () => {
  // Assert independent guards, not their source declaration order.
  assert.match(layout, /canRenderBusiness\(\)/)
  assert.match(layout, /v-if="canRenderBusiness"/)
  assert.match(layout, /permissionReady/)
  assert.match(layout, /scopeReady/)
  assert.match(layout, /writeEnabled: this\.permissionReady && !this\.ctx\.readonlyTenant && studentListWrite/)
  assert.match(layout, /GraduationExtensionAdminPanel/)
  assert.match(layout, /<router-view v-else :key="businessViewKey" :ctx="businessCtx" \/>/)
})

test('G10 visually compresses but does not replace batch store, URL or validation semantics', () => {
  assert.match(layout, /useGraduationBatchStore/)
  assert.match(layout, /store\.ensureLoaded\(\{ batchIdFromUrl: id \|\| '', force: !store\.initialized \}\)/)
  assert.match(layout, /syncBatchToUrl\(\)/)
  assert.match(layout, /batchId=/)
  assert.match(batchStrip, /useGraduationBatchStore/)
  assert.match(batchStrip, /this\.store\.selectBatch\(id\)/)
  assert.match(batchStrip, /q\.batchId = id/)
  assert.match(batchStrip, /this\.\$router\.replace\(\{ query: q \}\)/)
  assert.match(batchStrip, /store\.needsExplicitSelect/)
})

test('G10 remains inside the graduation module and keeps BasePortalLayout unchanged', () => {
  assert.match(layout, /import BasePortalLayout from '@\/layouts\/BasePortalLayout\.vue'/)
  assert.match(layout, /import \{ graduationPickerAdapters \}/)
  assert.match(layout, /provide\(\) \{ return \{ appPickerAdapters: graduationPickerAdapters \} \}/)
  assert.match(layout, /@menu-select="onMenuSelect"/)
})

test('G10 behavior: business rendering requires context, ready permissions and ready data scope', () => {
  const options = optionsFrom(layout)
  for (const ctx of [null, {}]) {
    for (const permissionReady of [false, true]) {
      for (const scopeReady of [false, true]) {
        const actual = options.computed.canRenderBusiness.call({ ctx, permissionReady, scopeReady })
        assert.equal(actual, Boolean(ctx && permissionReady && scopeReady))
      }
    }
  }
})

test('G10 behavior: readonly tenants and read-only student viewers never acquire write access', () => {
  const options = optionsFrom(layout)
  assert.equal(options.computed.businessCtx.call({ ctx: null }), null)
  for (const permissionReady of [false, true]) {
    for (const readonlyTenant of [false, true]) {
      for (const canManageStudents of [false, true]) {
        for (const isStudentList of [false, true]) {
          const ctx = { readonlyTenant, permissionActions: {}, permissionPatterns: ['existing-pattern'] }
          const actual = options.computed.businessCtx.call({ ctx, permissionReady, scopeReady: true, isStudentList, canManageStudents, contextError: '' })
          assert.equal(actual.writeEnabled, permissionReady && !readonlyTenant && (!isStudentList || canManageStudents))
          assert.equal(actual.permissionActions, ctx.permissionActions)
          assert.equal(actual.permissionPatterns, ctx.permissionPatterns)
          assert.equal(Object.hasOwn(ctx, 'writeEnabled'), false, 'projection must not mutate the canonical context')
        }
      }
    }
  }
})

test('G10 behavior: failed context requests close both permission and scope gates', async () => {
  const options = optionsFrom(layout, { graduationApi: { async getContext() { return { code: 403001, message: 'permission denied' } } } })
  const context = { loading: false, ctx: { permissionPatterns: ['*'] }, permissionReady: true, scopeReady: true, contextError: '' }
  await options.methods.loadContext.call(context)
  assert.equal(context.permissionReady, false)
  assert.equal(context.scopeReady, false)
  assert.equal(context.loading, false)
  assert.equal(context.contextError, 'permission denied')
  assert.equal(options.computed.canRenderBusiness.call(context), false)
})

test('G10 behavior: server organization-scope requirements control the scope gate', async () => {
  for (const [roleNeedsOrgScope, scopeConfigured, expected] of [[true, false, false], [true, true, true], [false, false, true]]) {
    const calls = []
    const store = { async ensureLoaded(query) { calls.push(query) } }
    const options = optionsFrom(layout, {
      useGraduationBatchStore: () => store,
      graduationApi: { async getContext() { return { code: 0, data: { permissionReady: true, roleNeedsOrgScope, scopeConfigured } } } }
    })
    const context = { $route: { query: { batchId: 'batch-a' } }, syncBatchToUrl() {} }
    await options.methods.loadContext.call(context)
    assert.equal(context.scopeReady, expected)
    assert.equal(context.permissionReady, true)
    assert.equal(calls.length, 1)
    assert.equal(calls[0].batchIdFromUrl, 'batch-a')
  }
})

test('G10 behavior: batch watcher delegates explicit selection to the canonical store', () => {
  const calls = []
  const store = { initialized: false, ensureLoaded(query) { calls.push(query) } }
  const options = optionsFrom(layout, { useGraduationBatchStore: () => store })
  const watcher = options.watch['$route.query.batchId']
  assert.equal(watcher.immediate, true)
  watcher.handler.call({}, 'batch-b')
  assert.equal(calls[0].batchIdFromUrl, 'batch-b')
  assert.equal(calls[0].force, true)
  store.initialized = true
  watcher.handler.call({}, undefined)
  assert.equal(calls[1].batchIdFromUrl, '')
  assert.equal(calls[1].force, false)
})

test('G10 behavior: batch selector preserves work context and never mutates router query in place', () => {
  const options = optionsFrom(batchStrip)
  const selections = []
  const navigations = []
  const query = { batchId: 'old', panel: 'archive', asel: 'record-17', returnTo: '/admin/graduation' }
  const context = {
    store: { selectBatch(id) { selections.push(id) } },
    $route: { query },
    $router: { replace(target) { navigations.push(target); return Promise.resolve() } }
  }
  options.methods.onSelect.call(context, 'new')
  assert.equal(selections[0], 'new')
  assert.equal(navigations[0].query.batchId, 'new')
  for (const key of ['panel', 'asel', 'returnTo']) assert.equal(navigations[0].query[key], query[key])
  assert.equal(query.batchId, 'old')
  options.methods.onSelect.call(context, '')
  assert.equal(Object.hasOwn(navigations[1].query, 'batchId'), false)
  assert.equal(navigations[1].query.returnTo, query.returnTo)
})

test('G10 behavior: menu navigation retains the selected batch without overwriting an explicit batch', () => {
  const destinations = []
  const store = { selectedBatchId: 'batch 1' }
  const options = optionsFrom(layout, {
    useGraduationBatchStore: () => store,
    router: { push(target) { destinations.push(target); return Promise.resolve() } }
  })
  const context = { $route: { fullPath: '/admin/graduation' } }
  options.methods.onMenuSelect.call(context, { path: '/admin/graduation/finals' })
  options.methods.onMenuSelect.call(context, { path: '/admin/graduation/proposals?tab=PENDING_REVIEW' })
  options.methods.onMenuSelect.call(context, { path: '/admin/graduation/finals?batchId=other' })
  assert.equal(destinations[0], '/admin/graduation/finals?batchId=batch%201')
  assert.equal(destinations[1], '/admin/graduation/proposals?tab=PENDING_REVIEW&batchId=batch%201')
  assert.equal(destinations[2], '/admin/graduation/finals?batchId=other')
})

test('G10 behavior: route and default panel determine the existing business lifecycle key', () => {
  const options = optionsFrom(layout)
  const context = { $route: { name: 'graduation-defense-scoring', path: '/admin/graduation/defense-scoring', meta: { defaultPanel: 'defense' }, query: { studentId: '1' } } }
  const initial = options.computed.businessViewKey.call(context)
  context.$route.query.studentId = '2'
  assert.equal(options.computed.businessViewKey.call(context), initial, 'selection changes must not replace the module lifecycle policy')
  context.$route.name = 'graduation-defense-confirmation'
  assert.notEqual(options.computed.businessViewKey.call(context), initial)
})
