/** Real workbench layout adapter -> real admin menu; only HTTP and unused browser IO are stubbed.
 * Run: node --test tests/module-commerce-layout-context.test.mjs
 * This is not browser/MySQL acceptance; the 16-combination E2E remains mandatory.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { fileURLToPath } from 'node:url'

const sourceRoot = fileURLToPath(new URL('../src/', import.meta.url))
const dataUrl = (source) => `data:text/javascript,${encodeURIComponent(source)}`
const httpUrl = dataUrl(`
  export const request = (...args) => globalThis.__MODULE_CONTEXT_IO__.read(...args)
  export const getToken = () => 'context-test-token'
  export const currentUserFromToken = () => ({ userType: 'ADMIN', currentRoleCode: 'SCHOOL_ADMIN' })
  export const shouldTryReal = () => true
  export const requestBlob = () => { throw new Error('unexpected blob IO') }
  export const requestUpload = () => { throw new Error('unexpected upload IO') }
`)
register(dataUrl(`
  import path from 'node:path'
  import { pathToFileURL } from 'node:url'
  import { existsSync } from 'node:fs'
  let options
  export function initialize(data) { options = data }
  export async function resolve(specifier, context, nextResolve) {
    if (specifier === '@/services/http' || specifier === '@/services/http/client')
      return { shortCircuit: true, url: options.httpUrl }
    if (specifier === '@/utils/xlsxDownload')
      return { shortCircuit: true, url: 'data:text/javascript,export function downloadXlsxFromApi(){throw new Error("unexpected download")}' }
    if (specifier === '@/modules/graduation/api/graduation-batch-context')
      return { shortCircuit: true, url: 'data:text/javascript,export function withGraduationBatch(){throw new Error("unexpected business operation")}' }
    if (specifier.startsWith('@/')) {
      let target = path.join(options.sourceRoot, specifier.slice(2))
      if (!existsSync(target)) target += '.js'
      return { shortCircuit: true, url: pathToFileURL(target).href }
    }
    try { return await nextResolve(specifier, context) }
    catch (error) {
      if (error.code === 'ERR_MODULE_NOT_FOUND' && specifier.startsWith('.') && !path.extname(specifier))
        return nextResolve(specifier + '.js', context)
      throw error
    }
  }
`), { parentURL: import.meta.url, data: { sourceRoot, httpUrl } })

const { fetchLayoutContext } = await import('../src/modules/workbench/api/workbench.api.js')
const { getVisibleAdminMenu, clearVisibleAdminMenuCache } = await import('../src/config/adminMenu.js')
const { resetAdminQueryCoordinatorForTest } = await import('../src/services/performance/queryCoordinator.js')
const { clearPermissionPatterns } = await import('../src/security/permissionGate.js')
const adapters = {
  workbench: fetchLayoutContext,
}
const core = [
  ['internship', 'internship'], ['graduationDesign', 'graduation'],
  ['studentAffairs', 'student-affairs'], ['academicAffairs', 'academic-affairs'],
]
const technical = ['workbench', 'todoMessage', 'systemAdmin', 'auditLog', 'messages']

function input(entitlements, additions = {}) {
  return { currentRole: { roleCode: 'SCHOOL_ADMIN', roleType: 'SCHOOL_ADMIN', roleName: '学校管理员' },
    dataScope: { scopeName: '本校' }, permissionPatterns: ['*'],
    moduleEntitlements: entitlements, moduleStates: { internship: { entitled: entitlements.includes('internship') } },
    moduleAccessHealthy: true, moduleAccessError: '', readonlyTenant: false, ...additions }
}
function configure(payload, { rbacFails = false, brandFails = false } = {}) {
  resetAdminQueryCoordinatorForTest()
  clearPermissionPatterns()
  const calls = []
  globalThis.__MODULE_CONTEXT_IO__ = { read: async (path) => {
    calls.push(path)
    if (path === '/rbac/current-context') {
      if (rbacFails) throw new Error('context unavailable')
      return payload
    }
    if (path === '/auth/me') return { tenantId: '42', tenantName: '测试学校', realName: '管理员' }
    if (path === '/tenant/brand') {
      if (brandFails) throw new Error('brand unavailable')
      return { schoolName: '测试学校' }
    }
    if (path === '/admin/workbench-snapshot') return { summary: {}, todos: { items: [] }, messages: { unread: 0 } }
    if (path === '/admin/messages/count') return { unread: 0, pendingAck: 0 }
    if (path === '/graduation/context') return { permissionActions: {}, fullScope: true }
    throw new Error('unexpected request: ' + path)
  } }
  return calls
}
function menuKeys(ctx) {
  return getVisibleAdminMenu(ctx).map((row) => row.key).filter((key) => core.some(([, group]) => group === key)).sort()
}

for (const [name, load] of Object.entries(adapters)) {
  for (let mask = 0; mask < 16; mask++) {
    test(`${name}: purchased mask ${mask} survives real layout adapter and menu cache`, async () => {
      const selected = core.filter((_, i) => mask & (1 << i))
      const raw = input([...technical, ...selected.map(([key]) => key)])
      const calls = configure(raw)
      // Seed the actual menu cache with the previous all-module identity.
      getVisibleAdminMenu(input([...technical, ...core.map(([key]) => key)]))
      const ctx = await load()
      assert.deepEqual(ctx.moduleEntitlements, raw.moduleEntitlements)
      assert.deepEqual(ctx.moduleStates, raw.moduleStates)
      assert.equal(ctx.moduleAccessHealthy, true)
      assert.deepEqual(menuKeys(ctx), selected.map(([, group]) => group).sort())
      assert.equal(calls.filter((path) => path === '/rbac/current-context').length, 1)
    })
  }
  test(`${name}: authoritative empty array never turns into unknown/all modules`, async () => {
    configure(input([]))
    const ctx = await load()
    assert.deepEqual(ctx.moduleEntitlements, [])
    assert.deepEqual(menuKeys(ctx), [])
  })
  test(`${name}: authority outage stays a service error, not an unpurchased snapshot`, async () => {
    const raw = input([], { moduleAccessHealthy: false, moduleAccessError: '授权计算暂不可用' })
    configure(raw)
    const ctx = await load()
    assert.equal(ctx.moduleAccessHealthy, false)
    assert.equal(ctx.moduleAccessError, raw.moduleAccessError)
  })
  test(`${name}: detached arrays cannot mutate the authority response`, async () => {
    const raw = input([...technical, 'internship'])
    configure(raw)
    const ctx = await load()
    assert.notEqual(ctx.moduleEntitlements, raw.moduleEntitlements)
    ctx.moduleEntitlements.push('employment')
    assert.equal(raw.moduleEntitlements.includes('employment'), false)
  })
  test(`${name}: failed fresh context cannot inherit an earlier tenant grant`, async () => {
    configure(input([...technical, 'internship']))
    await load()
    configure(input([]), { rbacFails: true })
    const ctx = await load()
    assert.equal(ctx.moduleEntitlements, null)
    assert.equal(ctx.moduleAccessHealthy, false)
    assert.ok(ctx.moduleAccessError)
  })
}

test('workbench: optional brand outage does not erase authoritative entitlements', async () => {
  configure(input([...technical, 'graduationDesign']), { brandFails: true })
  const ctx = await fetchLayoutContext()
  assert.deepEqual(menuKeys(ctx), ['graduation'])
  assert.equal(ctx.moduleAccessHealthy, true)
})

test('workbench: layout badge uses one lightweight read for concurrent consumers', async () => {
  const calls = configure(input([...technical, 'graduationDesign']))
  const read = globalThis.__MODULE_CONTEXT_IO__.read
  globalThis.__MODULE_CONTEXT_IO__.read = async (path, ...args) => {
    if (path === '/admin/messages/count') {
      calls.push(path)
      return { unread: 7, pendingAck: 2 }
    }
    return read(path, ...args)
  }
  const contexts = await Promise.all([fetchLayoutContext(), fetchLayoutContext(), fetchLayoutContext()])
  for (const ctx of contexts) {
    assert.equal(ctx.messageUnreadCount, 7)
    assert.deepEqual(menuKeys(ctx), ['graduation'])
  }
  assert.equal(calls.filter((path) => path === '/admin/messages/count').length, 1)
  assert.equal(calls.includes('/admin/workbench-snapshot'), false)
})

test('workbench: optional message count failure preserves authorized navigation', async () => {
  configure(input([...technical, 'graduationDesign']))
  const read = globalThis.__MODULE_CONTEXT_IO__.read
  globalThis.__MODULE_CONTEXT_IO__.read = async (path, ...args) => {
    if (path === '/admin/messages/count') throw new Error('message unavailable')
    return read(path, ...args)
  }
  const ctx = await fetchLayoutContext()
  assert.equal(ctx.messageUnreadCount, 0)
  assert.equal(ctx.moduleAccessHealthy, true)
  assert.deepEqual(menuKeys(ctx), ['graduation'])
})

test.after(() => {
  clearVisibleAdminMenuCache()
  resetAdminQueryCoordinatorForTest()
  clearPermissionPatterns()
  delete globalThis.__MODULE_CONTEXT_IO__
})
