import { academicRoleAllows, academicRoleDefaultPath, hasAcademicRoleMenu } from '../src/modules/academicAffairs/config/academicRoleNavigation.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

function overview(transport) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/components/AaOverviewWorkspace.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
  const context = Object.fromEntries(['AaOverviewPageFrame', 'AcademicFlowOverview', 'DataTable', 'LoadingState', 'ErrorState', 'EmptyState', 'AppButton', 'AppTermEntityPicker'].map(key => [key, {}]))
  Object.assign(context, { academicAffairsApi: { getDashboardRoleQueue: transport }, safeBusinessMessage: (value, fallback) => value || fallback, sourceTimeLabel: value => value, adaptTypedTodoPage: value => value })
  vm.runInNewContext(script, context)
  return context.component
}
test('A5: unknown, invalid and missing counts never become zero; readiness remains unknown', () => {
  const component = overview()
  for (const value of [undefined, null, -1, NaN, '0']) assert.equal(component.methods.countLabel(value), '—')
  assert.equal(component.methods.countLabel(0), 0)
  assert.equal(component.computed.readinessStatus.call({ readiness: {} }), '状态待核对')
  assert.equal(component.computed.readinessStatus.call({ readiness: { status: 'UNKNOWN' } }), '状态待核对')
})
test('A5: failed or malformed queue is an error, not empty success', async () => {
  for (const transport of [async () => { throw new Error('离线') }, async () => ({ code: 0, data: { items: [] } })]) {
    const component = overview(transport)
    const state = { ...component.methods, requestId: 0, identity: () => 'a', current: () => true, tab: 'pending', page: 1, pageSize: 5, $route: {query: {}}, queue: { items: [{title: '旧身份'}] } }
    await state.loadQueue()
    assert.ok(state.error)
    assert.deepEqual(Object.keys(state.queue), [])
    assert.equal(state.loading, false)
  }
})
test('A6: earlier identity queue response cannot replace the current identity', async () => {
  let resolve
  const component = overview(() => new Promise(done => { resolve = done }))
  let identity = 'a'
  const state = { ...component.methods, disposed: false, requestId: 0, identity: () => identity, tab: 'pending', page: 1, pageSize: 5, $route: {query: {}}, queue: {} }
  const pending = state.loadQueue()
  identity = 'b'; state.queue = { items: [{title: '当前身份'}] }
  resolve({ code: 0, data: { total: 1, items: [{title: '旧身份'}] } })
  await pending
  assert.equal(state.queue.items[0].title, '当前身份')
})

// Controlled compiled Vue consumer tests: declared API collaborators, no HTTP or authorization proof.
// ErrorState, AppGlobalState, AppButton and normalizeUiError are the actual production implementations.
import { createRequire } from 'node:module'
import process from 'node:process'
import { setImmediate } from 'node:timers'
import { normalizeUiError, safeBusinessMessage } from '../src/utils/presentationSafety.js'
import { academicIdentity, createAcademicReturnStore } from '../src/modules/academicAffairs/academicFlowContext.js'
import { adaptTypedTodoPage } from '../src/modules/workbench/config/todoTypedRouteBridge.js'

const require = createRequire(import.meta.url)
const Vue = require('vue')
const { parse, compileTemplate } = require('@vue/compiler-sfc')
const { h, reactive, createRenderer, nextTick } = Vue
const overviewRelative = 'modules/academicAffairs/components/AaOverviewWorkspace.vue'
function readOverviewSource(relative) {
  if (relative === overviewRelative && process.env.AA_OVERVIEW_BEFORE_VIEW) return readFileSync(process.env.AA_OVERVIEW_BEFORE_VIEW, 'utf8')
  return readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')
}
function compileOverviewSfc(relative, scope = {}) {
  const { descriptor, errors } = parse(readOverviewSource(relative), { filename: relative }); assert.deepEqual(errors, [])
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const component = new Function(...Object.keys(scope), `${script}\nreturn component`)(...Object.values(scope))
  const template = compileTemplate({ source: descriptor.template.content, filename: relative, id: relative, compilerOptions: { mode: 'function' } }); assert.deepEqual(template.errors, [])
  component.render = new Function('Vue', template.code)(Vue)
  return component
}
const ActualAppGlobalState = compileOverviewSfc('components/common/AppGlobalState.vue', { normalizeUiError })
const ActualErrorState = compileOverviewSfc('components/business/ErrorState.vue', { AppGlobalState: ActualAppGlobalState, normalizeUiError })
const ActualLoadingState = compileOverviewSfc('components/business/LoadingState.vue', { AppGlobalState: ActualAppGlobalState })
const ActualEmptyState = compileOverviewSfc('components/business/EmptyState.vue', { AppGlobalState: ActualAppGlobalState })
const ActualOverviewButton = compileOverviewSfc('components/ui/AppButton.vue')
const overviewNode = (type, value = '') => ({ type, tagName: type.toUpperCase(), value, props: {}, children: [], parent: null, listeners: {}, addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler) }, removeEventListener(name, handler) { this.listeners[name] = (this.listeners[name] || []).filter(fn => fn !== handler) } })
const overviewRenderer = createRenderer({
  createElement: tag => overviewNode(tag), createText: value => overviewNode('#text', value), createComment: value => overviewNode('#comment', value),
  setText(n, value) { n.value = value }, setElementText(n, value) { n.value = value; n.children = [] },
  parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
  patchProp(n, key, _old, value) { n.props[key] = value },
  insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(n); else parent.children.splice(i, 0, n) },
  remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } }
})
const overviewWalk = n => [n, ...n.children.flatMap(overviewWalk)]
const overviewText = n => n.type === '#comment' ? '' : n.value + n.children.map(overviewText).join('')
const overviewButtons = (root, label) => overviewWalk(root).filter(n => n.type === 'button' && overviewText(n).trim() === label)
function clickOverviewButton(root, label) {
  const buttons = overviewButtons(root, label); assert.equal(buttons.length, 1, `One public ${label} button`)
  const button = buttons[0]; if (button.props.disabled) return false
  for (const fn of Array.isArray(button.props.onClick) ? button.props.onClick : [button.props.onClick]) fn?.({ target: button, type: 'click' })
  return true
}
async function overviewRenderTerminal() { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const healthyQueue = title => ({ code: 0, data: { items: title ? [{ todoId: 'DECLARED_TODO', title, status: 'PENDING' }] : [], total: title ? 1 : 0, summary: { pending: title ? 1 : 0, done: 0, nearDeadline: 0 } }, message: 'ok' })
const healthyReadiness = () => ({ term: { termId: '1' }, items: [], status: 'BLOCKED', conclusion: '声明运行检查阻断', blockerCount: 1, riskCount: 0 })
const overviewDeferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
async function compiledOverviewFixture(t, options = {}) {
  const calls = [], errors = [], warnings = []
  const state = reactive({ claims: { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_USER_A', currentRoleCode: 'COLLEGE_ADMIN', activeContextId: 'DECLARED_CONTEXT' }, ctx: { ctxKey: 'DECLARED_CTX_A', permissionPatterns: ['academicAffairs.dashboard.view'], dataScope: 'COLLEGE', permissionVersion: 1, dataScopeVersion: 1 } })
  const api = { getDashboardRoleQueue(params) { calls.push(['queue', { ...params }]); return options.queue ? options.queue(params) : Promise.resolve(healthyQueue()) } }
  const readiness = { get(term) { calls.push(['readiness', term]); return options.readiness ? options.readiness(term) : Promise.resolve(healthyReadiness()) }, exportXlsx() { throw new Error('禁止该错误状态夹具导出') } }
  const visual = (name, render) => ({ name, inheritAttrs: false, setup(_props, { slots }) { return render || (() => h('section', {}, slots.default?.())) } })
  const Frame = { name: 'DeclaredOverviewFrame', inheritAttrs: false, setup(_props, { slots }) { return () => h('main', {}, [slots.actions?.(), slots.default?.()]) } }
  // Unrelated flow/picker/table visuals are declared; neither error-state normalization nor buttons are replaced.
  const Table = { name: 'DeclaredTodoTable', props: ['rows'], render() { return h('table', {}, (this.rows || []).map(row => h('tr', {}, row.title))) } }
  const component = compileOverviewSfc(overviewRelative, {
    AaOverviewPageFrame: Frame, AcademicFlowOverview: visual('DeclaredFlowOverview'), DataTable: Table,
    LoadingState: ActualLoadingState, ErrorState: ActualErrorState, EmptyState: ActualEmptyState, AppButton: ActualOverviewButton, AppTermEntityPicker: visual('DeclaredTermPicker'),
    academicAffairsApi: api, readinessApi: readiness, academicIdentity, createAcademicReturnStore, adaptTypedTodoPage, safeBusinessMessage,
    currentUserFromToken: () => state.claims, sourceTimeLabel: value => value,
    request() { throw new Error('禁止该夹具发起HTTP') }, canEnterRoute: () => true, matchPermission: () => true, routeTarget: () => null, routeAllowed: () => false
  })
  const root = overviewNode('root')
  const app = overviewRenderer.createApp({ render: () => h(component, { ctx: state.ctx, mode: options.mode || 'todos', ref: 'overview' }) })
  const path = options.mode === 'overview' ? '/admin/academic-affairs' : '/admin/academic-affairs/todos'
  app.config.globalProperties.$route = reactive({ path, fullPath: path, query: {} })
  app.config.globalProperties.$router = { options: { history: { state: {} } }, resolve: location => ({ ...location, matched: [] }), push() { throw new Error('禁止该错误状态夹具导航') } }
  app.config.warnHandler = value => warnings.push(value); app.config.errorHandler = value => errors.push(value)
  const wrapper = app.mount(root); await overviewRenderTerminal(); assert.notEqual(wrapper.$refs.overview.identity(), '', 'Actual academicIdentity has all required declared claims')
  let stopped = false
  const stop = () => { if (!stopped) { app.unmount(); stopped = true } }
  t.after(async () => { stop(); await overviewRenderTerminal(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) })
  return { root, vm: wrapper.$refs.overview, state, calls, errors, warnings, stop }
}
function assertOverviewPublicState(f, kind, title) {
  const panels = overviewWalk(f.root).filter(n => String(n.props.class || '').split(/\s+/).includes(`ags-${kind}`))
  assert.equal(panels.length, 1, `Actual shared public ${kind} panel`)
  assert.match(overviewText(panels[0]), new RegExp(title))
  return panels[0]
}

test('A5 compiled queue typed403 generic message renders forbidden without a retry action', async t => {
  const f = await compiledOverviewFixture(t, { queue: async () => ({ code: 403001, data: null, message: '请求未完成', httpStatus: 403, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_SUPPORT_403' }) })
  assertOverviewPublicState(f, 'forbidden', '暂无访问权限')
  assert.equal(overviewButtons(f.root, '重试').length, 0)
  assert.equal(overviewButtons(f.root, '返回').length, 1)
  assert.equal(f.calls.length, 1); assert.equal(f.vm.loading, false); assert.deepEqual(Object.keys(f.vm.queue), [])
})

test('A5 compiled queue typed401 renders re-login rather than retry or an empty queue', async t => {
  const f = await compiledOverviewFixture(t, { queue: async () => ({ code: 401001, data: null, message: '请求未完成', httpStatus: 401, traceId: 'DECLARED_SUPPORT_401' }) })
  assertOverviewPublicState(f, 'unauthorized', '登录已失效')
  assert.equal(overviewButtons(f.root, '重新登录').length, 1); assert.equal(overviewButtons(f.root, '重试').length, 0)
  assert.doesNotMatch(overviewText(f.root), /暂无记录/); assert.equal(f.vm.loading, false)
})

test('A5 compiled queue business NO_DATA_SCOPE remains forbidden without a numeric status', async t => {
  const f = await compiledOverviewFixture(t, { queue: async () => ({ code: 1, data: null, message: '请求未完成', bizCode: 'NO_DATA_SCOPE' }) })
  assertOverviewPublicState(f, 'forbidden', '暂无访问权限'); assert.equal(overviewButtons(f.root, '重试').length, 0)
})

test('A5 compiled queue 5xx takes precedence over stale permission code and retains a safe support number', async t => {
  const f = await compiledOverviewFixture(t, { queue: async () => ({ code: 403001, httpStatus: 503, bizCode: 'NO_PERMISSION', data: null, message: 'column internal_secret SQL failed', traceId: 'DECLARED_SUPPORT_503' }) })
  const panel = assertOverviewPublicState(f, 'error', '操作未完成，请稍后重试')
  assert.match(overviewText(panel), /DECLARED_SUPPORT_503/); assert.doesNotMatch(overviewText(f.root), /internal_secret|column|SQL failed/)
  assert.equal(overviewButtons(f.root, '重试').length, 1); assert.equal(overviewButtons(f.root, '重新登录').length, 0)
})

test('A5 compiled queue ordinary business error retries through the real shared button and recovers healthy rows', async t => {
  let reads = 0
  const f = await compiledOverviewFixture(t, { queue: async () => ++reads === 1 ? { code: 409001, httpStatus: 409, data: null, message: '版本发生变化' } : healthyQueue('当前责任事项') })
  assertOverviewPublicState(f, 'error', '记录已发生变化'); assert.equal(overviewButtons(f.root, '重试').length, 1)
  assert.equal(clickOverviewButton(f.root, '重试'), true); await overviewRenderTerminal()
  assert.equal(reads, 2); assert.match(overviewText(f.root), /当前责任事项/); assert.equal(overviewButtons(f.root, '重试').length, 0); assert.equal(f.vm.loading, false)
})

test('A5 compiled queue thrown typed failure preserves semantic metadata and hides older healthy rows', async t => {
  let reads = 0
  const f = await compiledOverviewFixture(t, { queue: async () => { if (++reads === 1) return healthyQueue('旧责任事项'); throw Object.assign(new Error('请求未完成'), { httpStatus: 403, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_THROWN_403' }) } })
  assert.match(overviewText(f.root), /旧责任事项/)
  assert.equal(clickOverviewButton(f.root, '更新责任队列'), true); await overviewRenderTerminal()
  assertOverviewPublicState(f, 'forbidden', '暂无访问权限'); assert.doesNotMatch(overviewText(f.root), /旧责任事项|暂无记录/)
  assert.equal(reads, 2); assert.equal(f.vm.loading, false); assert.equal(overviewButtons(f.root, '重试').length, 0)
})

test('A5 compiled queue malformed success remains an error and genuine empty success stays empty', async t => {
  let reads = 0
  const f = await compiledOverviewFixture(t, { queue: async () => ++reads === 1 ? { code: 0, message: '回执不完整', data: { items: [] } } : healthyQueue() })
  assertOverviewPublicState(f, 'error', '回执不完整'); assert.doesNotMatch(overviewText(f.root), /暂无记录/)
  clickOverviewButton(f.root, '重试'); await overviewRenderTerminal()
  assertOverviewPublicState(f, 'empty', '暂无记录'); assert.equal(reads, 2); assert.equal(f.vm.loading, false)
})

test('A5 compiled readiness thrown typed403 renders forbidden without queue retry or stale readiness', async t => {
  const f = await compiledOverviewFixture(t, { mode: 'overview', readiness: async () => { throw Object.assign(new Error('请求未完成'), { code: 403001, httpStatus: 403, bizCode: 'NO_PERMISSION' }) } })
  assertOverviewPublicState(f, 'forbidden', '暂无访问权限'); assert.equal(overviewButtons(f.root, '重试').length, 0)
  assert.equal(f.vm.readinessLoading, false); assert.deepEqual(Object.keys(f.vm.readiness), [])
  assert.deepEqual(f.calls.map(call => call[0]), ['queue', 'readiness'])
})

test('A5 compiled readiness 5xx overrides stale login metadata and never displays technical details', async t => {
  const f = await compiledOverviewFixture(t, { mode: 'overview', readiness: async () => { throw Object.assign(new Error('column readiness_private failed'), { httpStatus: 503, code: 401001, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_READINESS_503' }) } })
  const panel = assertOverviewPublicState(f, 'error', '操作未完成，请稍后重试'); assert.match(overviewText(panel), /DECLARED_READINESS_503/)
  assert.doesNotMatch(overviewText(f.root), /readiness_private|column/); assert.equal(overviewButtons(f.root, '重新登录').length, 0)
})

test('A5 compiled readiness ordinary rejection retries to the genuine declared blocked result', async t => {
  let reads = 0
  const f = await compiledOverviewFixture(t, { mode: 'overview', readiness: async () => { if (++reads === 1) throw new Error('检查暂时未完成'); return healthyReadiness() } })
  assertOverviewPublicState(f, 'error', '检查暂时未完成'); clickOverviewButton(f.root, '重试'); await overviewRenderTerminal()
  assert.equal(reads, 2); assert.match(overviewText(f.root), /声明运行检查阻断/); assert.equal(overviewButtons(f.root, '重试').length, 0)
  assert.equal(f.vm.readinessLoading, false); assert.equal(f.vm.readiness.status, 'BLOCKED')
})

test('A5 compiled old identity rejection cannot replace current queue or clear its pending loading', async t => {
  const old = overviewDeferred(), current = overviewDeferred(); let reads = 0
  const f = await compiledOverviewFixture(t, { queue: () => ++reads === 1 ? old.promise : current.promise })
  assert.equal(f.vm.loading, true)
  f.state.claims.userId = 'DECLARED_USER_B'; f.state.ctx.ctxKey = 'DECLARED_CTX_B'; await overviewRenderTerminal()
  assert.equal(reads, 2); assert.equal(f.vm.loading, true)
  old.reject(Object.assign(new Error('旧身份拒绝'), { httpStatus: 403, bizCode: 'NO_PERMISSION' })); await overviewRenderTerminal()
  assert.equal(f.vm.loading, true); assert.equal(f.vm.error, ''); assert.doesNotMatch(overviewText(f.root), /旧身份拒绝|暂无访问权限/)
  current.resolve(healthyQueue('当前身份责任事项')); await overviewRenderTerminal()
  assert.match(overviewText(f.root), /当前身份责任事项/); assert.equal(f.vm.loading, false); assert.equal(f.vm.error, '')
})

test('A5 compiled old readiness rejection cannot replace the newer context result', async t => {
  const old = overviewDeferred(); let reads = 0
  const f = await compiledOverviewFixture(t, { mode: 'overview', readiness: () => ++reads === 1 ? old.promise : Promise.resolve(healthyReadiness()) })
  assert.equal(f.vm.readinessLoading, true)
  f.state.claims.userId = 'DECLARED_USER_B'; f.state.ctx.ctxKey = 'DECLARED_CTX_B'; await overviewRenderTerminal()
  assert.equal(reads, 2); assert.equal(f.vm.readiness.status, 'BLOCKED'); assert.equal(f.vm.readinessLoading, false)
  old.reject(Object.assign(new Error('旧检查拒绝'), { httpStatus: 401 })); await overviewRenderTerminal()
  assert.equal(f.vm.readiness.status, 'BLOCKED'); assert.equal(f.vm.readinessLoading, false); assert.equal(f.vm.readinessError, '')
  assert.doesNotMatch(overviewText(f.root), /旧检查拒绝|登录已失效/)
})

// Navigation ownership uses the actual table slots, RouterView, permission guard
// and commit adapter. Only API reads and legitimate lazy page factories are declared.
import * as overviewNavigationGate from '../src/security/permissionGate.js'
import * as overviewNavigationOwned from '../src/router/ownedAcademicNavigation.js'
import { matchPermission as overviewMatchPermission } from '../src/config/navPlan.js'
import { routeTarget as overviewRouteTarget } from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-data.mjs'
import { routeAllowed as overviewRouteAllowed } from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-runtime.mjs'
import { sourceTimeLabel as overviewSourceTimeLabel } from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-presentation.mjs'

const overviewNavigationRouter = require('vue-router')
const overviewNavigationSource = '/admin/academic-affairs'
const overviewNavigationA = '/admin/academic-affairs/status-changes/101'
const overviewNavigationB = '/admin/academic-affairs/warnings'
const overviewNavigationPatterns = ['academicAffairs.dashboard.view', 'academicAffairs.statusChange.view', 'academicAffairs.warning.view']
const overviewNavigationTick = async () => { for (let i = 0; i < 12; i++) await overviewRenderTerminal() }
async function overviewNavigationUntil(predicate, label) {
  for (let i = 0; i < 120; i++) { await overviewRenderTerminal(); if (predicate()) return }
  assert.fail(`Navigation fixture did not reach ${label}`)
}
const overviewNavigationVisual = name => ({ name, inheritAttrs: false, render: () => h('span') })
const overviewNavigationPagination = compileOverviewSfc('components/common/display/AppPagination.vue')
const overviewNavigationTable = compileOverviewSfc('components/business/DataTable.vue', { AppPagination: overviewNavigationPagination })
const overviewNavigationShell = compileOverviewSfc('components/business/ModulePageShell.vue', { SecurityWatermark: overviewNavigationVisual('DeclaredNoPIIWatermark') })
const overviewNavigationFrame = compileOverviewSfc('modules/academicAffairs/components/AaOverviewPageFrame.vue', { ModulePageShell: overviewNavigationShell })
const overviewNavigationNode = (type, value = '') => Object.assign(overviewNode(type, value), {
  scrollTop: 0,
  closest(selector) { for (let parent = this; parent; parent = parent.parent) if (selector === '.tw-main' && String(parent.props.class || '').split(/\s+/).includes('tw-main')) return parent; return null }
})
const overviewNavigationRenderer = createRenderer({
  createElement: tag => overviewNavigationNode(tag), createText: value => overviewNavigationNode('#text', value), createComment: value => overviewNavigationNode('#comment', value),
  setText(n, value) { n.value = value }, setElementText(n, value) { n.value = value; n.children = [] },
  parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
  patchProp(n, key, _old, value) { n.props[key] = value },
  insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(n); else parent.children.splice(i, 0, n) },
  remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } }
})
function overviewNavigationRow(id, exact) {
  return { todoId: id, todoType: exact ? 'AA_STATUS_APPROVAL' : 'ACAD_WARNING_HANDLE', title: `声明责任${id}`, bizType: exact ? 'AA_STATUS_CHANGE' : 'AA_WARNING', bizId: id,
    sourceBizType: exact ? 'AA_STATUS_CHANGE' : 'AA_WARNING', sourceBizId: id, recordId: id, routeName: exact ? 'todo-route:academic-status-change-detail' : 'todo-route:academic-warning-queue',
    routeParams: { recordId: id }, query: exact ? {} : { status: 'OPEN', recordId: id }, routePath: exact ? overviewNavigationA : overviewNavigationB,
    routeExact: exact, focusMode: exact ? 'DETAIL' : 'NONE', allowedActions: ['OPEN'], version: 1, expectedVersion: 1, sourceModule: 'academic-affairs', priority: 'NORMAL', status: 'PENDING', dueAt: null,
    createdAt: '2026-10-15T00:00:00Z', assigneeId: '301', responsibility: '明确指派给本人', assignmentReason: '正式待办指派给当前账号', blocker: null, completedAt: null }
}
async function overviewNavigationFixture(t, options = {}) {
  const { createRouter, createMemoryHistory, RouterView, RouterLink } = overviewNavigationRouter
  const state = reactive({ claims: { tenantId: 'DECLARED_SCHOOL', userId: '301', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_CONTEXT' }, ctx: { ctxKey: 'DECLARED_SCOPE', permissionPatterns: overviewNavigationPatterns, dataScope: { scope: 'TENANT_ALL' }, permissionVersion: 1, dataScopeVersion: 1 } })
  const contexts = [], requests = [], transitions = [], errors = [], warnings = [], factories = [], mounts = [], unmounts = []
  const lazyA = overviewDeferred(), lazyB = overviewDeferred(), allowed = { rbacOk: true, permissionPatterns: overviewNavigationPatterns }
  const oldGlobals = Object.fromEntries(['window', 'document', 'sessionStorage'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const oldGate = { patterns: overviewNavigationGate.getPermissionPatterns(), entitlements: overviewNavigationGate.getModuleEntitlements(), health: overviewNavigationGate.getModuleAccessHealth(), error: overviewNavigationGate.getRbacLoadFailed() }
  const memory = new Map(), storage = { getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, String(value)), removeItem: key => memory.delete(key) }
  let app, router, vm, stopped = false, restored = false, unregister, removeCanonical, removeAfter, removeError
  const dispose = async () => {
    if (restored) return
    if (app && !stopped) { app.unmount(); stopped = true }
    for (const pending of contexts) pending.resolve(allowed)
    lazyA.resolve(); lazyB.resolve(); await overviewNavigationTick()
    removeCanonical?.(); removeAfter?.(); removeError?.(); unregister?.()
    overviewNavigationGate.clearPermissionPatterns(); overviewNavigationGate.setPermissionPatterns(oldGate.patterns); overviewNavigationGate.setModuleEntitlements(oldGate.entitlements); overviewNavigationGate.setModuleAccessHealth(oldGate.health.healthy, oldGate.health.error); overviewNavigationGate.setRbacLoadFailed(!!oldGate.error, oldGate.error)
    for (const [key, descriptor] of Object.entries(oldGlobals)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    restored = true; assert.deepEqual(errors, []); assert.deepEqual(warnings, [])
  }
  t.after(dispose)
  try {
    Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: { sessionStorage: storage } })
    Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body: overviewNavigationNode('body') } })
    Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: storage })
    overviewNavigationGate.clearPermissionPatterns(); overviewNavigationGate.setModuleEntitlements(['academicAffairs']); overviewNavigationGate.setPermissionPatterns(overviewNavigationPatterns)
    const forbidden = () => { throw new Error('Outside this declared readonly navigation fixture') }
    const request = (path, config = {}) => {
      requests.push({ path, method: config.method || 'GET', params: config.params || null })
      if (path === '/academic-affairs/dashboard/role-queue') {
        assert.equal(config.params.pageSize, 5); assert.ok(['PENDING', 'DONE'].includes(config.params.status))
        return Promise.resolve({ items: [overviewNavigationRow('101', true), overviewNavigationRow('102', false)].map(row => ({ ...row, status: config.params.status })), total: 2, page: config.params.page, pageSize: 5,
          summary: { pending: 2, nearDeadline: 0, done: 2, toStart: null, initiated: null }, sourceTime: '2026-10-15T00:00:00Z', scopeBlocked: false, scopeNote: '声明本人责任', capabilities: { pending: true, done: true, toStart: false, initiated: false }, unavailableReason: '无统一待启动投影' })
      }
      assert.equal(path, '/rbac/current-context'); assert.equal(config.method, undefined)
      const pending = overviewDeferred(); contexts.push(pending); return pending.promise
    }
    const apiScript = readOverviewSource('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
    const api = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiScript}\nreturn academicAffairsApi`)(request, forbidden, forbidden, () => true, () => state.claims, overviewNavigationGate.setPermissionPatterns)
    const Component = compileOverviewSfc(overviewRelative, { DataTable: overviewNavigationTable, LoadingState: ActualLoadingState, ErrorState: ActualErrorState, EmptyState: ActualEmptyState, AppButton: ActualOverviewButton,
      AppTermEntityPicker: overviewNavigationVisual('DeclaredUnopenedPicker'), AaOverviewPageFrame: overviewNavigationFrame, AcademicFlowOverview: overviewNavigationVisual('DeclaredModeTodosNoFlow'), request,
      currentUserFromToken: () => state.claims, academicAffairsApi: api, readinessApi: { get: forbidden, exportXlsx: forbidden }, academicIdentity, createAcademicReturnStore, adaptTypedTodoPage,
      routeTarget: overviewRouteTarget, routeAllowed: overviewRouteAllowed, sourceTimeLabel: overviewSourceTimeLabel, safeBusinessMessage, canEnterRoute: overviewNavigationGate.canEnterRoute, matchPermission: overviewMatchPermission,
      issueFrameOwnedNavigation: overviewNavigationOwned.issueFrameOwnedNavigation })
    const sourceMeta = { moduleCode: 'ACADEMIC_AFFAIRS', permissionAny: ['academicAffairs.dashboard.view', 'academicAffairs.schedule.view'] }
    const Source = { render() { return h(Component, { ctx: state.ctx, mode: 'todos', onVnodeMounted: vnode => { vm = vnode.component.proxy; mounts.push(vnode.component.uid) }, onVnodeUnmounted: vnode => unmounts.push(vnode.component.uid) }) } }
    const body = label => ({ render: () => h('p', `声明只读目标${label}`) })
    const factory = (name, pending) => () => { factories.push(name); return pending.promise.then(() => body(name)) }
    const history = createMemoryHistory(), owned = overviewNavigationOwned.createOwnedHistoryAdapter(history, { resolveLocation: raw => router.resolve(raw), shouldEnforce: path => { const meta = router.resolve(path).meta; return meta.moduleCode === 'ACADEMIC_AFFAIRS' && overviewNavigationGate.canEnterRoute(meta) } })
    router = createRouter({ history: owned.history, routes: [
      { path: overviewNavigationSource, component: Source, meta: sourceMeta },
      { path: '/admin/academic-affairs/status-changes/:id', name: 'aa-status-change-detail', component: factory('A', lazyA), meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.statusChange.view' } },
      { path: overviewNavigationB, name: 'aa-warnings', component: factory('B', lazyB), meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.warning.view' } }
    ] })
    unregister = overviewNavigationOwned.registerOwnedHistoryAdapter(router, owned)
    const index = readOverviewSource('router/index.js'), start = index.indexOf('router.beforeEach(async (to, from, next) => {'), end = index.indexOf('\n\nexport default router', start)
    assert.ok(start > 0 && end > start)
    const registration = index.slice(start, end); assert.equal(registration.split('import.meta.env.PROD').length - 1, 1)
    const guardScope = { router, currentUserFromToken: () => state.claims, getModuleEntitlements: overviewNavigationGate.getModuleEntitlements, academicRoleAllows, academicRoleDefaultPath, hasAcademicRoleMenu, getToken: () => 'DECLARED_NOT_NORMAL_AUTH', request: forbidden, _declaredBuildProd: false, isPlatformPrincipal: () => false, ensurePlatformAccessContext: forbidden, resolvePlatformHome: forbidden,
      GUARDED_MODULES: overviewNavigationGate.GUARDED_MODULES, getPermissionPatterns: overviewNavigationGate.getPermissionPatterns, ensurePermissionPatterns: overviewNavigationGate.ensurePermissionPatterns, getRbacLoadFailed: overviewNavigationGate.getRbacLoadFailed, canEnterRoute: overviewNavigationGate.canEnterRoute, routeAccessNotice: overviewNavigationGate.routeAccessNotice }
    removeCanonical = new Function(...Object.keys(guardScope), `return ${registration.replace('import.meta.env.PROD', '_declaredBuildProd')}`)(...Object.values(guardScope))
    removeAfter = router.afterEach((to, from, failure) => transitions.push({ to: to.fullPath, from: from.fullPath, type: failure?.type ?? null }))
    removeError = router.onError(error => errors.push({ origin: 'router', message: error.message }))
    await router.push({ path: overviewNavigationSource, query: options.query || {} })
    const root = overviewNavigationNode('root')
    app = overviewNavigationRenderer.createApp({ render: () => h('main', { class: 'tw-main' }, [
      h(RouterLink, { to: { path: overviewNavigationSource, query: { tab: 'done' } } }, () => '声明切到已办'),
      h(RouterLink, { to: { path: overviewNavigationSource, query: { termId: '11' } } }, () => '声明切到学期11'), h(RouterView)
    ]) })
    app.use(router); app.config.warnHandler = value => warnings.push(String(value)); app.config.errorHandler = error => errors.push({ origin: 'vue', message: error.message })
    app.mount(root); await router.isReady(); await overviewNavigationUntil(() => vm && !vm.loading && vm.rows.length === 2, 'whole declared queue rendered')
    assert.equal(mounts.length, 1); assert.equal(unmounts.length, 0); assert.equal(requests.length, 1)
    const click = id => {
      const rows = overviewWalk(root).filter(n => n.type === 'tr' && overviewText(n).includes(`声明责任${id}`)); assert.equal(rows.length, 1)
      const buttons = overviewWalk(rows[0]).filter(n => n.type === 'button' && ['继续办理', '前往责任列表'].includes(overviewText(n).trim())); assert.equal(buttons.length, 1)
      const button = buttons[0]; assert.equal(!!button.props.disabled, false); button.props.onClick({ type: 'click', target: button, currentTarget: button })
    }
    const clickLink = label => {
      const links = overviewWalk(root).filter(n => n.type === 'a' && overviewText(n) === label); assert.equal(links.length, 1)
      const link = links[0]; return link.props.onClick({ type: 'click', button: 0, target: link, currentTarget: link, defaultPrevented: false, preventDefault() { this.defaultPrevented = true } })
    }
    return { root, router, history, state, contexts, requests, transitions, errors, warnings, factories, mounts, unmounts, lazyA, lazyB, allowed, storage, click, clickLink, dispose,
      get vm() { return vm }, stop() { if (!stopped) { app.unmount(); stopped = true } } }
  } catch (error) { await dispose(); throw error }
}
const overviewNavigationSucceededA = f => f.transitions.some(row => row.to.split('?')[0] === overviewNavigationA && row.type === null)

test('A5 public newer B selection survives an older preflight response while B lazy component waits', async t => {
  const f = await overviewNavigationFixture(t)
  f.click('101'); f.click('102'); assert.equal(f.contexts.length, 2)
  f.contexts[1].resolve(f.allowed); await overviewNavigationUntil(() => f.factories.includes('B'), 'new B factory')
  assert.equal(f.router.currentRoute.value.path, overviewNavigationSource); assert.equal(f.unmounts.length, 0)
  f.contexts[0].resolve(f.allowed); f.lazyA.resolve(); await overviewNavigationTick(); f.lazyB.resolve()
  await overviewNavigationUntil(() => f.transitions.some(row => row.to.split('?')[0] === overviewNavigationB), 'B settled')
  assert.equal(f.router.currentRoute.value.path, overviewNavigationB); assert.equal(f.history.location, f.router.currentRoute.value.fullPath)
  assert.equal(overviewNavigationSucceededA(f), false); assert.deepEqual(f.factories, ['B']); assert.match(overviewText(f.root), /声明只读目标B/)
})

test('A5 new public selection revokes an already-issued A commit and old finally preserves B ownership', async t => {
  for (const issueBFirst of [false, true]) {
    const f = await overviewNavigationFixture(t)
    try {
      f.click('101'); f.contexts[0].resolve(f.allowed); await overviewNavigationUntil(() => f.factories.includes('A'), 'old A factory')
      f.click('102'); assert.equal(f.contexts.length, 2)
      if (issueBFirst) { f.contexts[1].resolve(f.allowed); await overviewNavigationUntil(() => f.factories.includes('B'), 'new B ticket before old finishes') }
      f.lazyA.resolve(); await overviewNavigationTick()
      assert.equal(f.router.currentRoute.value.path, overviewNavigationSource); assert.equal(f.history.location, overviewNavigationSource)
      assert.equal(f.unmounts.length, 0); assert.equal(overviewNavigationSucceededA(f), false); assert.match(overviewText(f.root), /声明责任102/)
      if (!issueBFirst) { f.contexts[1].resolve(f.allowed); await overviewNavigationUntil(() => f.factories.includes('B'), 'new B factory') }
      f.lazyB.resolve(); await overviewNavigationUntil(() => f.router.currentRoute.value.path === overviewNavigationB, 'new B healthy completion')
      assert.match(overviewText(f.root), /声明只读目标B/); assert.deepEqual(f.errors, []); assert.deepEqual(f.warnings, [])
    } finally { await f.dispose() }
  }
})

test('A5 current preflight denial remains visible and a fresh allowed click preserves query term and return position', async t => {
  const f = await overviewNavigationFixture(t, { query: { termId: '11', page: '1' } })
  const identity = f.vm.identity()
  f.click('102'); f.contexts[0].resolve({ rbacOk: true, permissionPatterns: ['academicAffairs.dashboard.view'] }); await overviewNavigationTick()
  assert.equal(f.router.currentRoute.value.path, overviewNavigationSource); assert.match(overviewText(f.root), /当前身份无法进入该责任页面/); assert.deepEqual(f.factories, [])
  f.click('102'); f.contexts[1].resolve(f.allowed); await overviewNavigationUntil(() => f.factories.includes('B'), 'fresh allowed B factory'); f.lazyB.resolve()
  await overviewNavigationUntil(() => f.router.currentRoute.value.path === overviewNavigationB, 'allowed target')
  const query = f.router.currentRoute.value.query
  assert.equal(query.termId, '11'); assert.equal(query.status, 'OPEN'); assert.equal(query.recordId, '102'); assert.ok(query.returnToken)
  const back = createAcademicReturnStore(f.storage).resolve(query.returnToken, identity)
  assert.equal(back.path, '/admin/academic-affairs?termId=11&page=1'); assert.equal(back.scrollTop, 0)
})

test('A5 stale preflight error cannot overwrite the newer request and current failure permits a fresh retry', async t => {
  const f = await overviewNavigationFixture(t)
  f.click('101'); f.click('102'); f.contexts[0].reject(new Error('旧责任复核失败')); await overviewNavigationTick()
  assert.equal(f.vm.message, ''); assert.deepEqual(f.factories, [])
  f.contexts[1].reject(new Error('当前复核暂不可用')); await overviewNavigationTick()
  assert.match(overviewText(f.root), /当前复核暂不可用/); assert.doesNotMatch(overviewText(f.root), /旧责任复核失败/)
  assert.equal(f.router.currentRoute.value.path, overviewNavigationSource)
  f.click('102'); f.contexts[2].resolve(f.allowed); await overviewNavigationUntil(() => f.factories.includes('B'), 'retry target factory'); f.lazyB.resolve()
  await overviewNavigationUntil(() => f.router.currentRoute.value.path === overviewNavigationB, 'fresh retry completion')
  assert.equal(f.vm.message, ''); assert.match(overviewText(f.root), /声明只读目标B/)
})

test('A6 source tab term identity and unmount changes invalidate only the departing overview preflight', async t => {
  for (const kind of ['tab', 'term', 'identity', 'unmount']) {
    const f = await overviewNavigationFixture(t)
    try {
      f.click('101'); assert.equal(f.contexts.length, 1)
      if (kind === 'tab') await f.clickLink('声明切到已办')
      if (kind === 'term') await f.clickLink('声明切到学期11')
      if (kind === 'identity') { f.state.claims.userId = '302'; f.state.ctx.ctxKey = 'DECLARED_SCOPE_2' }
      if (kind === 'unmount') {
        assert.equal(f.router.currentRoute.value.fullPath, overviewNavigationSource); assert.equal(f.history.location, overviewNavigationSource)
        f.stop()
      }
      await overviewNavigationTick()
      const retainedURL = f.router.currentRoute.value.fullPath, retainedHistory = f.history.location
      if (kind === 'unmount') {
        // Installed Router resets its current route after its last app unmounts;
        // MemoryHistory retains the last committed URL. Neither may change later.
        assert.equal(retainedURL, '/'); assert.equal(retainedHistory, overviewNavigationSource)
        assert.equal(f.vm.disposed, true); assert.deepEqual(f.unmounts, f.mounts)
        assert.equal(f.unmounts.length, 1); assert.doesNotMatch(overviewText(f.root), /声明责任|声明只读目标/)
      } else assert.equal(retainedHistory, retainedURL)
      f.contexts[0].resolve(f.allowed); await overviewNavigationTick()
      assert.equal(f.router.currentRoute.value.fullPath, retainedURL); assert.equal(f.history.location, retainedHistory); assert.deepEqual(f.factories, [])
      if (kind === 'unmount') { assert.equal(f.vm.disposed, true); assert.deepEqual(f.unmounts, f.mounts); assert.doesNotMatch(overviewText(f.root), /声明责任|声明只读目标/) }
      assert.equal(overviewNavigationSucceededA(f), false); assert.equal(f.vm.message, '')
      if (kind === 'tab') assert.equal(f.router.currentRoute.value.query.tab, 'done')
      if (kind === 'term') { assert.equal(f.router.currentRoute.value.query.termId, '11'); assert.equal(f.vm.termId, '11') }
      if (kind !== 'unmount') { assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0); assert.match(overviewText(f.root), /声明责任102/) }
    } finally { await f.dispose() }
  }
})

// Actual client functions and readiness API; declared HTTP200/json only.
// Shared public retry is real; this is not actual network or V4 recovery.
function overviewBodyReadinessClient(fetcher) {
  const source = readFileSync(new URL('../src/services/http/client.js', import.meta.url), 'utf8')
  const rawSource = source.slice(source.indexOf('async function rawRequest('), source.indexOf('function newBrowserSessionId('))
  const failureSource = source.slice(source.indexOf('function transportFailure('), source.indexOf('function markOffline('))
  const transportFailure = new Function(failureSource + ';return transportFailure')()
  const stats = { fetch: 0, json: 0, markOffline: 0, clearOffline: 0, offline: false }
  const failures = [], paths = []
  const env = {
    fetch: async (path, options) => {
      stats.fetch++; paths.push(path); assert.equal(options.method, 'GET'); assert.equal(options.headers.Authorization, undefined)
      const response = await fetcher(path, options)
      return { status: response.status, json: async () => { stats.json++; return response.json() } }
    },
    state: { token: '' }, REQUEST_TIMEOUT_MS: 4000,
    isBackendOffline: () => stats.offline, canUseMockFallback: () => false,
    isWriteMethod: method => !['GET', 'HEAD', 'OPTIONS'].includes(String(method).toUpperCase()),
    API_BASE_URL: '', API_PREFIX: '', normalizeUiError,
    clearOfflineState() { stats.clearOffline++; stats.offline = false },
    markOffline() { stats.markOffline++; stats.offline = true },
    throwOfflineSkip() { throw new Error('Unexpected mock-only cooldown in declared readiness fixture') },
    transportFailure
  }
  const raw = new Function(...Object.keys(env), rawSource + ';return rawRequest')(...Object.values(env))
  const apiSource = readFileSync(new URL('../src/modules/academicAffairs/api/academic-affairs-dashboard-readiness.api.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace('export const academicAffairsDashboardReadinessApi', 'const academicAffairsDashboardReadinessApi')
  const api = new Function('request', 'requestBlob', apiSource + ';return academicAffairsDashboardReadinessApi')(
    async (...args) => { try { return await raw(...args) } catch (error) { failures.push(error); throw error } },
    () => { throw new Error('Export is forbidden in body-readiness fixture') }
  )
  return { api, stats, failures, paths }
}

test('A5 actual readiness client body cancellation renders the shared retry and recovers the declared blocked result', async t => {
  const original = new DOMException('Declared readiness body cancellation', 'AbortError')
  let reads = 0
  const client = overviewBodyReadinessClient(async () => ({ status: 200, json: async () => {
    if (++reads === 1) throw original
    return { code: 0, data: healthyReadiness() }
  } }))
  const f = await compiledOverviewFixture(t, { mode: 'overview', readiness: term => client.api.get(term) })
  assertOverviewPublicState(f, 'error', '系统暂时无法完成该操作，请稍后重试')
  assert.equal(client.failures.length, 1); assert.equal(client.failures[0].bizCode, 'REQUEST_TIMEOUT')
  assert.equal(client.failures[0].transportErrorName, 'AbortError'); assert.equal(client.failures[0].cause, original)
  assert.equal(client.stats.markOffline, 0); assert.equal(client.stats.offline, false)
  assert.equal(f.vm.readinessLoading, false); assert.deepEqual(Object.keys(f.vm.readiness), [])
  assert.equal(overviewButtons(f.root, '重试').length, 1)
  assert.equal(clickOverviewButton(f.root, '重试'), true); await overviewRenderTerminal()
  assert.equal(client.stats.fetch, 2); assert.equal(client.stats.json, 2)
  assert.deepEqual(client.paths, ['/academic-affairs/dashboard/readiness', '/academic-affairs/dashboard/readiness'])
  assert.deepEqual(f.calls.map(call => call[0]), ['queue', 'readiness', 'readiness'])
  assert.equal(f.vm.readiness.status, 'BLOCKED'); assert.equal(f.vm.readinessLoading, false); assert.equal(f.vm.readinessError, '')
  assert.match(overviewText(f.root), /声明运行检查阻断/); assert.equal(overviewButtons(f.root, '重试').length, 0)
})

test('A6 late actual readiness body timeout cannot replace a newer identity result or publish its error', async t => {
  const pendingBody = overviewDeferred(), bodyEntered = overviewDeferred()
  const original = new DOMException('Declared old readiness body timeout', 'TimeoutError')
  let reads = 0
  const client = overviewBodyReadinessClient(async () => ({ status: 200, json: async () => {
    if (++reads === 1) { bodyEntered.resolve(); return pendingBody.promise }
    return { code: 0, data: { ...healthyReadiness(), conclusion: '当前身份声明运行检查阻断' } }
  } }))
  const f = await compiledOverviewFixture(t, { mode: 'overview', readiness: term => client.api.get(term) })
  await bodyEntered.promise
  assert.equal(client.stats.fetch, 1); assert.equal(f.vm.readinessLoading, true)
  f.state.claims.userId = 'DECLARED_BODY_USER_B'; f.state.ctx.ctxKey = 'DECLARED_BODY_CTX_B'; await overviewRenderTerminal()
  assert.equal(client.stats.fetch, 2); assert.equal(f.vm.readiness.status, 'BLOCKED'); assert.equal(f.vm.readiness.conclusion, '当前身份声明运行检查阻断')
  assert.equal(f.vm.readinessLoading, false); assert.equal(f.vm.readinessError, '')
  pendingBody.reject(original); await overviewRenderTerminal()
  assert.equal(client.failures.length, 1); assert.equal(client.failures[0].bizCode, 'REQUEST_TIMEOUT')
  assert.equal(client.failures[0].transportErrorName, 'TimeoutError'); assert.equal(client.failures[0].cause, original)
  assert.equal(client.stats.markOffline, 0); assert.equal(f.vm.readiness.status, 'BLOCKED')
  assert.equal(f.vm.readiness.conclusion, '当前身份声明运行检查阻断'); assert.equal(f.vm.readinessLoading, false); assert.equal(f.vm.readinessError, '')
  assert.equal(overviewButtons(f.root, '重试').length, 0); assert.match(overviewText(f.root), /当前身份声明运行检查阻断/)
  assert.doesNotMatch(overviewText(f.root), /Declared old readiness|请求超时/)
})
