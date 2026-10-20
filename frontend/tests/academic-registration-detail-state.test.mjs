import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { compile, createRenderer, createSSRApp, h, nextTick, reactive } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { matchPermission } from '../src/config/navPlan.js'
import { academicStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

const files = { detail: '../src/modules/academicAffairs/views/AaRegistrationDetailView.vue', bulk: '../src/modules/academicAffairs/components/AaRegistrationBulkPanel.vue' }
const sources = Object.fromEntries(Object.entries(files).map(([key, path]) => [key, readFileSync(new URL(path, import.meta.url), 'utf8')]))
const templates = Object.fromEntries(Object.entries(sources).map(([key, source]) => [key, source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]]))
const batchId = '9007199254740993001', studentId = '9007199254740993011'
const batch = status => ({ batchId, batchName: 'PRIVATE-ORIGINAL-BATCH', registerType: 'ANNUAL', status })
const list = (items = [], total = items.length) => ({ code: 0, data: { list: items, total } })
const context = () => ({ userId: 'actor-a', currentRole: { roleName: '教务测试岗' }, dataScope: { scopeName: '本校' }, permissionPatterns: ['academicAffairs.registration.view', 'academicAffairs.registration.manage'] })
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const plain = (props, { slots }) => h('section', [slots.actions?.(), slots.default?.()])
const stubs = { ModulePageShell: plain, AppSectionCard: plain, AppInlineAlert: plain, AppStatusTag: plain, AppButton: (props, { slots }) => h('button', slots.default?.()), LoadingState: () => h('p', '正在读取'), ErrorState: () => h('p', '读取失败'), EmptyState: () => h('p', '无记录'), DataTable: () => h('table') }
function options(kind, dependencies = {}) {
  const sandbox = { dependencies: { ...stubs, matchPermission, academicStatusLabel, formatDateTime, toast: { info() {}, error() {}, success() {} }, ...dependencies } }
  vm.runInNewContext(sources[kind].match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component ='), sandbox)
  return sandbox.component
}
function stateOf(component, extra = {}) {
  const state = { ...component.data(), ...component.methods, ctx: context(), $emit() {}, ...extra }
  for (const [key, get] of Object.entries(component.computed)) Object.defineProperty(state, key, { get: () => get.call(state) })
  return state
}
function detail(api = {}) {
  const calls = []
  const component = options('detail', { academicAffairsApi: { getRegistrationBatches: async query => { calls.push(query); return list([batch('OPEN')]) }, getRegistrations: async () => list(), ...api } })
  return { component, calls, state: stateOf(component, { $route: { params: { batchId }, query: {} } }) }
}
function bulk(api = {}, batchState = 'OPEN') {
  const calls = [], events = []
  const component = options('bulk', { rosterRegistrationConvenienceApi: {
    getCandidates: async () => { calls.push('read'); return list() }, previewBulkRegistration: async () => { calls.push('preview'); return { code: 0 } },
    confirmBulkRegistration: async () => { calls.push('write'); return { code: 503002, message: '响应超时' } }, ...api } })
  return { component, calls, events, state: stateOf(component, { batchId, batchState, $emit: (...args) => events.push(args) }) }
}
function ready(state) {
  state.rows = [{ studentId, realName: 'PRIVATE-STUDENT' }]; state.selectedIds = [studentId]
  state.preview = { batchId, previewToken: 'original-token', ready: 1, blocked: 0, items: [] }; state.previewSignature = state.selectionSignature; state.reviewed = true
}
async function renderBulk(mounted) {
  const data = { ...mounted.state }
  for (const key of [...Object.keys(mounted.component.methods), 'batchId', 'batchState', 'ctx', '$emit']) delete data[key]
  return renderToString(createSSRApp({ ...mounted.component, created: undefined, render: compile(templates.bulk), data: () => data },
    { batchId: mounted.state.batchId, batchState: mounted.state.batchState, ctx: mounted.state.ctx }))
}

test('detail finds the exact original batch beyond page one and retains archived status without reading a neighboring ID', async () => {
  const queries = []
  const { state } = detail({ getRegistrationBatches: async query => {
    queries.push(query); return query.page === 1 ? list([batch('OPEN'), { ...batch('OPEN'), batchId: '9007199254740993000' }].slice(1), 101) : list([batch('ARCHIVED')], 101)
  } })
  await state.load()
  assert.equal(queries.length, 2); assert.equal(queries[1].pageSize, 100)
  assert.equal(queries[0].status, undefined); assert.equal(queries[0].registerType, undefined)
  assert.equal(state.batchState, 'ARCHIVED'); assert.equal(state.batchRecord.batchId, batchId)
})

test('unknown, malformed, unavailable and missing batch reads never fall back to OPEN', async () => {
  for (const reply of [async () => ({ code: 503002 }), async () => list([batch('MYSTERY')]), async () => list([{ ...batch('OPEN'), registerType: '' }]), async () => { throw new Error('网络中断') }]) {
    const { state } = detail({ getRegistrationBatches: reply }); await state.load()
    assert.equal(state.batchState, 'UNKNOWN'); assert.ok(state.batchError)
  }
  let calls = 0
  const { state } = detail({ getRegistrationBatches: async () => { calls++; return list([{ ...batch('OPEN'), batchId: 'other' }], 900) } })
  await state.load(); assert.equal(calls, 5); assert.equal(state.batchState, 'UNKNOWN'); assert.match(state.batchError, /最多 500/)
})

test('403 from formal records clears old context and cannot be overwritten by a later OPEN batch response', async () => {
  const reply = deferred()
  const { state } = detail({ getRegistrationBatches: () => reply.promise, getRegistrations: async () => ({ code: 403002, message: '无权读取' }) })
  const pending = state.load(); await Promise.resolve(); reply.resolve(list([batch('OPEN')])); await pending
  assert.equal(state.batchState, 'UNKNOWN'); assert.equal(state.batchRecord, null); assert.equal(state.rows.length, 0)
  assert.match(state.error, /无权读取/)
})

test('old batch and identity responses cannot reopen the current detail', async () => {
  const reply = deferred(); let calls = 0
  const { state } = detail({ getRegistrationBatches: () => ++calls === 1 ? reply.promise : Promise.resolve(list([batch('CLOSED')])) })
  const pending = state.load(); state.ctx = { ...state.ctx, userId: 'actor-b' }; await state.load()
  reply.resolve(list([batch('OPEN')])); await pending
  assert.equal(state.batchState, 'CLOSED'); assert.equal(state.batchContext, state.detailContext)
  state.$route.params.batchId = 'different'; assert.equal(state.batchState, 'UNKNOWN')
})

test('UNREGISTERED is explicitly this batch record status and timestamps use the shared local formatter', () => {
  const { state } = detail()
  assert.equal(state.registrationStateLabel('UNREGISTERED'), '本批次未注册')
  assert.equal(state.registrationStateLabel('REGISTERED'), '已注册'); assert.equal(state.registrationStateLabel('PENDING_REGISTER'), '待注册')
  assert.equal(state.registrationStateLabel('UNKNOWN'), '状态待确认')
  assert.equal(state.registrationTime('2026-09-08T09:30:00Z'), formatDateTime('2026-09-08T09:30:00Z', '未提供'))
  assert.equal(state.registrationTime(null), '未提供')
})

test('UNKNOWN, DRAFT, CLOSED and ARCHIVED show no selection or preview controls and dispatch no writes', async () => {
  for (const status of ['UNKNOWN', 'DRAFT', 'CLOSED', 'ARCHIVED', 'unexpected']) {
    const mounted = bulk({}, status), { state, calls } = mounted
    ready(state); state.selectedIds = []; state.toggleStudent(studentId); state.toggleCurrentPage()
    assert.equal(state.selectedIds.length, 0)
    ready(state); await state.makePreview(); await state.apply(); await state.load()
    assert.deepEqual(calls, []); assert.equal(state.canRegister, false)
    const html = await renderBulk(mounted)
    assert.doesNotMatch(html, /type="checkbox"|预览批量注册|确认注册 1 人|PRIVATE-STUDENT/)
    assert.match(html, /查看正式注册记录|尚未开放注册|批次状态尚未核对/)
  }
})

test('changing OPEN to CLOSED invalidates an in-flight preview and never permits its confirmation', async () => {
  const response = deferred(); let writes = 0
  const mounted = bulk({ previewBulkRegistration: () => response.promise, confirmBulkRegistration: async () => { writes++; return { code: 0 } } })
  ready(mounted.state); const pending = mounted.state.makePreview()
  mounted.state.batchState = 'CLOSED'; mounted.component.watch.batchState.call(mounted.state)
  response.resolve({ code: 0, data: { batchId, previewToken: 'late', ready: 1 } }); await pending; await mounted.state.apply()
  assert.equal(mounted.state.preview, null); assert.equal(writes, 0)
})

test('an unknown command remains locked after state refresh and identity switch without showing old student data', async () => {
  const mounted = bulk(); ready(mounted.state); await mounted.state.apply()
  const original = mounted.state.unknownReceipt
  for (const status of ['UNKNOWN', 'ARCHIVED', 'OPEN']) {
    mounted.state.batchState = status; mounted.component.watch.batchState.call(mounted.state)
    assert.equal(mounted.state.unknownReceipt, original)
  }
  mounted.state.ctx = { ...mounted.state.ctx, userId: 'actor-b' }; mounted.state.resetContext()
  assert.equal(mounted.state.unknownReceipt, original); assert.equal(mounted.state.unknownReceiptCurrent, false)
  await mounted.state.apply(); assert.equal(mounted.calls.filter(value => value === 'write').length, 1)
  assert.doesNotMatch(await renderBulk(mounted), /PRIVATE-STUDENT|original-token/)
})

function vueHost() {
  const node = (type, text = '') => ({ type, text, children: [], parent: null, props: {}, value: '',
    addEventListener() {}, removeEventListener() {}, getRootNode() { return this } })
  const remove = child => { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = null }
  return { root: node('root'), renderer: createRenderer({
    createElement: type => node(type), createText: text => node('text', text), createComment: text => node('comment', text),
    setText: (el, text) => { el.text = text }, setElementText: (el, text) => { el.text = text; el.children = [] },
    parentNode: el => el.parent, nextSibling: el => el.parent?.children[el.parent.children.indexOf(el) + 1] || null,
    patchProp: (el, key, old, value) => { el.props[key] = value }, remove,
    insert: (el, parent, anchor) => { remove(el); el.parent = parent; const index = parent.children.indexOf(anchor); parent.children.splice(index < 0 ? parent.children.length : index, 0, el) }
  }) }
}
const settle = async () => { for (let i = 0; i < 8; i++) { await Promise.resolve(); await nextTick() } }

test('actual Vue recheck keeps the same Bulk instance and unknown command through UNKNOWN→ARCHIVED refresh and identity change', async () => {
  let formalState = 'OPEN', writes = 0, mounts = 0, unmounts = 0, bulkInstance
  const bulkOptions = options('bulk', { rosterRegistrationConvenienceApi: { getCandidates: async () => list(), confirmBulkRegistration: async () => { writes++; formalState = 'ARCHIVED'; return { code: 503002, message: '响应超时' } } } })
  const liveBulk = { ...bulkOptions, render: compile(templates.bulk), mounted() { mounts++; bulkInstance = this }, unmounted() { unmounts++ } }
  const detailOptions = options('detail', { AaRegistrationBulkPanel: liveBulk, academicAffairsApi: {
    getRegistrationBatches: async () => list([batch(formalState)]), getRegistrations: async () => list([{ registrationId: '7', studentId, status: 'UNREGISTERED', registerAt: null }])
  } })
  const { renderer, root } = vueHost(), ctx = reactive(context())
  const app = renderer.createApp({ ...detailOptions, render: compile(templates.detail) }, { ctx })
  app.config.globalProperties.$route = reactive({ params: { batchId }, query: {} })
  const detailInstance = app.mount(root)
  try {
    await settle(); assert.equal(detailInstance.batchState, 'OPEN'); assert.equal(mounts, 1)
    const originalInstance = bulkInstance; ready(bulkInstance); await bulkInstance.apply(); await settle()
    const originalCommand = bulkInstance.unknownReceipt
    assert.equal(writes, 1); assert.equal(detailInstance.batchState, 'ARCHIVED'); assert.ok(originalCommand)
    assert.equal(bulkInstance, originalInstance); assert.equal(mounts, 1); assert.equal(unmounts, 0)
    bulkInstance.recheckRegistration(); await settle()
    assert.equal(bulkInstance.unknownReceipt, originalCommand); assert.equal(bulkInstance, originalInstance); assert.equal(unmounts, 0)
    ctx.userId = 'actor-b'; await settle()
    assert.equal(bulkInstance.unknownReceipt, originalCommand); assert.equal(bulkInstance.unknownReceiptCurrent, false)
    assert.equal(bulkInstance, originalInstance); assert.equal(mounts, 1); assert.equal(unmounts, 0)
    await bulkInstance.apply(); assert.equal(writes, 1)
  } finally { app.unmount() }
})
