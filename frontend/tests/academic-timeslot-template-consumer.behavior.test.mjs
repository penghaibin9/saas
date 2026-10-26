import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import process from 'node:process'
import { createRequire } from 'node:module'
import { matchPermission } from '../src/config/navPlan.js'
import { academicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import { systemConfirm } from '../src/services/systemDialog.js'

const require = createRequire(import.meta.url)
const Vue = require('vue')
const { parse, compileTemplate } = require('@vue/compiler-sfc')
const { h, reactive, createRenderer, nextTick } = Vue
const source = relative => fs.readFileSync(process.env.AA_TEMPLATE_BEFORE_DIR && relative.includes('academicAffairs/') ? `${process.env.AA_TEMPLATE_BEFORE_DIR}/frontend/src/${relative}` : new URL(`../src/${relative}`, import.meta.url), 'utf8')
const display = name => ({ name, inheritAttrs: false, setup(_props, { slots, attrs }) { return () => h('section', attrs, [slots.actions?.(), slots['header-extra']?.(), slots.default?.(), slots.footer?.()]) } })
const hidden = name => ({ name, render: () => h('section') })
const visuals = Object.fromEntries(['ModulePageShell', 'AppSectionCard', 'AppFormItem'].map(name => [name, display(name)]))
for (const name of ['DataTable', 'StatusTag', 'LoadingState', 'ErrorState', 'EmptyState', 'AppDrawer', 'AppTextInput', 'AppNumberInput', 'AppDatePicker', 'AppTimePicker', 'AppTimeSlotPicker', 'AppConfirmDialog']) visuals[name] = hidden(name)
visuals.AppInlineAlert = { props: ['description'], render() { return h('aside', {}, this.description || '') } }
function compile(relative, scope = {}) {
  const { descriptor, errors } = parse(source(relative), { filename: relative })
  assert.deepEqual(errors, [])
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const component = new Function(...Object.keys(scope), `${script}\nreturn component`)(...Object.values(scope))
  const compiled = compileTemplate({ source: descriptor.template.content, filename: relative, id: relative, compilerOptions: { mode: 'function' } })
  assert.deepEqual(compiled.errors, [])
  component.render = new Function('Vue', compiled.code)(Vue)
  return component
}
const AppButton = compile('components/ui/AppButton.vue')
const node = (type, text = '') => ({ type, tagName: type.toUpperCase(), text, props: {}, children: [], parent: null, listeners: {}, addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler) }, removeEventListener(name, handler) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== handler) } })
const renderer = createRenderer({
  createElement: tag => node(tag), createText: text => node('#text', text), createComment: text => node('#comment', text),
  setText: (n, text) => { n.text = text }, setElementText: (n, text) => { n.text = text; n.children = [] }, parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
  patchProp: (n, key, _old, value) => { n.props[key] = value },
  insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(n); else parent.children.splice(index, 0, n) },
  remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } }
})
const walk = n => [n, ...n.children.flatMap(walk)]
const text = n => n.type === '#comment' ? '' : n.text + n.children.map(text).join('')
const tick = async () => { await nextTick(); await nextTick() }
function button(root, label) { const matches = walk(root).filter(n => n.type === 'button' && text(n).trim() === label); assert.equal(matches.length, 1); return matches[0] }
function dispatch(root, label) {
  assert.ok(['标准 8 节', '标准 10 节', '检查当前作息', 'negative-control'].includes(label), 'Never dispatch apply/create')
  const target = button(root, label)
  if (target.props.disabled) return false
  for (const handler of Array.isArray(target.props.onClick) ? target.props.onClick : [target.props.onClick]) handler?.({ type: 'click', target, controlledHost: true })
  return true
}
async function click(root, label) { const sent = dispatch(root, label); await tick(); return sent }
const context = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '受控教务' }, dataScope: { scopeName: '受控本校' }, permissionPatterns: ['academicAffairs.timeslot.manage', 'academicAffairs.classTimeBand.view', 'academicAffairs.classTimeBand.manage'] })
const payload = key => ({ code: 0, data: { templateKey: key, readyCount: 1, existingCount: 0, blockedCount: 0, nextStep: `LOCAL_${key}`, items: [{ status: 'READY', desired: { slotNo: key === 'STANDARD_8' ? 8 : 10, slotName: `LOCAL_${key}`, startTime: '08:00', endTime: '08:45' }, reason: `LOCAL_${key}_ROW` }] } })
async function fixture(t) {
  const requests = [], errors = [], warnings = [], writes = []
  const api = new Proxy({}, { get(_target, name) { return () => { if (name === 'getTimeSlots' || name === 'getTimeBands') return Promise.resolve({ code: 0, data: [] }); writes.push(name); throw new Error('Canonical writes forbidden in non-apply fixture') } } })
  const previewAPI = { previewTimeSlotTemplate(key) { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); requests.push({ key, resolve, reject, promise, settled: false }); return promise } }
  const toast = { success() {}, warning() {}, error() {} }
  const child = compile('modules/academicAffairs/components/AaTimeSlotTemplatePanel.vue', { ...visuals, AppButton, academicAffairsApi: api, termCalendarConvenienceApi: previewAPI, toast })
  const parent = compile('modules/academicAffairs/views/AaTimeSlotView.vue', { ...visuals, AppButton, AaTimeSlotTemplatePanel: child, academicAffairsApi: api, toast, matchPermission, systemConfirm })
  const state = reactive({ ctx: context('A') }), claims = reactive({ tenantId: 'controlled-tenant-A', userId: 'controlled-user', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'A' })
  const flow = { identity: () => academicIdentity(claims, state.ctx) }
  const root = node('root'), app = renderer.createApp({ render: () => h(parent, { ctx: state.ctx, ref: 'parent' }) })
  app.provide('academicFlow', flow)
  app.config.globalProperties.$route = reactive({ path: '/admin/academic-affairs/time-slots', query: {} })
  app.config.globalProperties.$router = { replace: async () => { throw new Error('No router navigation in controlled component test') } }
  app.config.warnHandler = message => warnings.push(message)
  app.config.errorHandler = error => errors.push(error)
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  const wrapper = app.mount(root); await tick()
  const vm = wrapper.$refs.parent, panel = vm.$refs.timeSlotTemplate
  assert.equal(vm.canManageSlots, true); assert.ok(panel)
  let unmounted = false
  t.after(async () => {
    try { if (!unmounted) app.unmount(); for (const request of requests) if (!request.settled) request.resolve(payload(request.key)); await tick(); assert.deepEqual(writes, [], 'No apply/canonical write invocation') }
    finally { if (previousWindow) Object.defineProperty(globalThis, 'window', previousWindow); else delete globalThis.window }
  })
  return { requests, errors, warnings, state, claims, flow, root, app, vm, panel, parent, unmount() { app.unmount(); unmounted = true }, async settle(request, response = payload(request.key), reject = false) { request.settled = true; if (reject) request.reject(response); else request.resolve(response); await request.promise.catch(() => {}); await tick() } }
}

test('actual native AppButton disabled and loading block host dispatch; parent disabled reaches template controls', async t => {
  for (const props of [{ disabled: true }, { loading: true }, {}]) {
    let emitted = 0
    const app = renderer.createApp({ render: () => h(AppButton, { ...props, onClick: () => emitted++ }, () => 'negative-control') }), root = node('root')
    app.mount(root); await tick(); await click(root, 'negative-control'); assert.equal(emitted, props.disabled || props.loading ? 0 : 1); app.unmount()
  }
  const f = await fixture(t); f.vm.adding = true; await tick()
  assert.equal(button(f.panel.$el, '标准 10 节').props.disabled, true)
  assert.equal(button(f.panel.$el, '检查当前作息').props.disabled, true)
  assert.equal(await click(f.panel.$el, '标准 10 节'), false)
  await f.panel.loadPreview(); assert.equal(f.requests.length, 0)
})

test('pending preview produces actual parent busy and blocks its existing route hooks, while repeated check stays disabled', async t => {
  const f = await fixture(t)
  assert.equal(dispatch(f.panel.$el, '检查当前作息'), true)
  assert.equal(f.vm.templateApplying, true, 'Native dispatch publishes parent busy synchronously before any nextTick')
  assert.equal(f.vm.busy, true)
  for (const name of ['beforeRouteLeave', 'beforeRouteUpdate']) { const results = []; f.parent[name].call(f.vm, {}, {}, value => results.push(value)); assert.deepEqual(results, [false]) }
  await tick()
  assert.equal(f.panel.loading, true); assert.equal(await click(f.panel.$el, '检查当前作息'), false); assert.equal(f.requests.length, 1)
  assert.equal(f.vm.templateApplying, true); assert.equal(f.vm.busy, true)
  for (const name of ['beforeRouteLeave', 'beforeRouteUpdate']) { const results = []; f.parent[name].call(f.vm, {}, {}, value => results.push(value)); assert.deepEqual(results, [false]) }
  await f.settle(f.requests[0]); assert.equal(f.vm.busy, false); assert.equal(f.panel.preview.templateKey, 'STANDARD_8'); assert.deepEqual(f.errors, []); assert.deepEqual(f.warnings, [])
  const direct = f.panel.loadPreview()
  assert.equal(f.vm.busy, true, 'Actual method publishes busy synchronously')
  for (const name of ['beforeRouteLeave', 'beforeRouteUpdate']) { const results = []; f.parent[name].call(f.vm, {}, {}, value => results.push(value)); assert.deepEqual(results, [false]) }
  await f.settle(f.requests[1]); await direct; assert.equal(f.vm.busy, false)
})

test('pending choices stay natively blocked; context invalidation rejects old preview without clearing newer pending', async t => {
  const f = await fixture(t); await click(f.panel.$el, '检查当前作息'); const old = f.requests[0]
  assert.equal(await click(f.panel.$el, '标准 10 节'), false); assert.equal(f.panel.templateKey, 'STANDARD_8')
  f.state.ctx = context('B'); await tick()
  await click(f.panel.$el, '标准 10 节'); await click(f.panel.$el, '检查当前作息'); assert.equal(f.requests.length, 2)
  await f.settle(old); assert.equal(f.panel.preview, null); assert.equal(f.panel.loading, true); assert.equal(f.vm.busy, true)
  assert.ok(button(f.panel.$el, '标准 10 节').props.class.includes('app-button--primary'))
  assert.ok(!text(f.panel.$el).includes('LOCAL_STANDARD_8_ROW'))
  await f.settle(f.requests[1]); assert.equal(f.panel.preview.templateKey, 'STANDARD_10'); assert.ok(text(f.panel.$el).includes('LOCAL_STANDARD_10_ROW')); assert.equal(f.vm.busy, false)
})

test('actual parent ctx and provided identity function reject previous-context preview in the same permitted instance', async t => {
  const f = await fixture(t); await click(f.panel.$el, '检查当前作息'); const uid = f.panel.$.uid, oldIdentity = f.flow.identity()
  f.state.ctx = context('B'); f.claims.tenantId = 'controlled-tenant-B'; await tick()
  assert.notEqual(f.flow.identity(), oldIdentity); assert.equal(f.vm.canManageSlots, true); assert.equal(f.vm.$refs.timeSlotTemplate.$.uid, uid)
  await f.settle(f.requests[0]); assert.equal(f.panel.preview, null); assert.ok(!text(f.panel.$el).includes('LOCAL_STANDARD_8_ROW')); assert.equal(f.vm.busy, false)
  await click(f.panel.$el, '检查当前作息'); await f.settle(f.requests[1]); assert.equal(f.panel.preview.templateKey, 'STANDARD_8')
})

test('identity function change alone invalidates preview even when parent ctx object stays the same', async t => {
  const f = await fixture(t); await click(f.panel.$el, '检查当前作息'); const originalCtx = f.state.ctx
  f.claims.activeContextId = 'new-active-context'; await tick(); assert.equal(f.state.ctx, originalCtx)
  await f.settle(f.requests[0]); assert.equal(f.panel.preview, null); assert.equal(f.panel.loading, false); assert.equal(f.vm.busy, false)
})

test('handled failure releases actual busy; late rejection cannot clear a newer preview request', async t => {
  const f = await fixture(t); await click(f.panel.$el, '检查当前作息')
  await f.settle(f.requests[0], new Error('local deferred rejection'), true)
  assert.equal(f.panel.loading, false); assert.equal(f.vm.busy, false); assert.ok(f.panel.error); assert.deepEqual(f.errors, [])
  await click(f.panel.$el, '检查当前作息'); const old = f.requests[1]; f.state.ctx = context('B'); await tick(); await click(f.panel.$el, '标准 10 节'); await click(f.panel.$el, '检查当前作息')
  await f.settle(old, new Error('old rejected request'), true); assert.equal(f.panel.loading, true); assert.equal(f.panel.error, ''); assert.equal(f.vm.busy, true)
  await f.settle(f.requests[2], { code: 1, message: '受控预览失败' }); assert.equal(f.panel.error, '受控预览失败'); assert.equal(f.panel.templateKey, 'STANDARD_10'); assert.equal(f.vm.busy, false); assert.deepEqual(f.errors, [])
})

test('unmount rejects late mutation of the old panel and never contaminates a fresh visible child', async t => {
  const f = await fixture(t); await click(f.panel.$el, '检查当前作息'); const old = f.panel, uid = old.$.uid
  f.unmount(); await tick(); assert.equal(f.root.children.length, 0)
  const fresh = await fixture(t); assert.notEqual(fresh.panel.$.uid, uid)
  await f.settle(f.requests[0]); assert.equal(old.preview, null); assert.equal(old.loading, false); assert.equal(fresh.panel.preview, null); assert.ok(!text(fresh.panel.$el).includes('LOCAL_STANDARD_8_ROW'))
})

// Additional apply contracts use a separate fixture. Original preview-only seven
// tests, their dispatch whitelist and their no-canonical-write finalizer stay intact.
import { normalizeUiError as templateOutcomeNormalize } from '../src/utils/presentationSafety.js'
import { setImmediate as templateOutcomeImmediate } from 'node:timers'
const templateOutcomeTick = async () => { await new Promise(resolve => templateOutcomeImmediate(resolve)); await nextTick() }
async function templateOutcomeFixture(t, { failure = 'none', failAt = 2, refreshFails = false, holdWrite = false } = {}) {
  const previous = Object.fromEntries(['window', 'document', 'sessionStorage'].map(k => [k, Object.getOwnPropertyDescriptor(globalThis, k)]))
  const memory = new Map(), storage = { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, String(v)), removeItem: k => memory.delete(k) }, host = { addEventListener() {}, removeEventListener() {} }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: { ...host } })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { ...host, body: node('body') } })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: storage })
  let app, vm, stopped = false, releaseWrite
  const errors = [], warnings = [], requests = [], dtos = [], previews = [], toasts = [], mounts = [], unmounts = []
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } releaseWrite?.(); await templateOutcomeTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) }
    finally { for (const [k, d] of Object.entries(previous)) { if (d) Object.defineProperty(globalThis, k, d); else delete globalThis[k] } }
  })
  const prohibited = () => { throw new Error('Outside this declared template apply contract') }
  const claims = { tenantId: 'DECLARED_TEMPLATE_TENANT', userId: 'DECLARED_TEMPLATE_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_TEMPLATE_CONTEXT' }
  const makeContext = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务' }, dataScope: { scope: 'SCHOOL', scopeName: key }, permissionPatterns: ['academicAffairs.timeslot.view', 'academicAffairs.timeslot.manage'] })
  const state = reactive({ ctx: makeContext('A') })
  const standard = [[1, '第1节', '08:00', '08:45'], [2, '第2节', '08:55', '09:40'], [3, '第3节', '10:00', '10:45'], [4, '第4节', '10:55', '11:40'], [5, '第5节', '14:00', '14:45'], [6, '第6节', '14:55', '15:40'], [7, '第7节', '16:00', '16:45'], [8, '第8节', '16:55', '17:40']]
  const desired = standard.map(([slotNo, slotName, startTime, endTime]) => ({ slotNo, slotName, startTime, endTime }))
  const acks = desired.map((row, i) => ({ slotId: String(901 + i), ...row, campusCode: '', enabled: true, status: 'ENABLED', version: 0 }))
  const facts = acks.slice(0, 6), list = () => facts.map(row => ({ ...row, timeBandCount: 0, referenceCount: 0, referenceStatus: 'UNUSED' }))
  const counts = { slots: 0, preview: 0, writes: 0 }
  const previewValue = () => ({ templateKey: 'STANDARD_8', templateLabel: '标准 8 节作息', items: desired.map(wanted => { const current = facts.find(row => row.slotNo === wanted.slotNo) || null; return { desired: wanted, status: current ? 'EXISTS' : 'READY', reason: current ? '同序号节次已存在且时间一致，无需重复创建' : '', current } }), readyCount: 8 - facts.length, existingCount: facts.length, blockedCount: 0, canConfirm: facts.length < 8, nextStep: facts.length < 8 ? '可确认应用；仅创建 READY 项，每一项仍进入 create_time_slot() 最终校验。' : '当前作息已覆盖该模板，无需重复应用。' })
  const response = data => ({ status: 200, json: async () => ({ code: 0, data, message: 'ok' }) })
  const fetch = async (url, options) => {
    const u = new URL(url, 'https://declared.invalid'), method = options.method || 'GET', body = options.body ? JSON.parse(options.body) : null
    requests.push({ path: u.pathname, method, body }); assert.ok(requests.length <= 7); assert.equal(u.search, ''); assert.equal(options.credentials, 'include'); assert.ok(options.signal instanceof AbortSignal)
    if (u.pathname === '/api/v1/academic-affairs/time-slots/template-preview') {
      assert.equal(method, 'POST'); assert.deepEqual(body, { templateKey: 'STANDARD_8' }); assert.ok(++counts.preview <= 2)
      if (refreshFails && counts.preview === 2) return { status: 503, json: async () => ({ code: 503001, bizCode: 'SERVICE_UNAVAILABLE', message: '权威作息预览暂不可用', data: null }) }
      const data = JSON.parse(JSON.stringify(previewValue())); previews.push(data); return response(data)
    }
    assert.equal(u.pathname, '/api/v1/academic-affairs/time-slots')
    if (method === 'GET') { assert.ok(++counts.slots <= 2); return response({ items: list() }) }
    assert.equal(method, 'POST'); const ordinal = ++counts.writes; assert.ok(ordinal <= 2, 'No automatic third canonical create'); assert.deepEqual(body, desired[ordinal + 5])
    if (failure !== 'none' && ordinal === failAt) {
      if (holdWrite) await new Promise(resolve => { releaseWrite = resolve })
      if (failure === 'conflict') return { status: 409, json: async () => ({ code: 409001, bizCode: 'DATA_CONFLICT', message: '节次序号已有安排', traceId: 'DECLARED_TEMPLATE_CONFLICT', data: null }) }
      if (failure === 'timeout') throw new DOMException('Declared response unavailable', 'AbortError')
      throw new TypeError('Declared response unavailable')
    }
    facts.push(acks[ordinal + 5]); return response(acks[ordinal + 5])
  }
  const toast = { info: message => toasts.push({ kind: 'info', message }), success: message => toasts.push({ kind: 'success', message }), error: prohibited, warning: prohibited }
  const clientSource = source('services/http/client.js').replace(/^import .*$/gm, '').replace(/\bimport\.meta\b/g, '__buildMeta').replace(/^export /gm, '')
  const client = new Function('API_BASE_URL', 'API_PREFIX', 'allowMockFallback', 'realApiEnabled', 'toast', 'normalizeUiError', 'fetch', 'sessionStorage', 'localStorage', 'BroadcastChannel', '__buildMeta', `${clientSource}\nreturn { request, setToken }`)('', '/api/v1', () => false, () => true, toast, templateOutcomeNormalize, fetch, storage, storage, undefined, { env: { DEV: false } })
  client.setToken('DECLARED_NONEMPTY_TOKEN_NOT_NORMAL_LOGIN_PROOF')
  const apiSource = source('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const production = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(client.request, prohibited, prohibited, () => true, () => claims, prohibited)
  const api = { ...production, createTimeSlot(...args) { return production.createTimeSlot(...args).then(dto => { dtos.push(structuredClone(dto)); return dto }) } }
  const convenience = source('modules/academicAffairs/api/term-calendar-convenience.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default termCalendarConvenienceApi\s*$/m, '')
  const termCalendarConvenienceApi = new Function('request', `${convenience}\nreturn termCalendarConvenienceApi`)(client.request)
  const AppInlineAlert = compile('components/common/AppInlineAlert.vue')
  const child = compile('modules/academicAffairs/components/AaTimeSlotTemplatePanel.vue', { ...visuals, AppButton, AppInlineAlert, academicAffairsApi: api, termCalendarConvenienceApi, toast })
  const parent = compile('modules/academicAffairs/views/AaTimeSlotView.vue', { ...visuals, AppButton, AppInlineAlert, AaTimeSlotTemplatePanel: child, academicAffairsApi: api, toast, matchPermission, systemConfirm })
  const root = node('root'), route = reactive({ path: '/admin/academic-affairs/time-slots', fullPath: '/admin/academic-affairs/time-slots', query: {} })
  app = renderer.createApp({ render: () => state.ctx ? h(parent, { ctx: state.ctx, onVnodeMounted: vnode => { vm = vnode.component.proxy; mounts.push(vnode.component.uid) }, onVnodeUnmounted: vnode => unmounts.push(vnode.component.uid) }) : null })
  app.provide('academicFlow', { identity: () => academicIdentity(claims, state.ctx || {}), restorePosition() {} })
  app.config.globalProperties.$route = route; app.config.globalProperties.$router = { replace: prohibited, push: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = message => warnings.push(String(message)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  const until = async (predicate, label) => { for (let i = 0; i < 60; i++) { await templateOutcomeTick(); if (predicate()) return } assert.fail(label) }
  const publicClick = label => { const found = walk(root).filter(n => n.type === 'button' && text(n).trim() === label); assert.equal(found.length, 1, label); const n = found[0]; assert.equal(!!n.props.disabled, false, label); for (const fn of Array.isArray(n.props.onClick) ? n.props.onClick : [n.props.onClick]) { assert.equal(typeof fn, 'function'); fn({ type: 'click', target: n, currentTarget: n }) } }
  app.mount(root); await until(() => counts.slots === 1 && !vm?.loading && vm?.$refs.timeSlotTemplate, 'Initial full slots read')
  assert.deepEqual(vm.rows, list()); assert.equal(vm.rows.length, 6); assert.equal(vm.canManageSlots, true); assert.equal(vm.tab, 'periods')
  const start = async () => { publicClick('检查当前作息'); await until(() => counts.preview === 1 && vm.$refs.timeSlotTemplate.preview && !vm.$refs.timeSlotTemplate.loading, 'Initial preview'); assert.deepEqual(vm.$refs.timeSlotTemplate.preview, previews[0]); assert.equal(vm.$refs.timeSlotTemplate.preview.readyCount, 2); assert.equal(vm.$refs.timeSlotTemplate.canApply, true); publicClick('创建 2 个缺失节次') }
  const settled = async () => { await until(() => dtos.length === counts.writes && counts.preview === 2 && !vm.$refs.timeSlotTemplate.loading && !vm.$refs.timeSlotTemplate.applying && !vm.loading, 'Parent GET and automatic preview terminal'); assert.deepEqual(vm.rows, list()); assert.equal(counts.slots, 2); assert.equal(counts.writes, failure !== 'none' ? failAt : 2); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) }
  const alertTexts = () => walk(root).filter(n => n.props.role === 'alert').map(text)
  return { root, state, counts, dtos, previews, requests, acks, list, toasts, mounts, unmounts, until, start, settled, publicClick, alertTexts, vm: () => vm, panel: () => vm.$refs.timeSlotTemplate, release: () => releaseWrite?.(), async changeContext(remount) { if (remount) { state.ctx = null; await templateOutcomeTick() } state.ctx = makeContext('B'); await until(() => vm?.$refs.timeSlotTemplate && !vm.loading && (remount ? mounts.length === 2 : vm.ctx.ctxKey === 'B'), 'New owner established') } }
}
function assertTemplateUnknown(f, acknowledged) {
  const alerts = f.alertTexts(), message = alerts.find(value => /结果.*未确认|结果未知/.test(value))
  assert.ok(message, 'Unknown write outcome remains publicly visible after automatic preview')
  assert.match(message, new RegExp(`已成功创建 ${acknowledged} 项`)); assert.match(message, /回执/); assert.match(message, /作息|操作记录/)
  for (const raw of ['被系统拒绝', 'mock', 'TypeError', 'AbortError']) assert.equal(message.includes(raw), false)
  const dto = f.dtos.at(-1); assert.equal(dto.code, 503002); assert.equal(dto.httpStatus, undefined)
}

test('template all acknowledged creates keep normal success and authoritative preview without residual write or read errors', async t => {
  const f = await templateOutcomeFixture(t); await f.start(); await f.settled()
  assert.deepEqual(f.dtos.map(v => v.code), [0, 0]); assert.equal(f.vm().rows.length, 8); assert.equal(f.panel().preview.existingCount, 8); assert.equal(f.panel().preview.readyCount, 0)
  assert.equal(f.alertTexts().some(value => /未确认|被系统拒绝/.test(value)), false); assert.equal(f.panel().error, ''); assert.equal(f.panel().writeOutcome, ''); assert.equal(f.toasts.filter(v => v.kind === 'success').length, 1); assert.equal(f.requests.length, 6)
})

test('template definitive second409 remains a conflict with one received ACK after authoritative automatic preview', async t => {
  const f = await templateOutcomeFixture(t, { failure: 'conflict' }); await f.start(); await f.settled()
  const message = f.alertTexts().find(value => value.includes('被系统拒绝')); assert.ok(message); assert.match(message, /已成功创建 1 项/); assert.equal(message.includes('结果尚未确认'), false)
  assert.equal(f.dtos[1].code, 409001); assert.equal(f.dtos[1].httpStatus, 409); assert.equal(f.vm().rows.length, 7); assert.equal(f.panel().preview.readyCount, 1); assert.equal(f.requests.length, 6)
})

test('template first actual transport503002 keeps zero-ACK unknown result after successful automatic preview without retrying create', async t => {
  const f = await templateOutcomeFixture(t, { failure: 'network', failAt: 1 }); await f.start(); await f.settled(); assertTemplateUnknown(f, 0)
  assert.equal(f.vm().rows.length, 6); assert.equal(f.panel().preview.readyCount, 2); assert.equal(f.counts.writes, 1); assert.equal(f.requests.length, 5)
})

test('template second actual REQUEST_TIMEOUT keeps one-ACK unknown result after successful automatic preview without create replay', async t => {
  const f = await templateOutcomeFixture(t, { failure: 'timeout' }); await f.start(); await f.settled(); assertTemplateUnknown(f, 1)
  assert.equal(f.dtos[1].bizCode, 'REQUEST_TIMEOUT'); assert.equal(f.vm().rows.length, 7); assert.equal(f.panel().preview.readyCount, 1); assert.equal(f.counts.writes, 2); assert.equal(f.requests.length, 6)
})

test('template failed automatic preview preserves both unresolved write outcome and the actual read failure in public alerts', async t => {
  const f = await templateOutcomeFixture(t, { failure: 'network', refreshFails: true }); await f.start(); await f.settled(); assertTemplateUnknown(f, 1)
  assert.equal(f.panel().preview, null); assert.equal(f.panel().canApply, false); assert.ok(f.panel().error); assert.equal(f.alertTexts().length, 2); assert.ok(f.alertTexts().some(value => value.includes(f.panel().error))); assert.equal(f.vm().rows.length, 7); assert.equal(f.requests.length, 6)
})

test('template same-instance context change prevents late old create failure or automatic preview from replacing new owner feedback', async t => {
  const f = await templateOutcomeFixture(t, { failure: 'network', holdWrite: true }); await f.start(); await f.until(() => f.counts.writes === 2 && f.dtos.length === 1, 'Old second create held')
  const oldUID = f.mounts[0]; await f.changeContext(false); f.publicClick('检查当前作息'); await f.until(() => f.counts.preview === 2 && f.panel().preview && !f.panel().loading, 'B fresh preview')
  assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0); assert.equal(f.vm().$.uid, oldUID); const previewBefore = JSON.parse(JSON.stringify(f.panel().preview))
  f.release(); await f.until(() => f.dtos.length === 2, 'Old transport returned'); await templateOutcomeTick()
  assert.deepEqual(f.panel().preview, previewBefore); assert.equal(f.panel().error, ''); assert.equal(f.panel().writeOutcome, ''); assert.equal(f.alertTexts().some(v => /未确认|被系统拒绝/.test(v)), false); assert.deepEqual(f.counts, { slots: 1, preview: 2, writes: 2 }); assert.equal(f.requests.length, 5)
})

test('template actual unmount and new owner mount reject late old create publication and extra reads or canonical replay', async t => {
  const f = await templateOutcomeFixture(t, { failure: 'network', holdWrite: true }); await f.start(); await f.until(() => f.counts.writes === 2 && f.dtos.length === 1, 'Old second create held')
  const oldPanel = f.panel(); await f.changeContext(true); assert.equal(oldPanel.disposed, true); assert.equal(f.mounts.length, 2); assert.equal(f.unmounts.length, 1); assert.notEqual(f.mounts[0], f.mounts[1])
  f.publicClick('检查当前作息'); await f.until(() => f.counts.preview === 2 && f.panel().preview && !f.panel().loading, 'B complete fresh preview'); const previewBefore = JSON.parse(JSON.stringify(f.panel().preview))
  f.release(); await f.until(() => f.dtos.length === 2, 'Old transport returned'); await templateOutcomeTick()
  assert.deepEqual(f.panel().preview, previewBefore); assert.equal(f.panel().error, ''); assert.equal(f.panel().writeOutcome, ''); assert.equal(f.alertTexts().some(v => /未确认|被系统拒绝/.test(v)), false); assert.deepEqual(f.counts, { slots: 2, preview: 2, writes: 2 }); assert.equal(f.requests.length, 6)
})

// Canonical ACK contracts use a separate actual-client fixture. The complete
// original fourteen tests and their helpers above remain byte-for-byte intact.
async function templateAckFixture(t, { ackAt = 1, ackData = () => null, failure = 'none', failAt = 2, refreshFails = false, holdWrite = false } = {}) {
  const previous = Object.fromEntries(['window', 'document', 'sessionStorage'].map(k => [k, Object.getOwnPropertyDescriptor(globalThis, k)]))
  const memory = new Map(), storage = { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, String(v)), removeItem: k => memory.delete(k) }, host = { addEventListener() {}, removeEventListener() {} }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: { ...host } })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { ...host, body: node('body') } })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: storage })
  let app, vm, stopped = false, restored = false, releaseWrite
  const errors = [], warnings = [], requests = [], dtos = [], previews = [], toasts = [], mounts = [], unmounts = []
  const close = async () => {
    if (restored) return
    try { if (app && !stopped) { app.unmount(); stopped = true } releaseWrite?.(); await templateOutcomeTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) }
    finally { for (const [k, d] of Object.entries(previous)) { if (d) Object.defineProperty(globalThis, k, d); else delete globalThis[k] } restored = true }
  }
  t.after(close)
  const prohibited = () => { throw new Error('Outside this declared template apply contract') }
  const claims = { tenantId: 'DECLARED_TEMPLATE_TENANT', userId: 'DECLARED_TEMPLATE_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_TEMPLATE_CONTEXT' }
  const makeContext = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务' }, dataScope: { scope: 'SCHOOL', scopeName: key }, permissionPatterns: ['academicAffairs.timeslot.view', 'academicAffairs.timeslot.manage'] })
  const state = reactive({ ctx: makeContext('A') })
  const standard = [[1, '第1节', '08:00', '08:45'], [2, '第2节', '08:55', '09:40'], [3, '第3节', '10:00', '10:45'], [4, '第4节', '10:55', '11:40'], [5, '第5节', '14:00', '14:45'], [6, '第6节', '14:55', '15:40'], [7, '第7节', '16:00', '16:45'], [8, '第8节', '16:55', '17:40']]
  const desired = standard.map(([slotNo, slotName, startTime, endTime]) => ({ slotNo, slotName, startTime, endTime }))
  const acks = desired.map((row, i) => ({ slotId: String(901 + i), ...row, campusCode: '', enabled: true, status: 'ENABLED', version: 0 }))
  const facts = acks.slice(0, 6), list = () => facts.map(row => ({ ...row, timeBandCount: 0, referenceCount: 0, referenceStatus: 'UNUSED' }))
  const counts = { slots: 0, preview: 0, writes: 0 }
  const previewValue = () => ({ templateKey: 'STANDARD_8', templateLabel: '标准 8 节作息', items: desired.map(wanted => { const current = facts.find(row => row.slotNo === wanted.slotNo) || null; return { desired: wanted, status: current ? 'EXISTS' : 'READY', reason: current ? '同序号节次已存在且时间一致，无需重复创建' : '', current } }), readyCount: 8 - facts.length, existingCount: facts.length, blockedCount: 0, canConfirm: facts.length < 8, nextStep: facts.length < 8 ? '可确认应用；仅创建 READY 项，每一项仍进入 create_time_slot() 最终校验。' : '当前作息已覆盖该模板，无需重复应用。' })
  const response = data => ({ status: 200, json: async () => ({ code: 0, data, message: 'ok' }) })
  const fetch = async (url, options) => {
    const u = new URL(url, 'https://declared.invalid'), method = options.method || 'GET', body = options.body ? JSON.parse(options.body) : null
    requests.push({ path: u.pathname, method, body }); assert.ok(requests.length <= 7); assert.equal(u.search, ''); assert.equal(options.credentials, 'include'); assert.ok(options.signal instanceof AbortSignal)
    if (u.pathname === '/api/v1/academic-affairs/time-slots/template-preview') {
      assert.equal(method, 'POST'); assert.deepEqual(body, { templateKey: 'STANDARD_8' }); assert.ok(++counts.preview <= 2)
      if (refreshFails && counts.preview === 2) return { status: 503, json: async () => ({ code: 503001, bizCode: 'SERVICE_UNAVAILABLE', message: '权威作息预览暂不可用', data: null }) }
      const data = JSON.parse(JSON.stringify(previewValue())); previews.push(data); return response(data)
    }
    assert.equal(u.pathname, '/api/v1/academic-affairs/time-slots')
    if (method === 'GET') { assert.ok(++counts.slots <= 2); return response({ items: list() }) }
    assert.equal(method, 'POST'); const ordinal = ++counts.writes; assert.ok(ordinal <= 2, 'No automatic third canonical create'); assert.deepEqual(body, desired[ordinal + 5])
    if (failure !== 'none' && ordinal === failAt) {
      if (holdWrite) await new Promise(resolve => { releaseWrite = resolve })
      if (failure === 'conflict') return { status: 409, json: async () => ({ code: 409001, bizCode: 'DATA_CONFLICT', message: '节次序号已有安排', traceId: 'DECLARED_TEMPLATE_CONFLICT', data: null }) }
      if (failure === 'timeout') throw new DOMException('Declared response unavailable', 'AbortError')
      throw new TypeError('Declared response unavailable')
    }
    // A malformed success body does not prove that the request had no effect.
    const canonical = acks[ordinal + 5]; facts.push(canonical)
    return response(ordinal === ackAt ? ackData({ ...canonical }) : canonical)
  }
  const toast = { info: message => toasts.push({ kind: 'info', message }), success: message => toasts.push({ kind: 'success', message }), error: prohibited, warning: prohibited }
  const clientSource = source('services/http/client.js').replace(/^import .*$/gm, '').replace(/\bimport\.meta\b/g, '__buildMeta').replace(/^export /gm, '')
  const client = new Function('API_BASE_URL', 'API_PREFIX', 'allowMockFallback', 'realApiEnabled', 'toast', 'normalizeUiError', 'fetch', 'sessionStorage', 'localStorage', 'BroadcastChannel', '__buildMeta', `${clientSource}\nreturn { request, setToken }`)('', '/api/v1', () => false, () => true, toast, templateOutcomeNormalize, fetch, storage, storage, undefined, { env: { DEV: false } })
  client.setToken('DECLARED_NONEMPTY_TOKEN_NOT_NORMAL_LOGIN_PROOF')
  const apiSource = source('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const production = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(client.request, prohibited, prohibited, () => true, () => claims, prohibited)
  const api = { ...production, createTimeSlot(...args) { return production.createTimeSlot(...args).then(dto => { dtos.push(structuredClone(dto)); return dto }) } }
  const convenience = source('modules/academicAffairs/api/term-calendar-convenience.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default termCalendarConvenienceApi\s*$/m, '')
  const termCalendarConvenienceApi = new Function('request', `${convenience}\nreturn termCalendarConvenienceApi`)(client.request)
  const AppInlineAlert = compile('components/common/AppInlineAlert.vue')
  const child = compile('modules/academicAffairs/components/AaTimeSlotTemplatePanel.vue', { ...visuals, AppButton, AppInlineAlert, academicAffairsApi: api, termCalendarConvenienceApi, toast })
  const parent = compile('modules/academicAffairs/views/AaTimeSlotView.vue', { ...visuals, AppButton, AppInlineAlert, AaTimeSlotTemplatePanel: child, academicAffairsApi: api, toast, matchPermission, systemConfirm })
  const root = node('root'), route = reactive({ path: '/admin/academic-affairs/time-slots', fullPath: '/admin/academic-affairs/time-slots', query: {} })
  app = renderer.createApp({ render: () => state.ctx ? h(parent, { ctx: state.ctx, onVnodeMounted: vnode => { vm = vnode.component.proxy; mounts.push(vnode.component.uid) }, onVnodeUnmounted: vnode => unmounts.push(vnode.component.uid) }) : null })
  app.provide('academicFlow', { identity: () => academicIdentity(claims, state.ctx || {}), restorePosition() {} })
  app.config.globalProperties.$route = route; app.config.globalProperties.$router = { replace: prohibited, push: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = message => warnings.push(String(message)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  const until = async (predicate, label) => { for (let i = 0; i < 60; i++) { await templateOutcomeTick(); if (predicate()) return } assert.fail(label) }
  const publicClick = label => { const found = walk(root).filter(n => n.type === 'button' && text(n).trim() === label); assert.equal(found.length, 1, label); const n = found[0]; assert.equal(!!n.props.disabled, false, label); for (const fn of Array.isArray(n.props.onClick) ? n.props.onClick : [n.props.onClick]) { assert.equal(typeof fn, 'function'); fn({ type: 'click', target: n, currentTarget: n }) } }
  app.mount(root); await until(() => counts.slots === 1 && !vm?.loading && vm?.$refs.timeSlotTemplate, 'Initial full slots read')
  assert.deepEqual(vm.rows, list()); assert.equal(vm.rows.length, 6); assert.equal(vm.canManageSlots, true); assert.equal(vm.tab, 'periods')
  const start = async () => { publicClick('检查当前作息'); await until(() => counts.preview === 1 && vm.$refs.timeSlotTemplate.preview && !vm.$refs.timeSlotTemplate.loading, 'Initial preview'); assert.deepEqual(vm.$refs.timeSlotTemplate.preview, previews[0]); assert.equal(vm.$refs.timeSlotTemplate.preview.readyCount, 2); assert.equal(vm.$refs.timeSlotTemplate.canApply, true); publicClick('创建 2 个缺失节次') }
  const settled = async () => { await until(() => dtos.length === counts.writes && counts.preview === 2 && !vm.$refs.timeSlotTemplate.loading && !vm.$refs.timeSlotTemplate.applying && !vm.loading, 'Parent GET and automatic preview terminal'); assert.deepEqual(vm.rows, list()); assert.equal(counts.slots, 2); assert.ok(counts.writes >= ackAt && counts.writes <= 2); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) }
  const alertTexts = () => walk(root).filter(n => n.props.role === 'alert').map(text)
  return { root, state, counts, dtos, previews, requests, acks, list, toasts, mounts, unmounts, until, start, settled, close, publicClick, alertTexts, vm: () => vm, panel: () => vm.$refs.timeSlotTemplate, release: () => releaseWrite?.(), async changeContext(remount) { if (remount) { state.ctx = null; await templateOutcomeTick() } state.ctx = makeContext('B'); await until(() => vm?.$refs.timeSlotTemplate && !vm.loading && (remount ? mounts.length === 2 : vm.ctx.ctxKey === 'B'), 'New owner established') } }
}
function assertTemplateUnconfirmedAck(f, count) {
  const message = f.alertTexts().find(value => /结果.*未确认|结果未知/.test(value))
  assert.ok(message, 'Incomplete canonical row ACK stays unknown after authority preview')
  assert.match(message, new RegExp(`已成功创建 ${count} 项`)); assert.match(message, /仅计已收到成功回执/)
  assert.equal(f.toasts.filter(value => value.kind === 'success').length, 0)
  for (const raw of ['被系统拒绝', 'mock', 'TypeError']) assert.equal(message.includes(raw), false)
  assert.equal(f.dtos.at(-1).code, 0)
}

test('template first missing or malformed canonical ACK stops the next create and counts zero confirmed rows', async t => {
  const variants = [
    { label: 'null row', value: () => null },
    { label: 'missing row', value: () => undefined },
    { label: 'empty row', value: () => ({}) },
    { label: 'missing canonical identity', value: row => { delete row.slotId; return row } },
    { label: 'invalid canonical version', value: row => ({ ...row, version: -1 }) }
  ]
  for (const variant of variants) {
    const f = await templateAckFixture(t, { ackAt: 1, ackData: variant.value })
    try {
      await f.start(); await f.settled()
      assert.equal(f.counts.writes, 1, variant.label); assert.equal(f.dtos.length, 1); assert.equal(f.dtos[0].code, 0)
      assertTemplateUnconfirmedAck(f, 0)
      assert.deepEqual(f.counts, { slots: 2, preview: 2, writes: 1 }); assert.equal(f.requests.length, 5)
      assert.deepEqual(f.vm().rows, f.list()); assert.equal(f.vm().rows.length, 7); assert.equal(f.panel().preview.existingCount, 7); assert.equal(f.panel().preview.readyCount, 1)
    } finally { await f.close() }
  }
})

test('template preserves one confirmed row when the second canonical ACK does not match its requested slot or time', async t => {
  for (const mismatch of [row => ({ ...row, slotNo: 99 }), row => ({ ...row, startTime: '17:00' })]) {
    const f = await templateAckFixture(t, { ackAt: 2, ackData: mismatch })
    try {
      await f.start(); await f.settled()
      assert.deepEqual(f.dtos[0], { code: 0, data: f.acks[6], message: 'ok' }); assert.equal(f.dtos[1].code, 0)
      assert.notDeepEqual(f.dtos[1].data, f.acks[7]); assertTemplateUnconfirmedAck(f, 1)
      assert.deepEqual(f.counts, { slots: 2, preview: 2, writes: 2 }); assert.equal(f.requests.length, 6)
      assert.deepEqual(f.vm().rows, f.list()); assert.equal(f.vm().rows.length, 8); assert.equal(f.panel().preview.existingCount, 8); assert.equal(f.panel().preview.readyCount, 0)
    } finally { await f.close() }
  }
})


// Separate whole-client fixture for response-body cancellation and HTTP500 with
// a stale401 code. Old fixtures and all old oracles above stay untouched.
async function templateTransportBoundaryFixture(t, failure) {
  const previous = Object.fromEntries(['window', 'document', 'sessionStorage'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const memory = new Map(), storage = { getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, String(value)), removeItem: key => memory.delete(key) }, host = { addEventListener() {}, removeEventListener() {} }
  let app, vm, closed = false
  const errors = [], warnings = [], requests = [], dtos = [], rawFailures = [], toasts = [], previews = []
  const close = async () => {
    if (closed) return
    try { app?.unmount(); await templateOutcomeTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } closed = true }
  }
  t.after(close)
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: { ...host } })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { ...host, body: node('body') } })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: storage })
  const prohibited = () => { throw new Error('Outside the declared template transport boundary') }
  const claims = { tenantId: 'DECLARED_TEMPLATE_TENANT', userId: 'DECLARED_TEMPLATE_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_TEMPLATE_CONTEXT' }
  const ctx = { ctxKey: 'DECLARED_TRANSPORT_CTX', currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校' }, permissionPatterns: ['academicAffairs.timeslot.view', 'academicAffairs.timeslot.manage'] }
  const standard = [[1, '第1节', '08:00', '08:45'], [2, '第2节', '08:55', '09:40'], [3, '第3节', '10:00', '10:45'], [4, '第4节', '10:55', '11:40'], [5, '第5节', '14:00', '14:45'], [6, '第6节', '14:55', '15:40'], [7, '第7节', '16:00', '16:45'], [8, '第8节', '16:55', '17:40']]
  const desired = standard.map(([slotNo, slotName, startTime, endTime]) => ({ slotNo, slotName, startTime, endTime }))
  const acks = desired.map((row, index) => ({ slotId: String(901 + index), ...row, campusCode: '', enabled: true, status: 'ENABLED', version: 0 }))
  const facts = acks.slice(0, 6), list = () => facts.map(row => ({ ...row, timeBandCount: 0, referenceCount: 0, referenceStatus: 'UNUSED' }))
  const counts = { slots: 0, preview: 0, writes: 0, refresh: 0 }
  const bodyError = failure === 'stale500' ? null : new DOMException('Declared JSON body cancellation', failure)
  const response = data => ({ status: 200, json: async () => ({ code: 0, data, message: 'ok' }) })
  const preview = () => ({ templateKey: 'STANDARD_8', templateLabel: '标准 8 节作息', items: desired.map(wanted => { const current = facts.find(row => row.slotNo === wanted.slotNo) || null; return { desired: wanted, status: current ? 'EXISTS' : 'READY', reason: current ? '同序号节次已存在且时间一致，无需重复创建' : '', current } }), readyCount: 8 - facts.length, existingCount: facts.length, blockedCount: 0, canConfirm: facts.length < 8, nextStep: facts.length < 8 ? '可确认应用；仅创建 READY 项，每一项仍进入 create_time_slot() 最终校验。' : '当前作息已覆盖该模板，无需重复应用。' })
  const fetch = async (url, options) => {
    const u = new URL(url, 'https://declared.invalid'), method = options.method || 'GET'
    requests.push({ path: u.pathname, method }); assert.ok(requests.length <= 8); assert.equal(u.search, ''); assert.equal(options.credentials, 'include')
    if (u.pathname === '/api/v1/auth/browser-refresh') {
      assert.equal(method, 'POST'); counts.refresh++; assert.ok(counts.refresh <= 1)
      return response({ accessToken: 'DECLARED_ROTATED_TEMPLATE_TOKEN' })
    }
    if (u.pathname === '/api/v1/academic-affairs/time-slots/template-preview') {
      assert.equal(method, 'POST'); assert.deepEqual(JSON.parse(options.body), { templateKey: 'STANDARD_8' }); assert.ok(++counts.preview <= 2)
      const value = JSON.parse(JSON.stringify(preview())); previews.push(value); return response(value)
    }
    assert.equal(u.pathname, '/api/v1/academic-affairs/time-slots')
    if (method === 'GET') { assert.ok(++counts.slots <= 2); return response({ items: list() }) }
    assert.equal(method, 'POST'); const wanted = JSON.parse(options.body); counts.writes++
    // The old incorrect auth retry may reach3. Do not make expected writes2 a
    // settle/setup requirement; the first post-settle value oracle detects it.
    assert.ok(counts.writes <= 3); assert.deepEqual(wanted, desired[counts.writes === 1 ? 6 : 7])
    if (counts.writes === 2) {
      if (failure === 'stale500') return { status: 500, json: async () => ({ code: 401001, bizCode: 'UNAUTHORIZED', message: '声明服务故障携带旧认证码', data: null, traceId: 'DECLARED_TEMPLATE_HTTP500' }) }
      return { status: 200, json: async () => { throw bodyError } }
    }
    const ack = acks[wanted.slotNo - 1]; facts.push(ack); return response(ack)
  }
  const toast = { info: message => toasts.push({ kind: 'info', message }), success: message => toasts.push({ kind: 'success', message }), error: prohibited, warning: prohibited }
  const clientSource = source('services/http/client.js').replace(/^import .*$/gm, '').replace(/\bimport\.meta\b/g, '__buildMeta').replace(/^export /gm, '')
  const client = new Function('API_BASE_URL', 'API_PREFIX', 'allowMockFallback', 'realApiEnabled', 'toast', 'normalizeUiError', 'fetch', 'sessionStorage', 'localStorage', 'BroadcastChannel', '__buildMeta', `${clientSource}\nreturn {request,setToken,isBackendOffline}`)('', '/api/v1', () => false, () => true, toast, templateOutcomeNormalize, fetch, storage, storage, undefined, { env: { DEV: false } })
  client.setToken('DECLARED_INITIAL_TEMPLATE_TOKEN')
  const observedRequest = async (...args) => { try { return await client.request(...args) } catch (error) { rawFailures.push(error); throw error } }
  const apiSource = source('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const production = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(observedRequest, prohibited, prohibited, () => true, () => claims, prohibited)
  const api = { ...production, createTimeSlot(...args) { return production.createTimeSlot(...args).then(dto => { dtos.push(structuredClone(dto)); return dto }) } }
  const convenience = source('modules/academicAffairs/api/term-calendar-convenience.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default termCalendarConvenienceApi\s*$/m, '')
  const convenienceApi = new Function('request', `${convenience}\nreturn termCalendarConvenienceApi`)(observedRequest)
  const AppInlineAlert = compile('components/common/AppInlineAlert.vue')
  const child = compile('modules/academicAffairs/components/AaTimeSlotTemplatePanel.vue', { ...visuals, AppButton, AppInlineAlert, academicAffairsApi: api, termCalendarConvenienceApi: convenienceApi, toast })
  const parent = compile('modules/academicAffairs/views/AaTimeSlotView.vue', { ...visuals, AppButton, AppInlineAlert, AaTimeSlotTemplatePanel: child, academicAffairsApi: api, toast, matchPermission, systemConfirm })
  const root = node('root'), route = reactive({ path: '/admin/academic-affairs/time-slots', fullPath: '/admin/academic-affairs/time-slots', query: {} })
  app = renderer.createApp({ render: () => h(parent, { ctx, ref: 'owner' }) }); app.provide('academicFlow', { identity: () => academicIdentity(claims, ctx), restorePosition() {} })
  app.config.globalProperties.$route = route; app.config.globalProperties.$router = { replace: prohibited, push: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = value => warnings.push(String(value)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  const until = async (predicate, label) => { for (let i = 0; i < 60; i++) { await templateOutcomeTick(); if (predicate()) return } assert.fail(label) }
  const publicClick = label => { const found = walk(root).filter(n => n.type === 'button' && text(n).trim() === label); assert.equal(found.length, 1, label); assert.equal(!!found[0].props.disabled, false); for (const fn of Array.isArray(found[0].props.onClick) ? found[0].props.onClick : [found[0].props.onClick]) fn({ type: 'click', target: found[0], currentTarget: found[0] }) }
  vm = app.mount(root).$refs.owner; await until(() => counts.slots === 1 && !vm.loading && vm.$refs.timeSlotTemplate, 'Initial complete slots read')
  assert.deepEqual(vm.rows, list())
  const start = async () => { publicClick('检查当前作息'); await until(() => counts.preview === 1 && vm.$refs.timeSlotTemplate.preview && !vm.$refs.timeSlotTemplate.loading, 'Full template preview'); assert.deepEqual(vm.$refs.timeSlotTemplate.preview, previews[0]); assert.equal(vm.$refs.timeSlotTemplate.preview.readyCount, 2); publicClick('创建 2 个缺失节次') }
  const settled = async () => { await until(() => counts.preview === 2 && counts.slots === 2 && !vm.loading && !vm.$refs.timeSlotTemplate.loading && !vm.$refs.timeSlotTemplate.applying, 'Authority GET and automatic preview complete'); assert.deepEqual(vm.rows, list()); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) }
  return { counts, requests, dtos, rawFailures, bodyError, client, list, toasts, start, settled, close, panel: () => vm.$refs.timeSlotTemplate, vm: () => vm, alertTexts: () => walk(root).filter(n => n.props.role === 'alert').map(text) }
}

test('template JSON-body AbortError and TimeoutError keep one-ACK UNKNOWN after public apply and authoritative recovery without replay', async t => {
  for (const failure of ['AbortError', 'TimeoutError']) {
    const f = await templateTransportBoundaryFixture(t, failure)
    try {
      await f.start(); await f.settled()
      assert.equal(f.counts.writes, 2); assert.equal(f.counts.refresh, 0); assert.equal(f.dtos.length, 2)
      assertTemplateUnknown(f, 1); assert.equal(f.dtos[1].bizCode, 'REQUEST_TIMEOUT')
      assert.equal(f.rawFailures.length, 1); assert.equal(f.rawFailures[0].cause, f.bodyError); assert.equal(f.rawFailures[0].transportErrorName, failure)
      assert.equal(f.client.isBackendOffline(), false); assert.equal(f.toasts.filter(value => value.kind === 'success').length, 0)
      assert.deepEqual(f.counts, { slots: 2, preview: 2, writes: 2, refresh: 0 }); assert.equal(f.vm().rows.length, 7)
      assert.equal(f.panel().preview.readyCount, 1); assert.equal(f.requests.length, 6)
    } finally { await f.close() }
  }
})

test('template HTTP500 with a stale401 code cannot refresh or replay create and preserves the first ACK through authority reads', async t => {
  const f = await templateTransportBoundaryFixture(t, 'stale500')
  try {
    await f.start(); await f.settled()
    assert.equal(f.counts.writes, 2, 'The failed second create must not be automatically sent a third time')
    assert.equal(f.counts.refresh, 0); assert.equal(f.dtos.length, 2); assert.equal(f.dtos[0].code, 0)
    assert.equal(f.dtos[1].httpStatus, 500); assert.equal(f.dtos[1].code, 401001); assert.equal(f.dtos[1].traceId, 'DECLARED_TEMPLATE_HTTP500')
    assert.equal(f.rawFailures.length, 1); assert.equal(f.rawFailures[0].httpStatus, 500)
    assert.equal(f.toasts.filter(value => value.kind === 'success').length, 0)
    assert.ok(f.alertTexts().some(message => /已成功创建 1 项/.test(message)))
    assert.deepEqual(f.counts, { slots: 2, preview: 2, writes: 2, refresh: 0 }); assert.equal(f.vm().rows.length, 7)
    assert.equal(f.panel().preview.readyCount, 1); assert.equal(f.requests.length, 6)
  } finally { await f.close() }
})
