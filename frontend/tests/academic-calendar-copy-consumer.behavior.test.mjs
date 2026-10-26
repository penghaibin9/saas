import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import process from 'node:process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { matchPermission } from '../src/config/navPlan.js'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import { installDirtyFormGuard } from '../src/router/dirtyFormGuard.js'
import { systemConfirm } from '../src/services/systemDialog.js'
const repo = fileURLToPath(new URL('../../', import.meta.url))
const require = createRequire(import.meta.url)
const Vue = require('vue'), Router = require('vue-router')
const { parse, compileTemplate } = require('@vue/compiler-sfc')
const receipt = { localCalls: [], warnings: [], runtimeBehaviorErrors: [], counts: { canonicalWriteAdapters: 0, applyCopyInvocations: 0 } }
const listeners = () => ({ addEventListener() {}, removeEventListener() {} })
globalThis.window = listeners(); globalThis.document = listeners()
globalThis.sessionStorage = { getItem: () => null, setItem() { throw new Error('No persistence writes') } }
const { h, cloneVNode, createRenderer, reactive, nextTick } = Vue
const pass = name => ({ name, inheritAttrs: false, setup(_props, { slots, attrs }) { return () => h('section', attrs, [slots.actions?.(), slots['header-extra']?.(), slots.default?.(), slots.footer?.()]) } })
const hidden = name => ({ name, render: () => h('section') })
const visuals = { ModulePageShell: pass('ModulePageShell'), AppSectionCard: pass('AppSectionCard'), AppFormItem: pass('AppFormItem') }
for (const name of ['DataTable', 'StatusTag', 'LoadingState', 'ErrorState', 'EmptyState', 'AppDrawer', 'AppTextInput', 'AppDatePicker', 'AppTermEntityPicker', 'AppConfirmDialog', 'AaCalendarMonth', 'AaCalendarArchivePanel']) visuals[name] = hidden(name)
visuals.AppInlineAlert = { props: ['description'], render() { return h('aside', {}, this.description || '') } }
function compile(path, scope = {}) {
  const { descriptor, errors } = parse(fs.readFileSync(process.env.AA_CALENDAR_COPY_BEFORE_DIR && /academicAffairs\/(components|views)\//.test(path) ? `${process.env.AA_CALENDAR_COPY_BEFORE_DIR}/${path}` : `${repo}/${path}`, 'utf8'), { filename: path }); assert.deepEqual(errors, [])
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const component = new Function(...Object.keys(scope), `${script}\nreturn component`)(...Object.values(scope))
  const compiled = compileTemplate({ source: descriptor.template.content, filename: path, id: path, compilerOptions: { mode: 'function' } }); assert.deepEqual(compiled.errors, [])
  component.render = new Function('Vue', compiled.code)(Vue); return component
}
const AppButton = compile('frontend/src/components/ui/AppButton.vue'), AppSelect = compile('frontend/src/components/common/form/AppSelect.vue')
const node = (type, text = '') => ({ type, tagName: type.toUpperCase(), text, props: {}, children: [], parent: null, listeners: {}, addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler) }, removeEventListener(name, handler) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== handler) } })
const renderer = createRenderer({ createElement: tag => node(tag), createText: text => node('#text', text), createComment: text => node('#comment', text), setText: (n, text) => { n.text = text }, setElementText: (n, text) => { n.text = text; n.children = [] }, parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null, patchProp: (n, key, _old, value) => { n.props[key] = value }, insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const at = anchor ? parent.children.indexOf(anchor) : -1; if (at < 0) parent.children.push(n); else parent.children.splice(at, 0, n) }, remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } } })
const walk = n => [n, ...n.children.flatMap(walk)], text = n => n.type === '#comment' ? '' : n.text + n.children.map(text).join('')
const tick = async () => { await nextTick(); await nextTick() }
const nativeButton = (root, label) => { const all = walk(root).filter(n => n.type === 'button' && text(n).trim() === label); assert.equal(all.length, 1, `Unique nativebutton ${label}`); return all[0] }
function dispatchButton(root, label) { assert.ok(['negative-control', '预览复制结果', '刷新权威预览'].includes(label), 'No apply action'); const n = nativeButton(root, label); if (n.props.disabled) return false; for (const handler of Array.isArray(n.props.onClick) ? n.props.onClick : [n.props.onClick]) handler?.({ type: 'click', target: n, controlled: true }); return true }
function dispatchSelect(root, value) { const all = walk(root).filter(n => n.type === 'select'); assert.equal(all.length, 1); const n = all[0]; if (n.props.disabled) return false; const option = walk(n).find(o => o.type === 'option' && String(o.props.value) === String(value)); assert.ok(option); if (option.props.disabled) return false; n.props.onChange?.({ type: 'change', target: { value }, controlled: true }); return true }
const ctx = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '受控教务' }, dataScope: { scope: 'SCHOOL', scopeName: '受控范围' }, permissionPatterns: ['academicAffairs.calendar.manage', 'academicAffairs.calendar.view', 'academicAffairs.term.view'] })
const fixtures = [{ termId: 'controlled-source-1', yearCode: 'LOCAL_SOURCE1', termNo: 1, status: 'PUBLISHED', startDate: '2026-09-01', endDate: '2027-01-31', teachingWeeks: 17 }, { termId: 'controlled-source-2', yearCode: 'LOCAL_SOURCE2', termNo: 2, status: 'PUBLISHED', startDate: '2027-02-01', endDate: '2027-06-30', teachingWeeks: 17 }, { termId: 'controlled-target', yearCode: 'LOCAL_TARGET', termNo: 1, status: 'DRAFT', startDate: '2027-09-01', endDate: '2028-01-31', teachingWeeks: 17 }, { termId: 'controlled-target-other', yearCode: 'LOCAL_OTHER', termNo: 2, status: 'DRAFT', startDate: '2028-02-01', endDate: '2028-06-30', teachingWeeks: 17 }]
function payload(source, target, marker = 'LOCAL_COPY_OLD') { return { code: 0, data: { sourceTerm: { termId: source }, targetTerm: { termId: target }, mappingRule: 'TEACHING_WEEK_RELATIVE_WITH_EXAM_WEEK_ALIGNMENT', readyCount: 0, reviewCount: 1, blockedCount: 0, targetExistingCount: 0, canConfirm: true, nextStep: marker, items: [{ sourceEventId: 'local-event', eventType: 'HOLIDAY', startDate: '2027-09-01', endDate: '2027-09-01', swapToDate: null, remark: marker, status: 'REVIEW', needsReview: true, reasons: ['LOCAL_REVIEW'] }] } } }
async function mount() {
  const requests = [], state = reactive({ ctx: ctx('A') }), claims = reactive({ tenantId: 'controlled-tenant-A', userId: 'controlled-user', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'A' })
  const flow = { identity: () => academicIdentity(claims, state.ctx), restorePosition() {} }
  const api = new Proxy({}, { get(_t, name) { return (...args) => { receipt.localCalls.push({ kind: `academicAffairsApi.${String(name)}`, args, fixtureOnly: true }); if (name === 'getCurrentTerm') return Promise.resolve({ code: 0, data: { termId: 'controlled-source-1', canDirectSwitch: true } }); if (name === 'getCalendar') return Promise.resolve({ code: 0, data: [] }); receipt.counts.canonicalWriteAdapters++; throw new Error(`API writes forbidden: ${String(name)}`) } } })
  const previewApi = { previewCalendarCopy(target, source) { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); const request = { target, source, promise, resolve, reject, settled: false }; requests.push(request); receipt.localCalls.push({ kind: 'previewCalendarCopy', target, source, fixtureOnly: true }); return promise } }
  const toast = { warning: message => receipt.localCalls.push({ kind: 'toast.warning', message }), success() {}, error() {} }
  const child = compile('frontend/src/modules/academicAffairs/components/AaCalendarCopyPanel.vue', { ...visuals, AppButton, AppSelect, academicAffairsApi: api, termCalendarConvenienceApi: previewApi, toast })
  const parent = compile('frontend/src/modules/academicAffairs/views/AaCalendarView.vue', { ...visuals, AppButton, AppSelect, AaCalendarCopyPanel: child, academicAffairsApi: api, academicAffairsTermDetailApi: {}, loadAcademicTermCatalog: async () => fixtures.map(row => ({ ...row })), toast, matchPermission, currentUserFromToken: () => claims, systemConfirm })
  const router = Router.createRouter({ history: Router.createMemoryHistory(), routes: [{ name: 'aa-calendar', path: '/admin/academic-affairs/calendar', component: parent }, { name: 'controlled-holding', path: '/controlled-holding', component: { render: () => h('article', {}, 'CONTROLLED_HOLDING') } }] })
  await router.push('/admin/academic-affairs/calendar?termId=controlled-target&tab=events'); await router.isReady()
  const disposeGuard = installDirtyFormGuard(router), guard = window.__SAAS_DIRTY_FORM_GUARD__
  let vm
  const app = renderer.createApp({ render() { return h(Router.RouterView, {}, { default: ({ Component }) => Component ? cloneVNode(Component, { ctx: state.ctx, onVnodeMounted: vnode => { if (vnode.component?.type.name === 'AaCalendarView') vm = vnode.component.proxy } }) : null }) } })
  app.use(router); app.provide('academicFlow', flow)
  app.config.warnHandler = (message, _instance, trace) => { receipt.warnings.push({ message, trace }); void trace }
  app.config.errorHandler = (error, _instance, info) => { receipt.runtimeBehaviorErrors.push({ message: error.message, stack: error.stack, info }); void info }
  const root = node('root'); app.mount(root)
  for (let i = 0; i < 12 && !vm?.$refs.calendarCopyPanel; i++) await tick()
  assert.ok(vm?.$refs.calendarCopyPanel, 'Actual parent mounted child through actualRouterView')
  assert.equal(vm.canEditEvents, true); assert.equal(guard.handlesRoute(router.currentRoute.value), true); assert.equal(guard.isDirty(), false)
  const panel = vm.$refs.calendarCopyPanel
  assert.equal(router.currentRoute.value.matched[0].instances.default, vm, 'Actual RouterView registered actual parent for source option hooks')
  return { state, claims, flow, requests, router, app, vm, panel, root, parent, guard, async settle(request, response = payload(request.source, request.target), reject = false) { request.settled = true; if (reject) request.reject(response); else request.resolve(response); await request.promise.catch(() => {}); await tick() }, async close() { app.unmount(); disposeGuard(); for (const request of requests) if (!request.settled) request.resolve(payload(request.source, request.target)); await tick() } }
}

async function fixture(t) {
  const f = await mount()
  t.after(async () => { await f.close(); assert.equal(receipt.counts.canonicalWriteAdapters, 0); assert.equal(receipt.counts.applyCopyInvocations, 0) })
  return f
}
function checkbox(root) { const matches = walk(root).filter(n => n.type === 'input' && n.props.type === 'checkbox'); assert.equal(matches.length, 1); return matches[0] }
function checkReview(root) { const input = checkbox(root); if (input.props.disabled) return false; input.checked = true; for (const handler of input.listeners.change || []) handler({ target: input, controlled: true }); return true }

test('actual AppSelect and AppButton native negative controls and parent disabled copy controls reject dispatch', async t => {
  for (const disabled of [true, false]) {
    let updated = 0; const app = renderer.createApp({ render: () => h(AppSelect, { disabled, options: [{ value: 'allowed', label: 'Allowed' }, { value: 'blocked', label: 'Blocked', disabled: true }], 'onUpdate:modelValue': () => updated++ }) }), root = node('root')
    app.mount(root); await tick(); assert.equal(dispatchSelect(root, 'blocked'), false); assert.equal(dispatchSelect(root, 'allowed'), !disabled); assert.equal(updated, disabled ? 0 : 1); app.unmount()
  }
  for (const props of [{ disabled: true }, { loading: true }, {}]) {
    let clicked = 0; const app = renderer.createApp({ render: () => h(AppButton, { ...props, onClick: () => clicked++ }, () => 'negative-control') }), root = node('root')
    app.mount(root); await tick(); dispatchButton(root, 'negative-control'); assert.equal(clicked, props.disabled || props.loading ? 0 : 1); app.unmount()
  }
  const f = await fixture(t); f.vm.adding = true; await tick()
  assert.equal(dispatchButton(f.panel.$el, '预览复制结果'), false)
  assert.equal(dispatchSelect(f.panel.$el, 'controlled-source-2'), false)
  await f.panel.loadPreview(); assert.equal(f.requests.length, 0); assert.equal(f.panel.canApply, false)
})

test('native preview publishes parent busy before nextTick and actual memory router rejects pending update and leave', async t => {
  const f = await fixture(t); assert.equal(dispatchButton(f.panel.$el, '预览复制结果'), true)
  assert.equal(f.vm.copying, true, 'Actual native handler produces copying synchronously')
  assert.equal(f.vm.busy, true)
  const callbacks = []; f.parent.beforeRouteUpdate.call(f.vm, {}, {}, value => callbacks.push(value)); assert.deepEqual(callbacks, [false])
  await tick(); assert.equal(dispatchButton(f.panel.$el, '预览复制结果'), false); assert.equal(dispatchSelect(f.panel.$el, 'controlled-source-2'), false); assert.equal(f.requests.length, 1)
  const original = f.router.currentRoute.value.fullPath
  for (const destination of ['/admin/academic-affairs/calendar?termId=controlled-target&tab=holiday', '/controlled-holding']) { const failure = await f.router.push(destination); assert.ok(Router.isNavigationFailure(failure, Router.NavigationFailureType.aborted)); assert.equal(f.router.currentRoute.value.fullPath, original) }
  await f.settle(f.requests[0]); assert.equal(f.vm.busy, false)
  const direct = f.panel.loadPreview(); assert.equal(f.vm.busy, true, 'Actual method also produces busy synchronously'); await f.settle(f.requests[1]); await direct
  const navigation = await f.router.push('/controlled-holding'); await tick(); assert.equal(navigation, undefined); assert.ok(text(f.root).includes('CONTROLLED_HOLDING'))
})

test('existing source and target invalidation preserve review acknowledgement without creating copy events', async t => {
  const f = await fixture(t); dispatchButton(f.panel.$el, '预览复制结果'); await tick(); await f.settle(f.requests[0])
  assert.equal(f.panel.canApply, false); assert.equal(checkReview(f.panel.$el), true); await tick(); assert.equal(f.panel.reviewConfirmed, true); assert.equal(f.panel.canApply, true)
  const seq = f.panel.previewSeq; assert.equal(dispatchSelect(f.panel.$el, 'controlled-source-2'), true)
  assert.equal(f.panel.sourceTermId, 'controlled-source-2')
  assert.equal(f.panel.canApply, false, 'Source selection immediately rejects old review before watcher/render flush')
  await tick()
  assert.ok(f.panel.previewSeq > seq); assert.equal(f.panel.preview, null); assert.equal(f.panel.reviewConfirmed, false)
  dispatchButton(f.panel.$el, '预览复制结果'); await tick(); await f.settle(f.requests[1])
  const beforeTargetSeq = f.panel.previewSeq
  await f.router.push('/admin/academic-affairs/calendar?termId=controlled-target-other&tab=events'); await tick()
  assert.ok(f.panel.previewSeq > beforeTargetSeq); assert.equal(f.panel.targetTermId, 'controlled-target-other'); assert.equal(f.panel.preview, null); assert.equal(f.panel.reviewConfirmed, false)
})

test('disabled refresh and pending review controls stay disabled while method entries remain gated', async t => {
  const f = await fixture(t); dispatchButton(f.panel.$el, '预览复制结果'); await tick(); await f.settle(f.requests[0])
  f.vm.adding = true; await tick(); assert.equal(dispatchButton(f.panel.$el, '刷新权威预览'), false); assert.equal(checkReview(f.panel.$el), false)
  await f.panel.loadPreview(); assert.equal(f.requests.length, 1)
  f.vm.adding = false; await tick(); dispatchButton(f.panel.$el, '刷新权威预览'); await tick()
  assert.equal(checkReview(f.panel.$el), false); assert.equal(f.panel.canApply, false); assert.equal(dispatchButton(f.panel.$el, '刷新权威预览'), false)
  await f.settle(f.requests[1]); assert.equal(f.vm.busy, false)
})

test('actual provided identity function invalidates same-instance preview and old success or finally cannot clear new busy', async t => {
  const f = await fixture(t); dispatchButton(f.panel.$el, '预览复制结果'); await tick(); const old = f.requests[0], uid = f.panel.$.uid, identity = f.flow.identity()
  f.claims.activeContextId = 'controlled-context-B'; assert.equal(f.panel.loading, false, 'Identity invalidation releases old pending synchronously'); assert.equal(f.vm.busy, false); await tick(); assert.notEqual(f.flow.identity(), identity); assert.equal(f.panel.$.uid, uid); assert.equal(f.vm.busy, false)
  dispatchButton(f.panel.$el, '预览复制结果'); await tick(); assert.equal(f.requests.length, 2)
  await f.settle(old, payload(old.source, old.target, 'LOCAL_OLD_IDENTITY')); assert.equal(f.panel.preview, null); assert.equal(f.panel.loading, true); assert.equal(f.vm.busy, true); assert.ok(!text(f.panel.$el).includes('LOCAL_OLD_IDENTITY'))
  await f.settle(f.requests[1]); assert.equal(f.panel.loading, false); assert.equal(f.vm.busy, false); assert.ok(f.panel.preview)
})

test('ctx invalidation and current or late rejected previews preserve current error and busy ownership', async t => {
  const f = await fixture(t), errors = receipt.runtimeBehaviorErrors.length
  dispatchButton(f.panel.$el, '预览复制结果'); await tick(); const old = f.requests[0]
  f.state.ctx = { ...f.state.ctx, ctxKey: 'controlled-B' }; await tick(); assert.equal(f.panel.preview, null); assert.equal(f.vm.busy, false)
  dispatchButton(f.panel.$el, '预览复制结果'); await tick(); assert.equal(f.requests.length, 2)
  await f.settle(old, new Error('LOCAL_OLD_REJECTION'), true); assert.equal(f.panel.error, ''); assert.equal(f.panel.loading, true); assert.equal(f.vm.busy, true)
  await f.settle(f.requests[1], new Error('LOCAL_CURRENT_REJECTION'), true); assert.equal(f.panel.loading, false); assert.equal(f.vm.busy, false); assert.ok(f.panel.error); assert.equal(receipt.runtimeBehaviorErrors.length, errors)
  dispatchButton(f.panel.$el, '预览复制结果'); await tick(); await f.settle(f.requests[2], { code: 1, message: '受控复制预览失败' }); assert.equal(f.panel.error, '受控复制预览失败'); assert.equal(f.panel.preview, null); assert.equal(f.vm.busy, false)
})

test('actual shared guard still rejects controlled dirty leave and late unmounted preview cannot mutate dead or fresh panels', async t => {
  const f = await fixture(t); let prompts = 0; f.guard.registerConfirmation(() => { prompts++; return false }); f.guard.markDirty()
  const original = f.router.currentRoute.value.fullPath, failure = await f.router.push('/controlled-holding'); assert.ok(Router.isNavigationFailure(failure, Router.NavigationFailureType.aborted)); assert.equal(f.router.currentRoute.value.fullPath, original); assert.equal(prompts, 1); assert.equal(f.guard.isDirty(), true)
  f.guard.markSaved(); dispatchButton(f.panel.$el, '预览复制结果'); await tick(); const dead = f.panel, request = f.requests[0]; f.app.unmount(); await tick()
  const fresh = await fixture(t); assert.notEqual(fresh.panel.$.uid, dead.$.uid); await f.settle(request)
  assert.equal(dead.preview, null); assert.equal(dead.loading, false); assert.equal(fresh.panel.preview, null); assert.ok(!text(fresh.panel.$el).includes('LOCAL_COPY_OLD'))
})
