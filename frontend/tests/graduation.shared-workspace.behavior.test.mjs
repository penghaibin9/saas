import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { setImmediate as flushTasks } from 'node:timers/promises'
import vm from 'node:vm'

const read = (path) => fs.readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
const source = read('modules/graduation/views/AdminGraduationLayout.vue')
const script = source.match(/<script>([\s\S]*?)<\/script>/)?.[1]
assert.ok(script, 'Graduation layout script must exist')
const workspaceSource = read('modules/graduation/config/graduationWorkspaces.js')
const workspaces = vm.runInNewContext(
  workspaceSource.replace(/^export /gm, '') + '\nGRADUATION_WORKSPACES',
  {}, { timeout: 1000 }
)
const leaves = workspaces.flatMap(workspace => workspace.children).filter(leaf => !leaf.hidden)

// Execute the actual layout options. Only imports/external IO are test doubles;
// the navigation, permission and batch lifecycle methods are not reimplemented.
function loadLayout(selectedBatchId = '71', response = null) {
  const calls = { loads: [], replaces: [], pushes: [], context: 0 }
  const store = {
    selectedBatchId, initialized: true,
    ensureLoaded(options) { calls.loads.push(options); return Promise.resolve() }
  }
  const context = {
    URLSearchParams,
    BasePortalLayout: {}, LoadingState: {}, EmptyState: {}, AppInlineAlert: {},
    GraduationBatchStrip: {}, GraduationExtensionAdminPanel: {},
    graduationPickerAdapters: {},
    useGraduationBatchStore: () => store,
    matchPermission: (patterns, key) => patterns.includes('*') || patterns.includes(key),
    graduationApi: { getContext: async () => { calls.context++; return response } },
    router: {
      replace: async target => { calls.replaces.push(target) },
      push: async target => { calls.pushes.push(target) }
    }
  }
  const options = vm.runInNewContext(
    script.replace(/^import .+\n/gm, '').replace('export default', 'globalThis.layout ='),
    context, { timeout: 1000 }
  )
  return { options, store, calls }
}

function instance(options, overrides = {}) {
  const target = {
    ...options.data(),
    $route: { name: 'graduation-dashboard', path: '/admin/graduation', fullPath: '/admin/graduation', query: {}, meta: {} },
    ...overrides
  }
  for (const [key, method] of Object.entries(options.methods)) target[key] = method.bind(target)
  for (const [key, getter] of Object.entries(options.computed)) {
    Object.defineProperty(target, key, { get: () => getter.call(target), configurable: true })
  }
  return target
}

const plain = value => JSON.parse(JSON.stringify(value))

test('uses the existing workspace opt-in without adding another shell, sidebar or batch selector', () => {
  const opening = source.match(/<BasePortalLayout\b[\s\S]*?>/)?.[0] || ''
  assert.match(opening, /\sworkspace(?:\s|>)/)
  assert.match(opening, /\shide-global-workbench(?:\s|>)/)
  assert.match(opening, /:workspace-navigate="resolveWorkspaceDestination"/)
  assert.match(opening, /:ctx="layoutCtx"/)
  assert.match(opening, /@menu-select="onMenuSelect"/)
  assert.equal((source.match(/<GraduationBatchStrip\b/g) || []).length, 1)
  assert.equal((source.match(/<router-view\b/g) || []).length, 1)
  assert.doesNotMatch(source, /<TeacherWorkspaceFrame\b|<iframe\b|<aside\b/)
  assert.match(source, /<router-view v-else :key="businessViewKey" :ctx="businessCtx"/)
})

test('all 8 workspaces and 24 production leaves preserve their targets and inherit the selected batch', () => {
  assert.equal(workspaces.length, 8)
  assert.equal(leaves.length, 24)
  const { options, calls } = loadLayout()
  for (const item of [...workspaces, ...leaves]) {
    const before = new URL(item.path, 'https://test.invalid')
    const after = new URL(options.methods.resolveWorkspaceDestination(item.path), 'https://test.invalid')
    assert.equal(after.pathname, before.pathname, item.label)
    assert.equal(after.hash, before.hash, item.label)
    assert.deepEqual(after.searchParams.getAll('batchId'), ['71'], item.label)
    after.searchParams.delete('batchId')
    assert.equal(after.searchParams.toString(), before.searchParams.toString(), item.label)
  }
  assert.equal(calls.loads.length, 0, 'pure navigation must not fetch or switch batches')
  assert.equal(calls.pushes.length, 0, 'the existing shared frame owns the actual push')
  assert.equal(calls.replaces.length, 0)
})

test('deep links retain selection, pagination, filters, encoded values and hash', () => {
  const { options } = loadLayout('批次 &/#')
  const path = '/admin/graduation/finals?tab=PENDING_REVIEW&page=2&pageSize=20&selected=900&keyword=A%2BB#file-v3'
  assert.equal(options.methods.resolveWorkspaceDestination(path),
    '/admin/graduation/finals?tab=PENDING_REVIEW&page=2&pageSize=20&selected=900&keyword=A%2BB&batchId=%E6%89%B9%E6%AC%A1%20%26%2F%23#file-v3')
})

test('explicit batch queries, including encoded keys and empty values, remain authoritative', () => {
  const { options } = loadLayout()
  for (const path of [
    '/admin/graduation?batchId=99#review',
    '/admin/graduation/finals?batchId=&tab=PENDING_REVIEW',
    '/admin/graduation/finals?%62atchId=99',
    '/admin/graduation?batchId=99&batchId=98'
  ]) assert.equal(options.methods.resolveWorkspaceDestination(path), path)
})

test('never sends Graduation batch to other centers or similarly named routes', () => {
  const { options } = loadLayout()
  for (const path of [
    '/admin/student-affairs', '/admin/internship?batchId=88', '/admin/academic-affairs',
    '/admin/student/900', '/admin/system', '/workbench', '/admin/graduation-other',
    '//other.invalid/admin/graduation', 'https://other.invalid/admin/graduation', '', null, undefined
  ]) assert.equal(options.methods.resolveWorkspaceDestination(path), path)
})

test('does not guess a missing batch, and reads the current store on each navigation', () => {
  const { options, store, calls } = loadLayout('')
  assert.equal(options.methods.resolveWorkspaceDestination('/admin/graduation'), '/admin/graduation')
  store.selectedBatchId = '80'
  assert.equal(options.methods.resolveWorkspaceDestination('/admin/graduation#today'), '/admin/graduation?batchId=80#today')
  store.selectedBatchId = '81'
  assert.equal(options.methods.resolveWorkspaceDestination('/admin/graduation?'), '/admin/graduation?batchId=81')
  assert.equal(options.methods.resolveWorkspaceDestination('/admin/graduation?panel=risk&'), '/admin/graduation?panel=risk&batchId=81')
  assert.equal(calls.loads.length, 0)
})

test('permission/scope failures still prevent rendering the business view', () => {
  const { options } = loadLayout()
  const target = instance(options)
  assert.equal(target.canRenderBusiness, false)
  target.ctx = { permissionPatterns: [] }
  target.permissionReady = true
  assert.equal(target.canRenderBusiness, false)
  target.scopeReady = true
  assert.equal(target.canRenderBusiness, true)
  target.permissionReady = false
  assert.equal(target.canRenderBusiness, false)
  assert.equal(target.businessCtx.writeEnabled, false)
})

test('read-only student roles and read-only tenants cannot gain writes from the new shell', () => {
  const { options } = loadLayout()
  const target = instance(options, {
    ctx: { permissionPatterns: ['graduationDesign.student.view'], readonlyTenant: false },
    permissionReady: true, scopeReady: true,
    $route: { name: 'graduation-students', path: '/admin/graduation/students', query: {}, meta: {} }
  })
  assert.equal(target.canRenderBusiness, true)
  assert.equal(target.canManageStudents, false)
  assert.equal(target.businessCtx.writeEnabled, false)
  target.ctx.permissionPatterns.push('graduationDesign.student.manage')
  assert.equal(target.businessCtx.writeEnabled, true)
  target.ctx.readonlyTenant = true
  assert.equal(target.businessCtx.writeEnabled, false)
})

test('failed context response keeps permission and scope closed', async () => {
  const { options, calls } = loadLayout('71', { code: 403001, message: '权限服务失败' })
  const target = instance(options)
  await target.loadContext()
  assert.equal(target.permissionReady, false)
  assert.equal(target.scopeReady, false)
  assert.equal(target.canRenderBusiness, false)
  assert.equal(target.contextError, '权限服务失败')
  assert.equal(calls.loads.length, 0)
})

test('existing context loading and batch URL synchronization remain intact', async () => {
  const data = { permissionReady: true, roleNeedsOrgScope: true, scopeConfigured: true, permissionPatterns: [] }
  const { options, calls } = loadLayout('71', { code: 0, data })
  const target = instance(options)
  await target.loadContext()
  assert.equal(calls.context, 1)
  assert.equal(target.ctx, data)
  assert.equal(target.canRenderBusiness, true)
  assert.deepEqual(plain(calls.loads), [{ batchIdFromUrl: '', force: true }])
  assert.deepEqual(plain(calls.replaces), [{ query: { batchId: '71' } }])
})

test('batch watcher repairs only a missing query and stays synchronous', async () => {
  const { options, calls } = loadLayout()
  let repaired = 0
  const target = { $route: { path: '/admin/graduation' }, syncBatchToUrl: () => { repaired++ } }
  const handler = options.watch['$route.query.batchId'].handler
  assert.equal(handler.call(target, '99'), undefined)
  await Promise.resolve()
  assert.equal(repaired, 0)
  assert.equal(handler.call(target, undefined), undefined)
  await flushTasks()
  assert.equal(repaired, 1)
  assert.deepEqual(plain(calls.loads), [
    { batchIdFromUrl: '99', force: false }, { batchIdFromUrl: '', force: false }
  ])
})

test('legacy qualification redirect and original menu callback remain available', async () => {
  const { options, calls } = loadLayout()
  const target = instance(options)
  target.$route.query = { panel: 'grad-qual', batchId: '99', studentId: '7' }
  options.watch['$route.query.panel'].handler.call(target, 'grad-qual')
  target.onMenuSelect({ path: '/admin/graduation/proposals?tab=PENDING_REVIEW' })
  await Promise.resolve()
  assert.deepEqual(plain(calls.replaces), [{ query: { panel: 'roster', batchId: '99', studentId: '7' } }])
  assert.deepEqual(plain(calls.pushes), ['/admin/graduation/proposals?tab=PENDING_REVIEW&batchId=71'])
})

test('batch selector meets the supplied HTML readability floor without touching shared styles', () => {
  const style = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
  const selector = style.match(/\.gd-batch-bar :deep\(\.gbs__select\)\s*\{([^}]+)\}/)?.[1] || ''
  assert.match(selector, /min-height:\s*34px/)
  assert.match(selector, /font-size:\s*13px/)
  assert.doesNotMatch(style, /\.tw-|\.bpl-|:root|\bbody\s*\{/)
  assert.match(source, /gd-student-readonly/)
  assert.match(source, /催交会发送真实站内消息/)
  assert.match(source, /<GraduationExtensionAdminPanel v-if="isExtensionWorkspace" :ctx="businessCtx"/)
})
