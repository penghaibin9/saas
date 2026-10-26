import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import process from 'node:process'
import { createRequire } from 'node:module'
import { normalizeUiError } from '../src/utils/presentationSafety.js'
import * as academicRouteHelpers from '../src/modules/academicAffairs/academicFlowContext.js'
import { setImmediate } from 'node:timers'
import { createHash } from 'node:crypto'

// Compiled Vue component mechanism fixtures; no HTTP, database or normal-role authorization proof.
const require = createRequire(import.meta.url)
const Vue = require('vue')
const { parse, compileTemplate } = require('@vue/compiler-sfc')
const { h, reactive, createRenderer, nextTick } = Vue
const read = relative => fs.readFileSync(process.env.AA_ROSTER_BEFORE_DIR && relative.includes('academicAffairs/') ? `${process.env.AA_ROSTER_BEFORE_DIR}/frontend/src/${relative}` : new URL(`../src/${relative}`, import.meta.url), 'utf8')
const display = name => ({ name, inheritAttrs: false, setup(_props, { slots, attrs }) { return () => h('section', attrs, slots.default?.()) } })
const visuals = Object.fromEntries(['ModulePageShell', 'AppSectionCard', 'AppSelect', 'AppConfirmDialog', 'AppImportErrorSummary', 'AppImportPreviewTable'].map(name => [name, display(name)]))
visuals.AppInlineAlert = { props: ['description'], render() { return h('aside', {}, this.description || '') } }
visuals.AppStatusTag = { props: ['label'], render() { return h('span', {}, this.label || '') } }
function compile(relative, scope = {}) {
  const { descriptor, errors } = parse(read(relative), { filename: relative }); assert.deepEqual(errors, [])
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const component = new Function(...Object.keys(scope), `${script}\nreturn component`)(...Object.values(scope))
  const rendered = compileTemplate({ source: descriptor.template.content, filename: relative, id: relative, compilerOptions: { mode: 'function' } }); assert.deepEqual(rendered.errors, [])
  component.render = new Function('Vue', rendered.code)(Vue); return component
}
const AppButton = compile('components/ui/AppButton.vue')
const AppGlobalState = compile('components/common/AppGlobalState.vue', { normalizeUiError })
const AppPagination = compile('components/common/display/AppPagination.vue')
const node = (type, text = '') => ({ type, tagName: type.toUpperCase(), text, props: {}, children: [], parent: null, listeners: {}, addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler) }, removeEventListener(name, handler) { this.listeners[name] = (this.listeners[name] || []).filter(fn => fn !== handler) } })
const renderer = createRenderer({ createElement: tag => node(tag), createText: text => node('#text', text), createComment: text => node('#comment', text), setText(n, value) { n.text = value }, setElementText(n, value) { n.text = value; n.children = [] }, parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null, patchProp(n, key, _old, value) { n.props[key] = value }, insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(n); else parent.children.splice(index, 0, n) }, remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } } })
const walk = n => [n, ...n.children.flatMap(walk)]
const text = n => n.type === '#comment' ? '' : n.text + n.children.map(text).join('')
const buttons = (root, label) => walk(root).filter(n => n.type === 'button' && text(n).trim() === label)
function dispatch(root, label) { const targets = buttons(root, label); assert.equal(targets.length, 1); const target = targets[0]; if (target.props.disabled) return false; for (const fn of Array.isArray(target.props.onClick) ? target.props.onClick : [target.props.onClick]) fn?.({ target, type: 'click' }); return true }
const taskIdentityText = root => text(root) + walk(root).filter(n => n.props?.['data-job-id']).map(n => '任务 #' + n.props['data-job-id']).join(' ' )
const tick = async () => { for (let i = 0; i < 6; i++) { await Promise.resolve(); await nextTick() } }
const ctx = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '受控教务' }, dataScope: { scopeName: '受控本校' }, permissionPatterns: ['academicAffairs.roster.import'] })
const job = (id = '3', status = 'VALIDATED') => ({ id, jobType: 'IMPORT', moduleCode: 'ACADEMIC_AFFAIRS', importType: 'ACADEMIC_ROSTER', adapterType: 'EXCEL_IMPORT_JOB', sourceFileId: '5', version: status === 'SCANNING' ? 0 : 1, status, canConfirm: status === 'VALIDATED', preview: { totalRows: 1, validRows: 1, invalidRows: 0, rows: [{ studentNo: 'LOCAL_ONLY', realName: '组件声明行', className: '组件声明班' }], errors: [] } })
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
async function fixture(t, options = {}) {
  const calls = [], errors = [], warnings = [], pending = [], delays = [], notices = [], lists = []
  const previousWindow = globalThis.window
  globalThis.window = { setTimeout(fn, ms) { delays.push(ms); queueMicrotask(fn) } }
  const api = {
    listJobs: async params => { lists.push('list'); if (options.listJobs) return options.listJobs(params); return { code: 0, data: { list: options.jobs || [job('3', 'SCANNING')], total: 1 } } },
    getImportJob(id) { calls.push(['get', id]); if (options.get) return options.get(id); return Promise.resolve({ code: 0, data: job(id) }) },
    uploadRosterImport(file) { calls.push(['upload', file]); return Promise.resolve({ code: 0, data: job() }) },
    confirmImport(id, version) { calls.push(['confirm', id, version]); return Promise.resolve({ code: 0, data: { ...job(id, 'SUCCEEDED'), result: { created: 1 } } }) }
  }
  const child = compile('modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue', { ...visuals, AppButton, academicFileExchangeApi: api })
  const parent = compile('modules/academicAffairs/views/AaRosterImportExportView.vue', { ...visuals, AppButton, AppGlobalState, AppPagination, normalizeUiError, ...academicRouteHelpers, AaAuthoritativeImportDrawer: child, academicFileExchangeApi: api, academicAffairsApi: {}, academicExchangeTypeLabel: value => value, academicStatusLabel: value => value, toast: { error() {}, success(message) { notices.push(message) }, warning(message) { notices.push(message) } }, systemPrompt: async () => null })
  const state = reactive({ ctx: ctx('A'), identity: 'identity-A' }), root = node('root')
  const app = renderer.createApp({ render: () => h(parent, { ctx: state.ctx, ref: 'parent' }) }); app.provide('academicFlow', { identity: () => state.identity })
  app.config.warnHandler = value => warnings.push(value); app.config.errorHandler = value => errors.push(value)
  const wrapper = app.mount(root); await tick(); const vm = wrapper.$refs.parent
  function walkComponent(vnode, name) { if (vnode?.component?.type?.name === name) return vnode.component.proxy; if (vnode?.component) { const found = walkComponent(vnode.component.subTree, name); if (found) return found } for (const item of Array.isArray(vnode?.children) ? vnode.children : []) { const found = walkComponent(item, name); if (found) return found } return null }
  let stopped = false
  const panel = walkComponent(vm.$.subTree, 'AaAuthoritativeImportDrawer'); assert.ok(panel)
  t.after(async () => { if (!stopped) app.unmount(); for (const value of pending) value.resolve({ code: 0, data: job() }); await tick(); globalThis.window = previousWindow; assert.deepEqual(errors, []); assert.deepEqual(warnings, []) })
  return { root, vm, panel, state, calls, delays, notices, lists, errors, warnings, pending, api, stop() { app.unmount(); stopped = true } }
}

test('owned roster import card renders an actual native continuation button', async t => {
  const f = await fixture(t)
  assert.equal(buttons(f.root, '继续处理').length, 1, 'Owned IMPORT has one native continuation action, not a missing method substitute')
})

test('native continuation connects actual parent to owned job preview and blocks reupload controls', async t => {
  const f = await fixture(t); assert.equal(dispatch(f.root, '继续处理'), true); await tick()
  assert.deepEqual(f.calls, [['get', '3']]); assert.equal(f.panel.existingJobId, '3'); assert.equal(f.panel.job.id, '3')
  assert.equal(f.panel.preview.rows[0].studentNo, 'LOCAL_ONLY'); assert.equal(f.panel.canConfirm, true); assert.equal(f.panel.busy, false)
  const input = walk(f.root).find(n => n.type === 'input' && n.props.type === 'file'); assert.equal(input.props.disabled, true)
  assert.equal(dispatch(f.root, '重新选择文件'), false); assert.equal(dispatch(f.root, '上传并预检查'), false)
  f.panel.onFile({ target: { files: [{ name: 'not-selected.xlsx' }] } }); await f.panel.upload(); f.panel.reset()
  assert.equal(f.panel.file, null); assert.equal(f.panel.job.id, '3'); assert.deepEqual(f.calls, [['get', '3']])
})

test('default new-file upload and canonical confirmation retain their original consumer behavior', async t => {
  const f = await fixture(t); dispatch(f.root, '打开批量导入'); await tick()
  assert.equal(f.panel.existingJobId, ''); assert.equal(f.panel.job, null); assert.equal(f.calls.length, 0)
  const file = { name: 'LOCAL_DECLARED.xlsx', size: 100 }; f.panel.onFile({ target: { files: [file] } }); await f.panel.upload(); await tick()
  assert.equal(f.panel.canConfirm, true); await f.panel.confirm(); await tick()
  assert.deepEqual(f.calls, [['upload', file], ['confirm', '3', 1]]); assert.equal(f.panel.job.status, 'SUCCEEDED')
  f.panel.close(); await tick(); dispatch(f.root, '打开批量导入'); await tick(); assert.equal(f.panel.job, null); assert.equal(f.panel.file, null)
})

test('processing resume preserves the original 60-attempt 1500ms polling path', async t => {
  let reads = 0
  const f = await fixture(t, { get: async id => ({ code: 0, data: job(id, ['SCANNING', 'PARSING', 'VALIDATED'][reads++]) }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.deepEqual(f.calls, [['get', '3'], ['get', '3'], ['get', '3']]); assert.deepEqual(f.delays, [1500, 1500])
  assert.equal(f.panel.job.status, 'VALIDATED'); assert.equal(f.panel.polling, false); assert.equal(f.panel.busy, false)
})

test('processing timeout remains 60 natural polls and exposes an unconfirmed job without upload', async t => {
  const f = await fixture(t, { get: async id => ({ code: 0, data: job(id, 'SCANNING') }) })
  dispatch(f.root, '继续处理'); for (let i = 0; i < 70; i++) await tick()
  assert.equal(f.calls.length, 61); assert.equal(f.delays.length, 60); assert.ok(f.delays.every(ms => ms === 1500))
  assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.busy, false); assert.match(f.panel.message, /后台安全扫描/)
})

test('only roster IMPORT cards expose continuation; wrong owned detail stays unconfirmed', async t => {
  const other = [ { ...job('4'), importType: 'PROGRAM' }, { ...job('5'), adapterType: 'OTHER' }, { ...job('6'), jobType: 'EXPORT', status: 'FAILED' } ]
  const f = await fixture(t, { jobs: [job('3', 'SCANNING'), ...other], get: async () => ({ code: 0, data: { ...job(), importType: 'PROGRAM' } }) })
  assert.equal(buttons(f.root, '继续处理').length, 1); dispatch(f.root, '继续处理'); await tick()
  assert.equal(f.panel.job, null); assert.equal(f.panel.canConfirm, false); assert.match(f.panel.message, /不一致/); assert.equal(f.panel.busy, false)
})

test('expired and failed jobs show actual server reasons and never call confirmation', async t => {
  for (const status of ['EXPIRED', 'FAILED', 'VALIDATION_FAILED']) {
    const f = await fixture(t, { get: async id => ({ code: 0, data: { ...job(id, status), errorMessage: `LOCAL_${status}`, preview: { totalRows: 1, validRows: 0, invalidRows: 1, rows: [], errors: [{ message: 'LOCAL_ERROR' }] } } }) })
    dispatch(f.root, '继续处理'); await tick(); await f.panel.confirm()
    assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.message, `LOCAL_${status}`); assert.deepEqual(f.calls, [['get', '3']]); f.stop()
  }
})

test('close and a newly selected job reject the older response without clearing current busy', async t => {
  const old = deferred(), newer = deferred()
  const f = await fixture(t, { jobs: [job('3', 'SCANNING'), job('4', 'SCANNING')], get: id => id === '3' ? old.promise : newer.promise }); f.pending.push(old, newer)
  f.vm.resumeImport(f.vm.jobs.list[0]); await tick(); assert.equal(f.panel.busy, true)
  f.panel.close(); await tick(); f.vm.resumeImport(f.vm.jobs.list[1]); await tick(); assert.equal(f.panel.existingJobId, '4'); assert.equal(f.panel.busy, true)
  old.resolve({ code: 0, data: job('3') }); await tick(); assert.equal(f.panel.job, null); assert.equal(f.panel.busy, true)
  newer.resolve({ code: 0, data: job('4') }); await tick(); assert.equal(f.panel.job.id, '4'); assert.equal(f.panel.busy, false)
})

test('actual context and identity changes invalidate resume before request settlement or confirmation', async t => {
  for (const kind of ['context', 'identity']) {
    const response = deferred(); const f = await fixture(t, { get: () => response.promise }); f.pending.push(response)
    dispatch(f.root, '继续处理'); await tick()
    if (kind === 'context') f.state.ctx = ctx('B'); else f.state.identity = 'identity-B'
    await tick(); response.resolve({ code: 0, data: job() }); await tick()
    assert.equal(f.panel.job, null); assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.busy, false); await f.panel.confirm(); assert.deepEqual(f.calls, [['get', '3']]); f.stop()
  }
})

test('unmount leaves the disposed child empty while a fresh child owns its own preview', async t => {
  const response = deferred(); const f = await fixture(t, { get: () => response.promise }); f.pending.push(response)
  dispatch(f.root, '继续处理'); await tick(); const old = f.panel; f.stop()
  const fresh = await fixture(t); dispatch(fresh.root, '继续处理'); await tick()
  response.resolve({ code: 0, data: job() }); await tick()
  assert.equal(old.job, null); assert.equal(old.resumeBusy, false); assert.equal(fresh.panel.job.id, '3'); assert.notEqual(old.$.uid, fresh.panel.$.uid)
})

test('late resumed confirmation cannot emit success or repopulate a closed drawer', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const response = deferred(); f.pending.push(response); f.api.confirmImport = (id, version) => { f.calls.push(['confirm', id, version]); return response.promise }
  const submitting = f.panel.confirm(); f.panel.close(); await tick(); dispatch(f.root, '打开批量导入'); await tick()
  response.resolve({ code: 0, data: job('3', 'SUCCEEDED') }); await submitting; await tick()
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1); assert.equal(f.panel.job, null); assert.equal(f.panel.confirmBusy, false)
})

test('resumed validated confirmation uses its actual version once and emits the server result', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const response = deferred(); f.pending.push(response); f.api.confirmImport = (id, version) => { f.calls.push(['confirm', id, version]); return response.promise }
  const first = f.panel.confirm(); await f.panel.confirm(); await tick()
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1]])
  response.resolve({ code: 0, data: { ...job('3', 'SUCCEEDED'), result: { created: 1 } } }); await first; await tick()
  assert.equal(f.panel.job.status, 'SUCCEEDED'); assert.equal(f.panel.confirmBusy, false)
  assert.deepEqual(f.notices, ['学籍导入完成：新建 1']); assert.equal(f.lists.length, 2, 'Actual parent imported listener refreshes its list once')
})

test('identity change after validated preview closes confirmation eligibility before any write', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick(); assert.equal(f.panel.canConfirm, true)
  f.state.identity = 'identity-changed'; await tick(); await f.panel.confirm()
  assert.equal(f.panel.job, null); assert.equal(f.panel.canConfirm, false); assert.deepEqual(f.calls, [['get', '3']])
})

test('an already visible import blocks changing from existing job to a new upload', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  f.vm.openNewImport(); await tick(); assert.equal(f.panel.existingJobId, '3'); assert.equal(f.panel.job.id, '3')
  assert.deepEqual(f.calls, [['get', '3']])
})

test('resume rejects missing source and invalid version before exposing confirmation', async t => {
  for (const fields of [{ sourceFileId: '' }, { sourceFileId: null }, { version: -1 }, { version: '1' }, { version: 1.5 }]) {
    const f = await fixture(t, { get: async () => ({ code: 0, data: { ...job(), ...fields } }) })
    dispatch(f.root, '继续处理'); await tick(); await f.panel.confirm()
    assert.equal(f.panel.job, null); assert.equal(f.panel.canConfirm, false); assert.match(f.panel.message, /不一致/)
    assert.deepEqual(f.calls, [['get', '3']]); f.stop()
  }
})

test('natural poll cannot replace the captured immutable source file', async t => {
  let calls = 0
  const f = await fixture(t, { get: async id => ({ code: 0, data: calls++ === 0 ? job(id, 'SCANNING') : { ...job(id), sourceFileId: 'OTHER_LOCAL_FILE' } }) })
  dispatch(f.root, '继续处理'); await tick(); await f.panel.confirm()
  assert.equal(f.panel.job.status, 'SCANNING'); assert.equal(f.panel.job.sourceFileId, '5'); assert.equal(f.panel.preview.rows[0].studentNo, 'LOCAL_ONLY')
  assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.busy, false); assert.match(f.panel.message, /不一致/)
  assert.deepEqual(f.calls, [['get', '3'], ['get', '3']])
})

test('same-owned nonterminal confirmation ACK cannot announce import completion', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  f.api.confirmImport = async (id, version) => {
    f.calls.push(['confirm', id, version])
    return { code: 0, data: { ...job(id), result: { created: 1 } } }
  }
  await f.panel.confirm(); await tick()
  assert.deepEqual(f.notices, [], 'A VALIDATED ACK is not completed import evidence')
  assert.equal(f.lists.length, 1, 'Unconfirmed ACK must not emit imported to the real parent')
  assert.equal(f.panel.messageType, 'danger')
  assert.equal(f.panel.confirmBusy, false)
  assert.equal(f.panel.job.id, '3')
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']], 'Only existing query recovery, never automatic reconfirmation')
})

for (const status of ['CONFIRMING', 'SCANNING', 'FAILED', 'EXPIRED']) {
  test(`confirmation ACK ${status} preserves owned query recovery without a completion event`, async t => {
    const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
    f.api.confirmImport = async (id, version) => {
      f.calls.push(['confirm', id, version])
      return { code: 0, data: { ...job(id, status), result: { created: 1 } } }
    }
    await f.panel.confirm(); await tick()
    assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
    assert.equal(f.panel.job.status, 'VALIDATED'); assert.equal(f.panel.confirmBusy, false)
    assert.equal(f.panel.messageType, 'danger'); assert.match(f.panel.message, /尚未确认/)
    assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
  })
}

const invalidCompletionResults = [
  ['missing', undefined], ['null', null], ['array', []], ['empty', {}],
  ['unrecognized', { details: [] }], ['string count', { created: '1' }],
  ['negative count', { created: -1 }], ['fractional count', { created: 0.5 }],
  ['boolean count', { created: true }], ['null count', { created: null }],
  ['invalid additional recognized count', { created: 1, reused: '0' }],
  ['inherited recognized count', Object.create({ created: 1 })]
]
for (const [label, result] of invalidCompletionResults) {
  test(`SUCCEEDED ${label} result cannot report roster completion`, async t => {
    const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
    const original = f.panel.job
    let duringRecovery
    f.api.confirmImport = async (id, version) => {
      f.calls.push(['confirm', id, version])
      return { code: 0, data: { ...job(id, 'SUCCEEDED'), result } }
    }
    f.api.getImportJob = async id => {
      f.calls.push(['get', id]); duringRecovery = f.panel.job
      return { code: 0, data: job(id) }
    }
    await f.panel.confirm(); await tick()
    assert.equal(duringRecovery, original, 'Malformed ACK must not hydrate the panel before recovery')
    assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
    assert.equal(f.panel.job.status, 'VALIDATED'); assert.equal(f.panel.confirmBusy, false)
    assert.equal(f.panel.messageType, 'danger'); assert.match(f.panel.message, /尚未确认/)
    assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
  })
}

test('real roster result categories and thin zero counts remain completed without requiring all fields', async t => {
  for (const result of [
    { created: 1, reused: 0, filled: 0, skipped: 0, identityConflict: 0, orgConflict: 0, voidedConflict: 0, failed: 0 },
    { created: 0 }, { reused: 1 }, { failed: 1 }
  ]) {
    const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
    const ack = { ...job('3', 'SUCCEEDED'), version: 4, result }
    delete ack.preview; delete ack.canConfirm
    f.api.confirmImport = async (id, version) => { f.calls.push(['confirm', id, version]); return { code: 0, data: ack } }
    await f.panel.confirm(); await tick()
    assert.equal(f.panel.job.status, 'SUCCEEDED'); assert.deepEqual(f.panel.job.result, result)
    assert.equal(f.panel.messageType, 'success'); assert.equal(f.panel.confirmBusy, false)
    assert.equal(f.notices.length, 1); assert.equal(f.lists.length, 2)
    assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1]])
    f.stop()
  }
})

test('a valid completion shape still cannot replace the resumed source file or job identity', async t => {
  for (const fields of [{ id: 'OTHER_JOB' }, { sourceFileId: 'OTHER_FILE' }, { version: '4' }]) {
    const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
    f.api.confirmImport = async (id, version) => {
      f.calls.push(['confirm', id, version])
      return { code: 0, data: { ...job(id, 'SUCCEEDED'), result: { created: 1 }, ...fields } }
    }
    await f.panel.confirm(); await tick()
    assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
    assert.equal(f.panel.job.id, '3'); assert.equal(f.panel.job.sourceFileId, '5')
    assert.equal(f.panel.messageType, 'danger'); assert.equal(f.panel.confirmBusy, false)
    assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
    f.stop()
  }
})

test('generic new-upload confirmation accepts its own non-roster result without roster count policy', async t => {
  const emitted = [], calls = [], errors = [], warnings = []
  const ack = { ...job('LOCAL_GRADE', 'SUCCEEDED'), importType: 'ACADEMIC_GRADE', result: { updated: 1 } }
  delete ack.preview; delete ack.canConfirm
  const api = { confirmImport: async (id, version) => { calls.push([id, version]); return { code: 0, data: ack } } }
  const child = compile('modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue', { ...visuals, AppButton, academicFileExchangeApi: api })
  const root = node('root')
  const app = renderer.createApp(child, { visible: true, downloadTemplateFn: async () => null,
    uploadFn: async () => null, onImported: value => emitted.push(value) })
  app.config.warnHandler = value => warnings.push(value); app.config.errorHandler = value => errors.push(value)
  const panel = app.mount(root)
  t.after(() => { app.unmount(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) })
  panel.syncJob({ ...job('LOCAL_GRADE'), importType: 'ACADEMIC_GRADE' })
  await panel.confirm(); await tick()
  assert.deepEqual(calls, [['LOCAL_GRADE', 1]]); assert.deepEqual(emitted, [ack])
  assert.equal(panel.messageType, 'success'); assert.equal(panel.job.status, 'SUCCEEDED')
})

test('native completed-job resume explains completion without requesting another confirmation', async t => {
  const f = await fixture(t, { get: async id => ({ code: 0, data: { ...job(id, 'SUCCEEDED'), result: { created: 1 } } }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.match(f.panel.message, /已完成/, 'Completed history must not use the generic unconfirmed-task message')
  assert.match(f.panel.message, /无需再次确认/)
  assert.doesNotMatch(f.panel.message, /不可确认/)
  assert.equal(f.panel.job.status, 'SUCCEEDED'); assert.equal(f.panel.canConfirm, false)
  assert.equal(f.panel.messageType, 'info', 'Completion must preserve the existing tone; it does not prove every row succeeded')
  assert.equal(f.panel.busy, false); assert.deepEqual(f.calls, [['get', '3']])
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
})

test('completed resume preserves warning for failed-row evidence without claiming every row succeeded', async t => {
  // Component-state evidence only; this does not execute a native partial import.
  const f = await fixture(t, { get: async id => ({ code: 0, data: {
    ...job(id, 'SUCCEEDED'), result: { created: 1, failed: 1 },
    preview: { totalRows: 2, validRows: 1, invalidRows: 1, rows: [], errors: [{ message: 'LOCAL_FAILED_ROW' }] }
  } }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.match(f.panel.message, /已完成/); assert.match(f.panel.message, /无需再次确认/)
  assert.equal(f.panel.messageType, 'warning', 'Completion must not overwrite the original failed-row warning')
  assert.equal(f.panel.preview.invalidRows, 1); assert.equal(f.panel.job.result.failed, 1)
  assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.busy, false)
  assert.deepEqual(f.calls, [['get', '3']]); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
})

test('owned completed resume preserves the explicit server warning instead of a completion-only message', async t => {
  const warning = ' 服务端核对警示\n请保留原始说明 '
  const f = await fixture(t, { get: async id => ({ code: 0, data: {
    ...job(id, 'SUCCEEDED'), result: { created: 1, failed: 1 }, errorMessage: warning
  } }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.equal(f.panel.message, warning, 'An explicit server warning must survive completed history verbatim')
  assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.busy, false)
  assert.deepEqual(f.calls, [['get', '3']]); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
})

test('owned completed resume cannot hydrate a malformed result or announce verified completion', async t => {
  const f = await fixture(t, { get: async id => ({ code: 0, data: {
    ...job(id, 'SUCCEEDED'), result: {}
  } }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.equal(f.panel.job, null, 'Invalid completion evidence must not be adopted by the real resumed drawer')
  assert.equal(f.panel.messageType, 'danger'); assert.match(f.panel.message, /尚未确认/)
  assert.doesNotMatch(f.panel.message, /已完成/); assert.equal(f.panel.canConfirm, false)
  assert.equal(f.panel.busy, false); assert.equal(f.panel.resumeOwner.sourceFileId, undefined)
  assert.deepEqual(f.calls, [['get', '3']]); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
})

for (const [label, result] of [['missing', undefined], ['null', null], ['bad count', { created: '1' }]]) {
  test(`completed resume rejects ${label} result before adopting the source file`, async t => {
    const f = await fixture(t, { get: async id => ({ code: 0, data: { ...job(id, 'SUCCEEDED'), result } }) })
    dispatch(f.root, '继续处理'); await tick()
    assert.equal(f.panel.job, null); assert.equal(f.panel.resumeOwner.sourceFileId, undefined)
    assert.equal(f.panel.messageType, 'danger'); assert.match(f.panel.message, /尚未确认/)
    assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.busy, false)
    assert.deepEqual(f.calls, [['get', '3']]); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
  })
}

test('malformed completed result retains the server warning as well as completion uncertainty', async t => {
  const warning = ' 需人工核对原始任务\n服务端警示不可丢失 '
  const f = await fixture(t, { get: async id => ({ code: 0, data: {
    ...job(id, 'SUCCEEDED'), result: {}, errorMessage: warning
  } }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.ok(f.panel.message.startsWith(warning), 'The full explicit warning remains the first information shown')
  assert.match(f.panel.message, /统计尚未确认/)
  assert.equal(f.panel.messageType, 'danger'); assert.equal(f.panel.job, null)
  assert.equal(f.panel.resumeOwner.sourceFileId, undefined); assert.equal(f.panel.canConfirm, false)
  assert.deepEqual(f.calls, [['get', '3']]); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
})

test('completed resume accepts the full real result categories without a confirmation event', async t => {
  const result = { created: 1, reused: 0, filled: 0, skipped: 0, identityConflict: 0, orgConflict: 0, voidedConflict: 0, failed: 0 }
  const f = await fixture(t, { get: async id => ({ code: 0, data: { ...job(id, 'SUCCEEDED'), version: 4, result } }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.equal(f.panel.job.status, 'SUCCEEDED'); assert.equal(f.panel.job.version, 4)
  assert.deepEqual(f.panel.job.result, result); assert.equal(f.panel.resumeOwner.sourceFileId, '5')
  assert.match(f.panel.message, /已完成/); assert.equal(f.panel.messageType, 'info')
  assert.equal(f.panel.canConfirm, false); assert.deepEqual(f.calls, [['get', '3']])
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
})

test('generic completed resume retains its own updated result without applying roster count policy', async t => {
  const calls = [], emitted = [], errors = [], warnings = []
  const item = { ...job('LOCAL_GENERIC', 'SUCCEEDED'), importType: 'ACADEMIC_GRADE', result: { updated: 1 } }
  const api = { getImportJob: async id => { calls.push(['get', id]); return { code: 0, data: item } } }
  const child = compile('modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue', { ...visuals, AppButton, academicFileExchangeApi: api })
  const root = node('root')
  const app = renderer.createApp(child, { visible: true, existingJobId: 'LOCAL_GENERIC', downloadTemplateFn: async () => null,
    uploadFn: async () => null, onImported: value => emitted.push(value) })
  app.config.warnHandler = value => warnings.push(value); app.config.errorHandler = value => errors.push(value)
  const panel = app.mount(root)
  t.after(() => { app.unmount(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) })
  await tick()
  assert.equal(panel.job.status, 'SUCCEEDED'); assert.deepEqual(panel.job.result, { updated: 1 })
  assert.match(panel.message, /已完成/); assert.equal(panel.messageType, 'info')
  assert.equal(panel.canConfirm, false); assert.equal(panel.resumeOwner.sourceFileId, '5')
  assert.deepEqual(calls, [['get', 'LOCAL_GENERIC']]); assert.deepEqual(emitted, [])
})

test('confirmation recovery contains malformed completed evidence and retains both observed errors', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const original = f.panel.job
  const warning = ' 恢复查询原始警示\n不得丢失 '
  f.api.confirmImport = async (id, version) => {
    f.calls.push(['confirm', id, version])
    return { code: 0, data: { ...job(id), result: { created: 1 } } }
  }
  f.api.getImportJob = async id => {
    f.calls.push(['get', id])
    return { code: 0, data: { ...job(id, 'SUCCEEDED'), result: {}, errorMessage: warning } }
  }
  await assert.doesNotReject(f.panel.confirm(), 'A sole recovery read must display its failure rather than reject the confirmation promise')
  await tick()
  assert.equal(f.panel.job, original, 'Malformed recovery must not adopt a new job')
  assert.match(f.panel.message, /完成结果尚未确认/)
  assert.ok(f.panel.message.includes(warning), 'Keep the full server warning from the recovery response')
  assert.match(f.panel.message, /完成统计尚未确认/)
  assert.equal(f.panel.messageType, 'danger'); assert.equal(f.panel.confirmBusy, false)
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
})

test('a rejected recovery read preserves the initial confirmation error and clears busy without retry', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const original = f.panel.job
  const originalError = ' 原确认失败\n尚未得到完成回执 '
  const recoveryError = ' 原查询连接中断\n请核对原任务 '
  f.api.confirmImport = async (id, version) => {
    f.calls.push(['confirm', id, version]); throw new Error(originalError)
  }
  f.api.getImportJob = async id => { f.calls.push(['get', id]); throw new Error(recoveryError) }
  await assert.doesNotReject(f.panel.confirm()); await tick()
  assert.equal(f.panel.message, `${originalError}\n${recoveryError}`)
  assert.equal(f.panel.job, original); assert.equal(f.panel.messageType, 'danger')
  assert.equal(f.panel.confirmBusy, false); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
})

test('valid recovery keeps the initial failure and the complete server warning without announcing completion', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const originalError = '确认未能取得有效回执'
  const warning = ' 原任务服务端警示\n必须完整保留 '
  f.api.confirmImport = async (id, version) => {
    f.calls.push(['confirm', id, version]); throw new Error(originalError)
  }
  f.api.getImportJob = async id => {
    f.calls.push(['get', id]); return { code: 0, data: { ...job(id, 'SUCCEEDED'), result: { created: 1 }, errorMessage: warning } }
  }
  await assert.doesNotReject(f.panel.confirm()); await tick()
  assert.equal(f.panel.message, `${originalError}\n${warning}`)
  assert.equal(f.panel.job.status, 'SUCCEEDED'); assert.equal(f.panel.canConfirm, false)
  assert.equal(f.panel.messageType, 'danger'); assert.equal(f.panel.confirmBusy, false)
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
})

for (const settlement of ['reject', 'malformed']) {
  test(`late ${settlement} recovery after close cannot repopulate the closed drawer`, async t => {
    const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
    const recovery = deferred()
    f.api.confirmImport = async (id, version) => {
      f.calls.push(['confirm', id, version]); throw new Error('受控原确认失败')
    }
    f.api.getImportJob = id => { f.calls.push(['get', id]); return recovery.promise }
    const confirming = f.panel.confirm(); await tick()
    assert.equal(f.panel.confirmBusy, true)
    f.panel.close(); await tick()
    const currentMessage = f.panel.message, currentType = f.panel.messageType, currentJob = f.panel.job
    if (settlement === 'reject') recovery.reject(new Error('受控迟到查询失败'))
    else recovery.resolve({ code: 0, data: { ...job('3', 'SUCCEEDED'), result: {}, errorMessage: '迟到警示' } })
    await assert.doesNotReject(confirming); await tick()
    assert.equal(f.panel.message, currentMessage); assert.equal(f.panel.messageType, currentType)
    assert.equal(f.panel.job, currentJob); assert.equal(f.panel.job.status, 'VALIDATED'); assert.equal(f.panel.resumeOwner, null)
    assert.equal(f.panel.confirmBusy, false); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
    assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
  })
}


test('a malformed completed natural poll reaches the existing resume catch without adopting completion', async t => {
  let reads = 0
  const warning = '自然查询的原始警示'
  const f = await fixture(t, { get: async id => ({ code: 0, data: reads++ === 0
    ? job(id, 'SCANNING') : { ...job(id, 'SUCCEEDED'), result: {}, errorMessage: warning } }) })
  dispatch(f.root, '继续处理'); await tick()
  assert.equal(f.panel.job.status, 'SCANNING'); assert.equal(f.panel.job.sourceFileId, '5')
  assert.equal(f.panel.messageType, 'danger'); assert.ok(f.panel.message.includes(warning))
  assert.match(f.panel.message, /完成统计尚未确认/)
  assert.equal(f.panel.busy, false); assert.equal(f.panel.polling, false); assert.equal(f.panel.canConfirm, false)
  assert.deepEqual(f.calls, [['get', '3'], ['get', '3']]); assert.deepEqual(f.delays, [1500])
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
})


test('a failed recovery response retains its actual message with the initial error without another read', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const original = f.panel.job
  const firstMessage = '确认回执暂未得到核对'
  const recoveryMessage = ' 实际恢复查询拒绝原因\n保持原文 '
  f.api.confirmImport = async (id, version) => {
    f.calls.push(['confirm', id, version]); return { code: 8, message: firstMessage }
  }
  f.api.getImportJob = async id => {
    f.calls.push(['get', id]); return { code: 9, message: recoveryMessage }
  }
  await assert.doesNotReject(f.panel.confirm()); await tick()
  assert.equal(f.panel.message, `${firstMessage}\n${recoveryMessage}`)
  assert.equal(f.panel.job, original); assert.equal(f.panel.messageType, 'danger'); assert.equal(f.panel.confirmBusy, false)
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
})

test('a valid completed ACK preserves its explicit warning while still emitting actual terminal evidence once', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const warning = ' 原完成回执警示\n不要覆盖 '
  const ack = { ...job('3', 'SUCCEEDED'), version: 4, result: { created: 1, failed: 1 }, errorMessage: warning }
  delete ack.preview; delete ack.canConfirm
  f.api.confirmImport = async (id, version) => {
    f.calls.push(['confirm', id, version]); return { code: 0, data: ack }
  }
  await assert.doesNotReject(f.panel.confirm()); await tick()
  assert.equal(f.panel.message, warning)
  assert.equal(f.panel.job.status, 'SUCCEEDED'); assert.deepEqual(f.panel.job.result, ack.result)
  assert.equal(f.panel.messageType, 'success', 'Preserve the existing ACK tone without changing terminal/result acceptance')
  assert.equal(f.panel.canConfirm, false); assert.equal(f.panel.confirmBusy, false)
  assert.equal(f.notices.length, 1); assert.equal(f.lists.length, 2)
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1]])
})


test('a malformed ACK retains its own raw warning before the sole malformed recovery warning', async t => {
  const f = await fixture(t); dispatch(f.root, '继续处理'); await tick()
  const original = f.panel.job
  const ackWarning = ' 原确认回执警示\n保持完整 '
  const recoveryWarning = ' 原恢复回执警示\n仍须保留 '
  f.api.confirmImport = async (id, version) => {
    f.calls.push(['confirm', id, version])
    return { code: 0, data: { ...job(id, 'SUCCEEDED'), result: {}, errorMessage: ackWarning } }
  }
  f.api.getImportJob = async id => {
    f.calls.push(['get', id])
    return { code: 0, data: { ...job(id, 'SUCCEEDED'), result: {}, errorMessage: recoveryWarning } }
  }
  await assert.doesNotReject(f.panel.confirm()); await tick()
  assert.ok(f.panel.message.startsWith(ackWarning), 'Keep the actual ACK warning before its shape error')
  assert.ok(f.panel.message.includes(recoveryWarning), 'Also preserve the actual sole-recovery warning')
  assert.match(f.panel.message, /完成统计尚未确认/)
  assert.equal(f.panel.message.split(ackWarning).length, 2); assert.equal(f.panel.message.split(recoveryWarning).length, 2)
  assert.equal(f.panel.job, original); assert.equal(f.panel.messageType, 'danger'); assert.equal(f.panel.confirmBusy, false)
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
  assert.deepEqual(f.calls, [['get', '3'], ['confirm', '3', 1], ['get', '3']])
})

// Fresh-upload lifecycle follows the same real SFC renderer. Declared API collaborators only.
const freshFile = name => ({ name, size: 100 })
const beginFresh = async (f, file) => {
  assert.equal(dispatch(f.root, '打开批量导入'), true)
  await tick()
  assert.equal(!f.panel.existingJobId, true)
  f.panel.onFile({ target: { files: [file] } })
}
const reopenFresh = async f => {
  f.panel.close(); await tick()
  assert.equal(f.vm.importVisible, false)
  assert.equal(dispatch(f.root, '打开批量导入'), true); await tick()
  assert.equal(f.vm.importVisible, true); assert.equal(f.panel.job, null)
}
const freshJob = (id, status = 'VALIDATED') => ({ ...job(id, status), sourceFileId: `FILE_${id}` })

test('a late fresh upload cannot populate the separately reopened empty drawer', async t => {
  const f = await fixture(t), pendingUpload = deferred(), file = freshFile('DECLARED_NO_TRANSPORT.xlsx')
  f.pending.push(pendingUpload)
  f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return pendingUpload.promise }
  await beginFresh(f, file)
  const uploading = f.panel.upload(); await tick()
  const epoch = f.panel.resumeEpoch
  await reopenFresh(f); assert.ok(f.panel.resumeEpoch > epoch)
  const reopenedEpoch = f.panel.resumeEpoch, message = f.panel.message
  pendingUpload.resolve({ code: 0, data: freshJob('DECLARED_OLD_UPLOAD') })
  await uploading; await tick()
  assert.equal(f.panel.job, null, 'The prior upload must not populate a separately reopened empty drawer')
  assert.equal(f.panel.file, null); assert.equal(f.panel.message, message)
  assert.equal(f.panel.resumeEpoch, reopenedEpoch); assert.equal(f.panel.canConfirm, false)
  assert.equal(f.panel.uploadBusy, false)
  assert.deepEqual(f.calls, [['upload', file]]); assert.deepEqual(f.notices, [])
})

for (const settlement of ['resolve', 'reject']) {
  test(`the older fresh upload ${settlement} cannot clear a new pending upload`, async t => {
    const f = await fixture(t), first = deferred(), second = deferred()
    f.pending.push(first, second)
    const fileA = freshFile('DECLARED_A.xlsx'), fileB = freshFile('DECLARED_B.xlsx')
    f.api.uploadRosterImport = file => { f.calls.push(['upload', file]); return file.name === fileA.name ? first.promise : second.promise }
    await beginFresh(f, fileA); const uploadingA = f.panel.upload(); await tick()
    await reopenFresh(f); f.panel.onFile({ target: { files: [fileB] } })
    const uploadingB = f.panel.upload(); await tick(); assert.equal(f.panel.uploadBusy, true)
    const currentEpoch = f.panel.resumeEpoch, currentMessage = f.panel.message
    if (settlement === 'resolve') first.resolve({ code: 0, data: freshJob('OLD_A') })
    else first.reject(new Error('声明旧上传错误，不应写入新抽屉'))
    await uploadingA; await tick()
    assert.equal(f.panel.uploadBusy, true, 'Old finally must not clear the new operation busy flag')
    assert.equal(f.panel.job, null); assert.equal(f.panel.file.name, fileB.name)
    assert.equal(f.panel.message, currentMessage); assert.equal(f.panel.resumeEpoch, currentEpoch)
    second.resolve({ code: 0, data: freshJob('CURRENT_B') }); await uploadingB; await tick()
    assert.equal(f.panel.job.id, 'CURRENT_B'); assert.equal(f.panel.canConfirm, true)
    assert.equal(f.panel.uploadBusy, false)
    assert.deepEqual(f.calls, [['upload', fileA], ['upload', fileB]])
  })
}

for (const invalidation of ['context', 'identity', 'unmount']) {
  test(`fresh upload settlement after ${invalidation} cannot adopt an old job`, async t => {
    const f = await fixture(t), upload = deferred(), file = freshFile('DECLARED_SCOPE.xlsx')
    f.pending.push(upload)
    f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return upload.promise }
    await beginFresh(f, file); const uploading = f.panel.upload(); await tick()
    if (invalidation === 'context') f.state.ctx = ctx('B')
    else if (invalidation === 'identity') f.state.identity = 'identity-B'
    else f.stop()
    await tick()
    const jobBefore = f.panel.job, messageBefore = f.panel.message, epochBefore = f.panel.resumeEpoch
    upload.resolve({ code: 0, data: freshJob('OLD_SCOPE') }); await uploading; await tick()
    assert.equal(f.panel.job, jobBefore); assert.equal(f.panel.message, messageBefore)
    assert.equal(f.panel.resumeEpoch, epochBefore); assert.equal(f.panel.uploadBusy, false)
    assert.deepEqual(f.calls, [['upload', file]]); assert.deepEqual(f.notices, [])
  })
}

test('closing a fresh natural poll during its sleep prevents the next job GET', async t => {
  const f = await fixture(t), file = freshFile('DECLARED_SLEEP.xlsx'), sleeps = []
  window.setTimeout = (fn, ms) => { f.delays.push(ms); sleeps.push(fn) }
  f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return Promise.resolve({ code: 0, data: freshJob('SCANNING_A', 'SCANNING') }) }
  await beginFresh(f, file); const uploading = f.panel.upload(); await tick()
  assert.equal(sleeps.length, 1); assert.deepEqual(f.delays, [1500]); assert.equal(f.panel.polling, true)
  await reopenFresh(f); const currentEpoch = f.panel.resumeEpoch
  sleeps.shift()(); await uploading; await tick()
  assert.equal(f.panel.job, null); assert.equal(f.panel.message, '')
  assert.equal(f.panel.resumeEpoch, currentEpoch); assert.equal(f.panel.polling, false)
  assert.equal(f.panel.uploadBusy, false); assert.deepEqual(f.calls, [['upload', file]])
})

test('an older fresh poll response cannot replace the new upload or clear its busy flag', async t => {
  const f = await fixture(t), query = deferred(), newUpload = deferred()
  f.pending.push(query, newUpload)
  const fileA = freshFile('DECLARED_POLL_A.xlsx'), fileB = freshFile('DECLARED_POLL_B.xlsx')
  f.api.uploadRosterImport = file => { f.calls.push(['upload', file]); return file.name === fileA.name ? Promise.resolve({ code: 0, data: freshJob('POLL_A', 'SCANNING') }) : newUpload.promise }
  f.api.getImportJob = id => { f.calls.push(['get', id]); return query.promise }
  await beginFresh(f, fileA); const oldUploading = f.panel.upload(); await tick()
  assert.deepEqual(f.calls, [['upload', fileA], ['get', 'POLL_A']])
  await reopenFresh(f); f.panel.onFile({ target: { files: [fileB] } })
  const currentUploading = f.panel.upload(); await tick()
  query.resolve({ code: 0, data: freshJob('POLL_A') }); await oldUploading; await tick()
  assert.equal(f.panel.job, null); assert.equal(f.panel.uploadBusy, true)
  assert.equal(f.panel.message, ''); assert.equal(f.panel.polling, false)
  newUpload.resolve({ code: 0, data: freshJob('CURRENT_POLL_B') }); await currentUploading; await tick()
  assert.equal(f.panel.job.id, 'CURRENT_POLL_B'); assert.equal(f.panel.uploadBusy, false)
  assert.deepEqual(f.calls, [['upload', fileA], ['get', 'POLL_A'], ['upload', fileB]])
})

for (const settlement of ['resolve', 'reject']) {
  test(`late fresh confirmation ${settlement} after reopening cannot emit or query recovery`, async t => {
    const f = await fixture(t), confirming = deferred(), file = freshFile('DECLARED_CONFIRM.xlsx')
    f.pending.push(confirming)
    f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return Promise.resolve({ code: 0, data: freshJob('CONFIRM_A') }) }
    f.api.confirmImport = (id, version) => { f.calls.push(['confirm', id, version]); return confirming.promise }
    await beginFresh(f, file); await f.panel.upload(); await tick()
    const oldConfirm = f.panel.confirm(); await tick(); assert.equal(f.panel.confirmBusy, true)
    await reopenFresh(f)
    if (settlement === 'resolve') confirming.resolve({ code: 0, data: { ...freshJob('CONFIRM_A', 'SUCCEEDED'), result: { created: 1 } } })
    else confirming.reject(new Error('声明旧确认失败'))
    await assert.doesNotReject(oldConfirm); await tick()
    assert.equal(f.panel.job, null); assert.equal(f.panel.message, '')
    assert.equal(f.panel.confirmBusy, false); assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
    assert.deepEqual(f.calls, [['upload', file], ['confirm', 'CONFIRM_A', 1]])
  })
}

for (const settlement of ['resolve', 'reject']) {
  test(`late fresh recovery ${settlement} cannot overwrite another current confirmation`, async t => {
    const f = await fixture(t), recovery = deferred(), newConfirm = deferred()
    f.pending.push(recovery, newConfirm)
    const fileA = freshFile('DECLARED_RECOVERY_A.xlsx'), fileB = freshFile('DECLARED_RECOVERY_B.xlsx')
    f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return Promise.resolve({ code: 0, data: freshJob(value.name === fileA.name ? 'RECOVERY_A' : 'RECOVERY_B') }) }
    f.api.confirmImport = (id, version) => { f.calls.push(['confirm', id, version]); return id === 'RECOVERY_A' ? Promise.reject(new Error('声明首次确认失败')) : newConfirm.promise }
    f.api.getImportJob = id => { f.calls.push(['get', id]); return recovery.promise }
    await beginFresh(f, fileA); await f.panel.upload(); await tick()
    const oldConfirm = f.panel.confirm(); await tick()
    assert.deepEqual(f.calls, [['upload', fileA], ['confirm', 'RECOVERY_A', 1], ['get', 'RECOVERY_A']])
    await reopenFresh(f); f.panel.onFile({ target: { files: [fileB] } })
    await f.panel.upload(); await tick(); const currentConfirm = f.panel.confirm(); await tick()
    assert.equal(f.panel.confirmBusy, true); const currentJob = f.panel.job, currentMessage = f.panel.message
    if (settlement === 'resolve') recovery.resolve({ code: 0, data: { ...freshJob('RECOVERY_A', 'SUCCEEDED'), result: { created: 1 }, errorMessage: '声明迟到恢复提示' } })
    else recovery.reject(new Error('声明迟到恢复失败'))
    await assert.doesNotReject(oldConfirm); await tick()
    assert.equal(f.panel.job, currentJob); assert.equal(f.panel.job.id, 'RECOVERY_B')
    assert.equal(f.panel.message, currentMessage); assert.equal(f.panel.confirmBusy, true)
    assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
    newConfirm.resolve({ code: 0, data: { ...freshJob('RECOVERY_B', 'SUCCEEDED'), result: { created: 1 } } }); await currentConfirm; await tick()
    assert.equal(f.panel.confirmBusy, false); assert.equal(f.panel.job.status, 'SUCCEEDED')
    assert.equal(f.notices.length, 1); assert.equal(f.lists.length, 2)
    assert.deepEqual(f.calls, [['upload', fileA], ['confirm', 'RECOVERY_A', 1], ['get', 'RECOVERY_A'], ['upload', fileB], ['confirm', 'RECOVERY_B', 1]])
  })
}

test('fresh confirmation context invalidation stops recovery before another GET', async t => {
  const f = await fixture(t), confirm = deferred(), file = freshFile('DECLARED_CONTEXT_CONFIRM.xlsx')
  f.pending.push(confirm)
  f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return Promise.resolve({ code: 0, data: freshJob('OLD_CONTEXT_CONFIRM') }) }
  f.api.confirmImport = (id, version) => { f.calls.push(['confirm', id, version]); return confirm.promise }
  await beginFresh(f, file); await f.panel.upload(); await tick()
  const confirming = f.panel.confirm(); await tick(); f.state.ctx = ctx('B'); await tick()
  const message = f.panel.message
  confirm.reject(new Error('声明旧上下文确认失败')); await assert.doesNotReject(confirming); await tick()
  assert.equal(f.panel.job, null); assert.equal(f.panel.message, message); assert.equal(f.panel.confirmBusy, false)
  assert.deepEqual(f.notices, []); assert.deepEqual(f.calls, [['upload', file], ['confirm', 'OLD_CONTEXT_CONFIRM', 1]])
})

for (const settlement of ['resolve', 'reject']) {
  test(`old fresh upload ${settlement} cannot contaminate the newly resumed owned task`, async t => {
    const f = await fixture(t), oldUpload = deferred(), resumedRead = deferred()
    f.pending.push(oldUpload, resumedRead)
    const file = freshFile('DECLARED_SWITCH_TO_OWNED_TASK.xlsx')
    f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return oldUpload.promise }
    f.api.getImportJob = id => { f.calls.push(['get', id]); return resumedRead.promise }
    await beginFresh(f, file); const uploading = f.panel.upload(); await tick()
    f.panel.close(); await tick(); assert.equal(f.vm.importVisible, false)
    f.vm.resumeImport(f.vm.jobs.list[0]); await tick()
    assert.equal(f.vm.importVisible, true); assert.equal(f.panel.existingJobId, '3')
    assert.equal(f.panel.resumeBusy, true); assert.equal(f.panel.canConfirm, false)
    const current = { job: f.panel.job, preview: f.panel.preview, message: f.panel.message,
      type: f.panel.messageType, owner: f.panel.resumeOwner, epoch: f.panel.resumeEpoch }
    if (settlement === 'resolve') oldUpload.resolve({ code: 0, data: freshJob('OLD_BEFORE_OWNED_TASK') })
    else oldUpload.reject(new Error('声明切任务前的旧上传错误'))
    await assert.doesNotReject(uploading); await tick()
    assert.equal(f.panel.job, current.job); assert.equal(f.panel.preview, current.preview)
    assert.equal(f.panel.message, current.message); assert.equal(f.panel.messageType, current.type)
    assert.equal(f.panel.resumeOwner, current.owner); assert.equal(f.panel.resumeEpoch, current.epoch)
    assert.equal(f.panel.resumeBusy, true); assert.equal(f.panel.canConfirm, false)
    assert.equal(f.panel.uploadBusy, false); assert.deepEqual(f.notices, [])
    assert.deepEqual(f.calls, [['upload', file], ['get', '3']])
    resumedRead.resolve({ code: 0, data: job('3') }); await tick()
    assert.equal(f.panel.job.id, '3'); assert.equal(f.panel.job.sourceFileId, '5')
    assert.equal(f.panel.preview.rows[0].studentNo, 'LOCAL_ONLY')
    assert.equal(f.panel.canConfirm, true); assert.equal(f.panel.resumeBusy, false)
    assert.deepEqual(f.calls, [['upload', file], ['get', '3']])
  })
}

test('a current fresh confirmation failure recovers the same task and preserves its file and error', async t => {
  const f = await fixture(t), file = freshFile('DECLARED_HEALTHY_RECOVERY.xlsx')
  const source = freshJob('CURRENT_FRESH_RECOVERY'), warning = '声明当前服务器恢复提示'
  f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return Promise.resolve({ code: 0, data: source }) }
  f.api.confirmImport = (id, version) => { f.calls.push(['confirm', id, version]); return Promise.reject(new Error('声明当前确认失败')) }
  f.api.getImportJob = id => { f.calls.push(['get', id]); return Promise.resolve({ code: 0, data: { ...source, errorMessage: warning } }) }
  await beginFresh(f, file); await f.panel.upload(); await tick()
  await assert.doesNotReject(f.panel.confirm()); await tick()
  assert.equal(f.panel.job.id, 'CURRENT_FRESH_RECOVERY'); assert.equal(f.panel.job.status, 'VALIDATED')
  assert.equal(f.panel.job.sourceFileId, source.sourceFileId); assert.equal(f.panel.file.name, file.name)
  assert.equal(f.panel.preview.rows[0].studentNo, 'LOCAL_ONLY'); assert.equal(f.panel.canConfirm, true)
  assert.equal(f.panel.confirmBusy, false); assert.equal(f.panel.messageType, 'danger')
  assert.equal(f.panel.message, `声明当前确认失败\n${warning}`)
  assert.deepEqual(f.notices, []); assert.equal(f.lists.length, 1)
  assert.deepEqual(f.calls, [['upload', file], ['confirm', 'CURRENT_FRESH_RECOVERY', 1], ['get', 'CURRENT_FRESH_RECOVERY']])
})

// Append-only mechanism regression: real SFC/AppButton and strict Boolean native bindings.
// Custom renderer records actual compiled bindings; this is not a browser or normal-role proof.
test('fresh file controls expose real Boolean enabled bindings and retain busy and owned-job guards', async t => {
  const f = await fixture(t), response = deferred(), file = { name: 'DECLARED_BOOLEAN_CONTROLS.xlsx', size: 100 }
  f.pending.push(response)
  f.api.uploadRosterImport = value => { f.calls.push(['upload', value]); return response.promise }
  assert.equal(dispatch(f.root, '打开批量导入'), true); await tick()
  const inputs = walk(f.root).filter(n => n.type === 'input' && n.props.type === 'file')
  assert.equal(inputs.length, 1)
  const input = inputs[0]
  assert.equal(input.props.disabled, false, 'Actual compiled fresh native input binding must be Boolean false, never emptystring')
  assert.equal(buttons(f.root, '上传并预检查')[0].props.disabled, true, 'No selected file still blocks upload')
  const handlers = Array.isArray(input.props.onChange) ? input.props.onChange : [input.props.onChange]
  assert.ok(handlers.length && handlers.every(fn => typeof fn === 'function'))
  for (const handler of handlers) handler({ target: { files: [file] }, type: 'change' })
  await tick()
  assert.equal(input.props.disabled, false)
  assert.equal(buttons(f.root, '上传并预检查')[0].props.disabled, false, 'Actual Boolean AppButton prop must become enabled after public selection')
  assert.equal(dispatch(f.root, '上传并预检查'), true); await tick()
  assert.deepEqual(f.calls, [['upload', file]])
  assert.equal(input.props.disabled, true, 'Actual pending upload keeps the native input disabled')
  assert.equal(buttons(f.root, '上传并预检查')[0].props.disabled, true)
  assert.equal(dispatch(f.root, '上传并预检查'), false)
  assert.deepEqual(f.calls, [['upload', file]], 'A second public click cannot upload again while busy')
  response.resolve({ code: 0, data: job('DECLARED_BOOLEAN_JOB') }); await tick()
  assert.equal(input.props.disabled, true, 'A captured job keeps its file input disabled')
  assert.equal(buttons(f.root, '上传并预检查')[0].props.disabled, true)
  assert.equal(dispatch(f.root, '上传并预检查'), false)
  assert.deepEqual(f.calls, [['upload', file]], 'No confirmation or duplicate upload is called')
})
// Declared list-read failures exercise the real compiled parent and shared state.
// These mechanism cases do not inject failures into any normal HTTP/browser flow.
test('task-list business failure renders a public error instead of empty success', async t => {
  const retry = deferred(), requests = []
  const f = await fixture(t, { listJobs(params) {
    requests.push(params)
    return requests.length === 1
      ? Promise.resolve({ code: 1, message: '任务读取失败，请稍后重试', data: null })
      : retry.promise
  } })
  f.pending.push(retry)
  assert.match(text(f.root), /任务读取失败/, 'Business failure must render the actual public error panel, not empty success')
  assert.doesNotMatch(text(f.root), /暂无导入导出任务|共 0 个任务/)
  assert.equal(buttons(f.root, '继续处理').length, 0)
  assert.equal(buttons(f.root, '重试').length, 1, 'Actual AppGlobalState supplies the public recovery action')
  assert.equal(dispatch(f.root, '重试'), true)
  assert.equal(dispatch(f.root, '重试'), true, 'Two public events before render are still one in-flight request')
  await tick()
  assert.equal(requests.length, 2)
  assert.match(text(f.root), /正在读取任务/)
  assert.equal(dispatch(f.root, '刷新'), false)
  retry.resolve({ code: 0, data: { list: [job('3', 'SCANNING')], total: 1 } }); await tick()
  assert.equal(buttons(f.root, '继续处理').length, 1)
  assert.match(text(f.root), /共 1 个任务/)
  assert.doesNotMatch(text(f.root), /任务读取失败|正在读取任务|暂无导入导出任务/)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 1, pageSize: 50 }])
  assert.deepEqual(f.calls, [], 'Public list retry must not start import detail, upload or confirmation')
})

test('task-list rejected read exits loading and recovers through the real public retry button', async t => {
  let reads = 0
  const f = await fixture(t, { listJobs(params) {
    assert.deepEqual(params, { page: 1, pageSize: 50 }); reads++
    return reads === 1 ? Promise.reject(new Error('读取任务失败，请重试'))
      : Promise.resolve({ code: 0, data: { list: [job('3', 'SCANNING')], total: 1 } })
  } })
  assert.match(text(f.root), /读取任务失败，请重试/)
  assert.doesNotMatch(text(f.root), /正在读取任务|暂无导入导出任务|共 0 个任务/)
  assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
  assert.equal(dispatch(f.root, '重试'), true); await tick()
  assert.equal(reads, 2); assert.equal(buttons(f.root, '继续处理').length, 1)
  assert.equal(buttons(f.root, '重试').length, 0)
  assert.deepEqual(f.errors, []); assert.deepEqual(f.calls, [])
})

test('task-list failed public refresh hides stale cards and count while healthy empty retry remains distinct', async t => {
  let reads = 0
  const f = await fixture(t, { listJobs(params) {
    assert.deepEqual(params, { page: 1, pageSize: 50 }); reads++
    if (reads === 1) return Promise.resolve({ code: 0, data: { list: [job('3', 'SCANNING')], total: 1 } })
    if (reads === 2) return Promise.resolve({ code: 1, message: '任务列表暂时无法读取', data: null })
    return Promise.resolve({ code: 0, data: { list: [], total: 0 } })
  } })
  assert.equal(buttons(f.root, '继续处理').length, 1); assert.match(text(f.root), /共 1 个任务/)
  assert.equal(dispatch(f.root, '刷新'), true); await tick()
  assert.match(text(f.root), /任务列表暂时无法读取/)
  assert.equal(buttons(f.root, '继续处理').length, 0)
  assert.doesNotMatch(text(f.root), /共 1 个任务|共 0 个任务|暂无导入导出任务/)
  assert.equal(dispatch(f.root, '重试'), true); await tick()
  assert.equal(reads, 3); assert.match(text(f.root), /暂无导入导出任务。/)
  assert.match(text(f.root), /共 0 个任务/)
  assert.equal(buttons(f.root, '重试').length, 0)
  assert.doesNotMatch(text(f.root), /任务列表暂时无法读取|正在读取任务/)
  assert.deepEqual(f.calls, [])
})

test('task-list permission failure keeps the shared forbidden state rather than offering ordinary retry', async t => {
  const f = await fixture(t, { listJobs: async params => {
    assert.deepEqual(params, { page: 1, pageSize: 50 })
    return { code: 403001, bizCode: 'NO_PERMISSION', message: 'permissionKey academicAffairs.roster.view', data: null }
  } })
  assert.match(text(f.root), /暂无访问权限|不在授权范围/)
  assert.doesNotMatch(text(f.root), /permissionKey|academicAffairs|暂无导入导出任务|共 0 个任务/)
  assert.equal(buttons(f.root, '重试').length, 0)
  assert.equal(buttons(f.root, '继续处理').length, 0)
  assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
  assert.equal(f.lists.length, 1); assert.deepEqual(f.calls, [])
})
for (const change of ['context', 'identity']) {
  for (const settlement of ['resolve', 'reject']) {
    test(`task-list ${change} change keeps late ${settlement} out of a new public refresh`, async t => {
      const older = deferred(), current = deferred(), requests = []
      const f = await fixture(t, { listJobs(params) {
        requests.push(params)
        return requests.length === 1 ? older.promise : current.promise
      } })
      f.pending.push(older, current)
      assert.match(text(f.root), /正在读取任务/)
      if (change === 'context') f.state.ctx = ctx('B')
      else f.state.identity = 'identity-B'
      await tick()
      assert.equal(requests.length, 1, 'Identity invalidation must not manufacture an automatic query')
      assert.match(text(f.root), /任务列表需刷新/)
      assert.match(text(f.root), /身份或管理范围已变化，请重新读取任务列表/)
      assert.doesNotMatch(text(f.root), /暂无导入导出任务|共 0 个任务/)
      assert.equal(dispatch(f.root, '刷新'), true); await tick()
      assert.equal(requests.length, 2); assert.match(text(f.root), /正在读取任务/)
      if (settlement === 'resolve') older.resolve({ code: 0, data: { list: [job('OLD_TASK', 'SCANNING')], total: 99 } })
      else older.reject(new Error('旧身份读取失败，不应显示'))
      await tick()
      assert.match(text(f.root), /正在读取任务/)
      assert.doesNotMatch(text(f.root), /OLD_TASK|共 99 个任务|旧身份读取失败|任务读取失败|任务列表需刷新/)
      assert.equal(buttons(f.root, '继续处理').length, 0)
      assert.equal(dispatch(f.root, '刷新'), false, 'Old finally cannot enable a duplicate read while the new owner is pending')
      assert.equal(f.vm.jobs.loading, true); assert.equal(f.vm.jobs.error, null)
      current.resolve({ code: 0, data: { list: [job('4', 'SCANNING')], total: 1 } }); await tick()
      assert.match(taskIdentityText(f.root), /任务 #4/); assert.match(text(f.root), /共 1 个任务/)
      assert.doesNotMatch(text(f.root), /OLD_TASK|旧身份读取失败|正在读取任务|任务列表需刷新/)
      assert.equal(buttons(f.root, '继续处理').length, 1)
      assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
      assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 1, pageSize: 50 }])
      assert.deepEqual(f.errors, []); assert.deepEqual(f.calls, [])
    })
  }
}

for (const settlement of ['resolve', 'reject']) {
  test(`task-list unmount keeps late ${settlement} from changing a new mounted task list`, async t => {
    const response = deferred()
    const old = await fixture(t, { listJobs: () => response.promise }); old.pending.push(response)
    old.stop()
    const frozenOldState = JSON.parse(JSON.stringify(old.vm.jobs))
    const fresh = await fixture(t, { jobs: [job('4', 'SCANNING')] })
    const freshState = JSON.parse(JSON.stringify(fresh.vm.jobs))
    assert.match(taskIdentityText(fresh.root), /任务 #4/)
    if (settlement === 'resolve') response.resolve({ code: 0, data: { list: [job('DISPOSED_TASK', 'SCANNING')], total: 99 } })
    else response.reject(new Error('已卸载身份读取失败，不应显示'))
    await tick()
    assert.deepEqual(old.vm.jobs, frozenOldState, 'Unmounted instance must not accept late list, error or finally mutations')
    assert.deepEqual(fresh.vm.jobs, freshState)
    assert.match(taskIdentityText(fresh.root), /任务 #4/); assert.match(text(fresh.root), /共 1 个任务/)
    assert.doesNotMatch(text(fresh.root), /DISPOSED_TASK|共 99 个任务|已卸载身份读取失败/)
    assert.equal(buttons(fresh.root, '继续处理').length, 1)
    assert.deepEqual(old.errors, []); assert.deepEqual(fresh.errors, [])
    assert.equal(old.lists.length, 1); assert.equal(fresh.lists.length, 1)
    assert.deepEqual(old.calls, []); assert.deepEqual(fresh.calls, [])
  })
}
test('task-list synchronous invalidation releases the old owner before rendering a usable public refresh', async t => {
  for (const change of ['context', 'identity']) {
    const older = deferred(), current = deferred(), requests = []
    const f = await fixture(t, { listJobs(params) {
      requests.push(params)
      return requests.length === 1 ? older.promise : current.promise
    } })
    f.pending.push(older, current)
    assert.equal(buttons(f.root, '刷新')[0].props.disabled, true)
    if (change === 'context') f.state.ctx.ctxKey = 'B'
    else f.state.identity = 'identity-B'
    // Same-tick state invalidation is separate from the next real Vue render.
    // Never dispatch the still-disabled public button or change its host props.
    assert.equal(f.vm.jobs.loading, false)
    assert.equal(f.vm.jobs.error.title, '任务列表需刷新')
    assert.equal(requests.length, 1, 'Synchronous invalidation does not create an automatic request')
    assert.equal(buttons(f.root, '刷新')[0].props.disabled, true)
    await nextTick()
    assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
    assert.equal(dispatch(f.root, '刷新'), true); await tick()
    assert.equal(requests.length, 2)
    older.resolve({ code: 0, data: { list: [job('STALE_SYNC_OWNER', 'SCANNING')], total: 99 } }); await tick()
    assert.match(text(f.root), /正在读取任务/)
    assert.doesNotMatch(text(f.root), /STALE_SYNC_OWNER|共 99 个任务/)
    assert.equal(dispatch(f.root, '刷新'), false)
    current.resolve({ code: 0, data: { list: [job('4', 'SCANNING')], total: 1 } }); await tick()
    assert.match(taskIdentityText(f.root), /任务 #4/); assert.match(text(f.root), /共 1 个任务/)
    assert.equal(f.lists.length, 2); assert.deepEqual(f.calls, []); assert.deepEqual(f.errors, [])
    f.stop()
  }
})


// Public pagination uses the actual shared component; declared pages are not real owned database tasks.
const pagingButtons = (root, label) => walk(root).filter(n => n.type === 'button' && n.props['aria-label'] === label)
function dispatchPaging(root, label) {
  const targets = pagingButtons(root, label)
  assert.equal(targets.length, 1, 'Actual shared pagination must expose one public page action')
  const target = targets[0]
  if (target.props.disabled) return false
  for (const fn of Array.isArray(target.props.onClick) ? target.props.onClick : [target.props.onClick]) fn?.({ target, type: 'click' })
  return true
}
const declaredTasks = (start, count) => Array.from({ length: count }, (_, i) => job(String(start + i), 'SCANNING'))
const declaredPage = (page, total, list = page === 1 ? declaredTasks(1, Math.min(total, 50)) : declaredTasks(51, Math.max(0, total - 50))) => ({ code: 0, data: { list, total, page, pageSize: 50 } })

test('task pagination exposes the fifty-first declared task through public next and previous actions', async t => {
  const requests = []
  const f = await fixture(t, { listJobs: async params => { requests.push(params); return declaredPage(params.page, 51) } })
  assert.equal(pagingButtons(f.root, '下一页').length, 1, 'The first 50 tasks must not hide an available next page')
  assert.equal(pagingButtons(f.root, '上一页')[0].props.disabled, true)
  assert.doesNotMatch(taskIdentityText(f.root), /任务 #51/)
  assert.equal(dispatchPaging(f.root, '下一页'), true); await tick()
  assert.match(taskIdentityText(f.root), /任务 #51/); assert.match(text(f.root), /共 51 个任务/)
  assert.equal(buttons(f.root, '继续处理').length, 1)
  assert.equal(pagingButtons(f.root, '下一页')[0].props.disabled, true)
  assert.equal(dispatchPaging(f.root, '上一页'), true); await tick()
  assert.equal(buttons(f.root, '继续处理').length, 50)
  assert.doesNotMatch(taskIdentityText(f.root), /任务 #51/)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }, { page: 1, pageSize: 50 }])
  assert.deepEqual(f.calls, [])
})

test('task pagination pending read removes page actions and prevents duplicate public refresh', async t => {
  const response = deferred(), requests = []
  const f = await fixture(t, { listJobs(params) { requests.push(params); return requests.length === 1 ? Promise.resolve(declaredPage(1, 51)) : response.promise } })
  f.pending.push(response)
  assert.equal(dispatchPaging(f.root, '下一页'), true); await tick()
  assert.match(text(f.root), /正在读取任务/)
  assert.equal(pagingButtons(f.root, '下一页').length, 0)
  assert.equal(buttons(f.root, '刷新')[0].props.disabled, true)
  assert.equal(dispatch(f.root, '刷新'), false)
  assert.equal(requests.length, 2, 'Shared update:page and change must not produce duplicate reads')
  response.resolve(declaredPage(2, 51)); await tick()
  assert.equal(pagingButtons(f.root, '上一页').length, 1)
  assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
  assert.match(taskIdentityText(f.root), /任务 #51/)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }])
})

for (const failure of ['business', 'reject']) {
  test(`task pagination ${failure} failure retries the requested page instead of transient empty total`, async t => {
    const requests = []
    const f = await fixture(t, { listJobs(params) {
      requests.push(params)
      if (requests.length === 1) return Promise.resolve(declaredPage(1, 51))
      if (requests.length === 2) return failure === 'business' ? Promise.resolve({ code: 1, message: '第二页任务读取失败，请重试', data: null }) : Promise.reject(new Error('第二页任务读取失败，请重试'))
      return Promise.resolve(declaredPage(2, 51))
    } })
    assert.equal(dispatchPaging(f.root, '下一页'), true); await tick()
    assert.match(text(f.root), /第二页任务读取失败，请重试/)
    assert.doesNotMatch(taskIdentityText(f.root), /暂无导入导出任务|共 0 个任务|任务 #1/)
    assert.equal(f.vm.jobs.page, 2); assert.equal(f.vm.jobs.loading, false)
    assert.equal(dispatch(f.root, '重试'), true); await tick()
    assert.match(taskIdentityText(f.root), /任务 #51/)
    assert.equal(f.vm.jobs.page, 2)
    assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }, { page: 2, pageSize: 50 }])
    assert.deepEqual(f.calls, [])
  })
}

test('task pagination genuine zero total resets page one without a correction request', async t => {
  const requests = []
  const f = await fixture(t, { listJobs: async params => { requests.push(params); return requests.length === 1 ? declaredPage(1, 51) : declaredPage(2, 0, []) } })
  assert.equal(dispatchPaging(f.root, '下一页'), true); await tick()
  assert.equal(f.vm.jobs.page, 1); assert.equal(f.vm.jobs.loading, false)
  assert.match(text(f.root), /暂无导入导出任务。/); assert.match(text(f.root), /共 0 个任务/)
  assert.equal(pagingButtons(f.root, '下一页').length, 0)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }])
})

test('task pagination shrinking last page performs exactly one owned correction read', async t => {
  const requests = []
  const f = await fixture(t, { listJobs: async params => {
    requests.push(params)
    if (requests.length === 1) return declaredPage(1, 51)
    if (requests.length === 2) return declaredPage(2, 1, [])
    return declaredPage(1, 1, [job('CURRENT_LAST', 'SCANNING')])
  } })
  assert.equal(dispatchPaging(f.root, '下一页'), true); await tick()
  assert.match(taskIdentityText(f.root), /任务 #CURRENT_LAST/); assert.match(text(f.root), /共 1 个任务/)
  assert.doesNotMatch(text(f.root), /暂无导入导出任务|任务读取失败|正在读取任务/)
  assert.equal(f.vm.jobs.page, 1); assert.equal(f.vm.jobs.loading, false)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }, { page: 1, pageSize: 50 }])
})

test('task pagination second shrink stops correction and releases busy for a public retry', async t => {
  const requests = []
  const f = await fixture(t, { listJobs: async params => {
    requests.push(params)
    if (requests.length === 1) return declaredPage(1, 151, declaredTasks(1, 50))
    if (requests.length === 2) return declaredPage(4, 101, [])
    if (requests.length === 3) return declaredPage(3, 1, [])
    return declaredPage(1, 1, [job('LATEST_TASK', 'SCANNING')])
  } })
  assert.equal(dispatch(f.root, '4'), true); await tick()
  assert.match(text(f.root), /任务数量已变化，请重试/)
  assert.doesNotMatch(taskIdentityText(f.root), /暂无导入导出任务|共 0 个任务|任务 #1/)
  assert.equal(f.vm.jobs.page, 1); assert.equal(f.vm.jobs.loading, false)
  assert.equal(requests.length, 3, 'Second shrinking response must not cause a third automatic read')
  assert.equal(dispatch(f.root, '重试'), true); await tick()
  assert.match(taskIdentityText(f.root), /任务 #LATEST_TASK/)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 4, pageSize: 50 }, { page: 3, pageSize: 50 }, { page: 1, pageSize: 50 }])
})

test('task pagination correction read failure preserves the corrected retry target', async t => {
  const requests = []
  const f = await fixture(t, { listJobs: async params => {
    requests.push(params)
    if (requests.length === 1) return declaredPage(1, 151, declaredTasks(1, 50))
    if (requests.length === 2) return declaredPage(4, 101, [])
    if (requests.length === 3) throw new Error('回收页读取失败，请重试')
    return declaredPage(3, 101, [job('CORRECTED_TASK', 'SCANNING')])
  } })
  assert.equal(dispatch(f.root, '4'), true); await tick()
  assert.match(text(f.root), /回收页读取失败，请重试/)
  assert.equal(f.vm.jobs.page, 3); assert.equal(f.vm.jobs.loading, false)
  assert.equal(dispatch(f.root, '重试'), true); await tick()
  assert.match(taskIdentityText(f.root), /任务 #CORRECTED_TASK/)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 4, pageSize: 50 }, { page: 3, pageSize: 50 }, { page: 3, pageSize: 50 }])
})

for (const change of ['context', 'identity']) {
  for (const settlement of ['resolve', 'reject']) {
    test(`task pagination ${change} invalidation ignores late page-two ${settlement} and resets the public read`, async t => {
      const oldPage = deferred(), current = deferred(), requests = []
      const f = await fixture(t, { listJobs(params) {
        requests.push(params)
        if (requests.length === 1) return Promise.resolve(declaredPage(1, 51))
        return requests.length === 2 ? oldPage.promise : current.promise
      } })
      f.pending.push(oldPage, current)
      assert.equal(dispatchPaging(f.root, '下一页'), true); await tick()
      if (change === 'context') f.state.ctx.ctxKey = 'NEW_PAGE_SCOPE'
      else f.state.identity = 'identity-new-page-scope'
      assert.equal(f.vm.jobs.page, 1); assert.equal(f.vm.jobs.loading, false)
      assert.equal(requests.length, 2, 'Changed scope must not cause an automatic page read')
      await nextTick()
      assert.equal(dispatch(f.root, '刷新'), true); await tick()
      if (settlement === 'resolve') oldPage.resolve(declaredPage(2, 1, [job('OLD_PAGE', 'SCANNING')]))
      else oldPage.reject(new Error('旧分页读取失败，不应显示'))
      await tick()
      assert.match(text(f.root), /正在读取任务/)
      assert.doesNotMatch(text(f.root), /OLD_PAGE|旧分页读取失败|任务读取失败|暂无导入导出任务/)
      assert.equal(f.vm.jobs.page, 1); assert.equal(f.vm.jobs.loading, true)
      assert.equal(dispatch(f.root, '刷新'), false)
      assert.equal(requests.length, 3, 'Late old shrink must not cause a correction request')
      current.resolve(declaredPage(1, 1, [job('NEW_PAGE_SCOPE_TASK', 'SCANNING')])); await tick()
      assert.match(taskIdentityText(f.root), /任务 #NEW_PAGE_SCOPE_TASK/)
      assert.equal(f.vm.jobs.loading, false); assert.equal(f.vm.jobs.page, 1)
      assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }, { page: 1, pageSize: 50 }])
      assert.deepEqual(f.calls, [])
    })
  }
}

for (const settlement of ['resolve', 'reject']) {
  test(`task pagination unmount ignores late page-two ${settlement} without changing a fresh list`, async t => {
    const response = deferred(), requests = []
    const old = await fixture(t, { listJobs(params) { requests.push(params); return requests.length === 1 ? Promise.resolve(declaredPage(1, 51)) : response.promise } })
    old.pending.push(response)
    assert.equal(dispatchPaging(old.root, '下一页'), true); await tick()
    old.stop()
    const frozen = JSON.parse(JSON.stringify(old.vm.jobs))
    const fresh = await fixture(t, { jobs: [job('NEW_INSTANCE_TASK', 'SCANNING')] })
    const freshState = JSON.parse(JSON.stringify(fresh.vm.jobs))
    if (settlement === 'resolve') response.resolve(declaredPage(2, 1, [job('DISPOSED_PAGE', 'SCANNING')]))
    else response.reject(new Error('已卸载分页读取失败'))
    await tick()
    assert.deepEqual(old.vm.jobs, frozen); assert.deepEqual(fresh.vm.jobs, freshState)
    assert.match(taskIdentityText(fresh.root), /任务 #NEW_INSTANCE_TASK/)
    assert.doesNotMatch(text(fresh.root), /DISPOSED_PAGE|已卸载分页读取失败/)
    assert.equal(old.vm.jobs.page, 2); assert.equal(fresh.vm.jobs.page, 1)
    assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }])
    assert.equal(fresh.lists.length, 1); assert.deepEqual(old.calls, []); assert.deepEqual(fresh.calls, [])
  })
}

test('task pagination keeps a small actual-style list free from meaningless page actions', async t => {
  const requests = []
  const f = await fixture(t, { listJobs: async params => { requests.push(params); return declaredPage(1, 2, [job('4', 'SCANNING'), job('3', 'SCANNING')]) } })
  assert.equal(pagingButtons(f.root, '下一页').length, 0)
  assert.equal(pagingButtons(f.root, '上一页').length, 0)
  assert.match(taskIdentityText(f.root), /任务 #4/); assert.match(taskIdentityText(f.root), /任务 #3/)
  assert.equal(dispatch(f.root, '刷新'), true); await tick()
  assert.equal(pagingButtons(f.root, '下一页').length, 0)
  assert.deepEqual(requests, [{ page: 1, pageSize: 50 }, { page: 1, pageSize: 50 }])
  assert.deepEqual(f.calls, [])
})


// Actual MemoryRouter and canonical return-store mechanism; declared data is not native authorization proof.
const Router = require('vue-router')
const TASK_ROUTE = '/admin/academic-affairs/roster/import-export'
const hash = value => createHash('sha256').update(value).digest('hex')
const recordRouteEvidence = () => {}
async function routeFixture(t, options = {}) {
  const requests = [], errors = [], warnings = [], transitions = [], routerErrors = [], notices = [], pending = []
  const state = reactive({ ctx: ctx('CONTROLLED_SCOPE'), claims: { tenantId: 'CONTROLLED_TENANT', userId: 'CONTROLLED_USER', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'CONTROLLED_CONTEXT' }, taskLocation: TASK_ROUTE })
  const storageMap = new Map(), clock = { value: Date.now() }
  const storage = { getItem: key => storageMap.get(key) ?? null, setItem: (key, value) => storageMap.set(key, value), removeItem: key => storageMap.delete(key) }
  const returns = academicRouteHelpers.createAcademicReturnStore(storage, { now: () => clock.value })
  const identity = () => academicRouteHelpers.academicIdentity(state.claims, state.ctx)
  const api = {
    uploadRosterImport() { throw new Error('禁止该Router夹具调用上传') },
    listJobs: async params => {
      requests.push({ ...params })
      if (options.listJobs) return options.listJobs(params)
      const list = params.page === 1 ? Array.from({ length: 50 }, (_, i) => job(String(i + 1), 'SCANNING')) : [job('51', 'SCANNING')]
      return { code: 0, data: { list, total: 51, page: params.page, pageSize: 50 } }
    }
  }
  const child = compile('modules/academicAffairs/components/AaAuthoritativeImportDrawer.vue', { ...visuals, AppButton, academicFileExchangeApi: api })
  const parent = compile('modules/academicAffairs/views/AaRosterImportExportView.vue', { ...visuals, AppButton, AppGlobalState, AppPagination, normalizeUiError, ...academicRouteHelpers, AaAuthoritativeImportDrawer: child, academicFileExchangeApi: api, academicAffairsApi: {}, academicExchangeTypeLabel: value => value, academicStatusLabel: value => value, toast: { error(message) { notices.push(message) }, success() {}, warning() {} }, systemPrompt: async () => null })
  const router = Router.createRouter({ history: Router.createMemoryHistory(), routes: [
    { path: TASK_ROUTE, component: parent, props: () => ({ ctx: state.ctx }) },
    { path: '/declared-other-public-page', component: { render: () => h('p', '声明的其他公开路由') } }
  ] })
  const removeError = router.onError(error => routerErrors.push(String(error)))
  const removeAfter = router.afterEach((to, from, failure) => {
    transitions.push({ to: to.fullPath, from: from.fullPath, failed: !!failure })
    if (!failure && to.path === TASK_ROUTE) state.taskLocation = to.fullPath
  })
  const initial = typeof options.initial === 'function' ? options.initial({ state, returns, identity, clock, storage }) : options.initial || TASK_ROUTE
  await router.push(initial); await router.isReady()
  const removeResolve = options.beforeResolve ? router.beforeResolve((to, from) => options.beforeResolve(to, from, state)) : () => {}
  const root = node('root')
  const shell = { render() { return h('div', [
    h(Router.RouterLink, { to: '/declared-other-public-page' }, { default: () => '离开任务页' }),
    h(Router.RouterLink, { to: state.taskLocation }, { default: () => '返回任务页' }),
    h(Router.RouterView)
  ]) } }
  const app = renderer.createApp(shell)
  app.use(router)
  app.provide('academicFlow', { identity, returns })
  app.config.errorHandler = value => errors.push(String(value))
  app.config.warnHandler = value => warnings.push(String(value))
  app.mount(root); await routeRenderBarrier()
  let stopped = false
  function stop() { if (!stopped) { app.unmount(); stopped = true } }
  const evidence = { counterDomain: 'One declared public compiled View + actual MemoryRouter roundtrip; not native/API/MySQL', beforeViewSha256: hash(read('modules/academicAffairs/views/AaRosterImportExportView.vue')), requests, transitions, warnings, errors, firstTarget: 'Final task-page GET must restore requested page2', observed: {} }
  t.after(async () => {
    stop(); removeAfter(); removeResolve(); removeError()
    for (const value of pending) value.resolve(true)
    await routeRenderBarrier()
    evidence.observed.finalQueries = requests.map(x => ({ ...x }))
    recordRouteEvidence(evidence)
    assert.deepEqual(errors, []); assert.deepEqual(warnings, [])
  })
  return { root, router, requests, transitions, evidence, state, identity, returns, clock, storage, pending, notices, routerErrors, stop }
}
async function routeRenderBarrier() {
  await new Promise(resolve => setImmediate(resolve)); await nextTick()
}
function publicPageButton(root, label) {
  const matches = walk(root).filter(n => n.type === 'button' && n.props['aria-label'] === label)
  assert.equal(matches.length, 1)
  const target = matches[0]; assert.equal(target.props.disabled, false)
  for (const fn of Array.isArray(target.props.onClick) ? target.props.onClick : [target.props.onClick]) fn?.({ target, type: 'click' })
}
async function publicRouteLink(f, label, targetPath) {
  const matches = walk(f.root).filter(n => n.type === 'a' && text(n).trim() === label)
  assert.equal(matches.length, 1)
  const target = matches[0]
  const terminal = new Promise(resolve => {
    const remove = f.router.afterEach((to, _from, failure) => { if (to.path === targetPath) { remove(); resolve({ to, failure }) } })
  })
  const event = { target, currentTarget: { getAttribute: key => target.props[key] ?? null }, type: 'click', button: 0, metaKey: false, altKey: false, ctrlKey: false, shiftKey: false, defaultPrevented: false, preventDefault() { this.defaultPrevented = true } }
  for (const fn of Array.isArray(target.props.onClick) ? target.props.onClick : [target.props.onClick]) fn?.(event)
  const observed = await terminal
  assert.equal(!!observed.failure, false)
  await routeRenderBarrier()
}

test('task position public page-two navigation survives public route departure and return', async t => {
  const f = await routeFixture(t)
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }])
  publicPageButton(f.root, '下一页'); await routeRenderBarrier()
  assert.deepEqual(f.requests.at(-1), { page: 2, pageSize: 50 })
  assert.match(taskIdentityText(f.root), /任务 #51/)
  f.evidence.observed.actualTaskLocationBeforeLeave = f.router.currentRoute.value.fullPath
  await publicRouteLink(f, '离开任务页', '/declared-other-public-page')
  await publicRouteLink(f, '返回任务页', TASK_ROUTE)
  f.evidence.observed.actualReturnedURL = f.router.currentRoute.value.fullPath
  f.evidence.observed.actualReturnedTaskText = text(f.root)
  f.evidence.observed.lastQuery = { ...f.requests.at(-1) }
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }, { page: 2, pageSize: 50 }], 'Public route return must preserve page-two position and issue exactly one owned read')
  assert.match(taskIdentityText(f.root), /任务 #51/)
  assert.equal(f.router.currentRoute.value.query.page, '2')
  assert.equal(typeof f.router.currentRoute.value.query.returnToken, 'string')
  assert.ok(f.router.currentRoute.value.query.returnToken)
})


for (const value of ['2', '0', '1000001', ['2', '3']]) {
  test(`task position absent-token deep link parses declared page ${JSON.stringify(value)} for the current actor once`, async t => {
    const expected = value === '2' ? 2 : 1
    const f = await routeFixture(t, { initial: { path: TASK_ROUTE, query: { page: value, untouched: 'keep' } } })
    assert.deepEqual(f.requests, [{ page: expected, pageSize: 50 }])
    assert.equal(Number(f.router.currentRoute.value.query.page || '1'), expected)
    assert.equal(f.router.currentRoute.value.query.untouched, 'keep')
    assert.equal(typeof f.router.currentRoute.value.query.returnToken, 'string')
    assert.match(taskIdentityText(f.root), expected === 2 ? /任务 #51/ : /任务 #1/)
  })
}

for (const invalid of ['empty', 'array', 'unknown', 'expired', 'foreign-identity', 'sibling-path', 'page-mismatch']) {
  test(`task position present ${invalid} return token cannot fall through to explicit old page two`, async t => {
    const f = await routeFixture(t, { initial({ state, returns, identity, clock }) {
      let token
      if (invalid === 'empty') token = ''
      else if (invalid === 'array') token = ['not-one', 'not-two']
      else if (invalid === 'unknown') token = 'UNKNOWN_DECLARED_RETURN'
      else {
        const tokenIdentity = invalid === 'foreign-identity' ? academicRouteHelpers.academicIdentity({ ...state.claims, userId: 'OTHER_DECLARED_USER' }, state.ctx) : identity()
        const path = invalid === 'sibling-path' ? '/admin/academic-affairs/roster' : TASK_ROUTE
        token = returns.remember({ path, query: { page: invalid === 'page-mismatch' ? '3' : '2', keyword: 'DO_NOT_COPY_FROM_REFERENCE' } }, tokenIdentity)
        if (invalid === 'expired') clock.value += 30 * 60 * 1000
      }
      return { path: TASK_ROUTE, query: { page: '2', returnToken: token, untouched: 'keep' } }
    } })
    assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }])
    assert.match(taskIdentityText(f.root), /任务 #1/); assert.doesNotMatch(taskIdentityText(f.root), /任务 #51/)
    assert.equal(Number(f.router.currentRoute.value.query.page || '1'), 1)
    assert.equal(f.router.currentRoute.value.query.keyword, undefined)
    assert.equal(f.router.currentRoute.value.query.untouched, 'keep')
    assert.equal(typeof f.router.currentRoute.value.query.returnToken, 'string')
  })
}

test('task position reference uses canonical identity without evicting another same-identity consumer', async t => {
  let sibling, currentIdentity
  const f = await routeFixture(t, { initial({ returns, identity }) {
    currentIdentity = identity()
    sibling = returns.remember({ path: '/admin/academic-affairs/roster', query: { page: '2', keyword: 'DECLARED_SIBLING_POSITION' } }, currentIdentity)
    const token = returns.remember({ path: TASK_ROUTE, query: { page: '2', keyword: 'DO_NOT_COPY_FROM_REFERENCE' } }, currentIdentity)
    return { path: TASK_ROUTE, query: { page: '2', returnToken: token } }
  } })
  assert.deepEqual(f.requests, [{ page: 2, pageSize: 50 }])
  assert.equal(f.router.currentRoute.value.query.keyword, undefined)
  assert.equal(f.returns.resolve(sibling, currentIdentity).path, '/admin/academic-affairs/roster?page=2&keyword=DECLARED_SIBLING_POSITION')
  await publicRouteLink(f, '离开任务页', '/declared-other-public-page')
  await publicRouteLink(f, '返回任务页', TASK_ROUTE)
  assert.deepEqual(f.requests, [{ page: 2, pageSize: 50 }, { page: 2, pageSize: 50 }])
  assert.ok(f.returns.resolve(sibling, currentIdentity))
})

for (const change of ['context', 'identity']) {
  test(`task position cancels a pending URL publication before commit after real ${change} change`, async t => {
    const guard = deferred(); let entered = false
    const f = await routeFixture(t, { beforeResolve(to) { if (to.path === TASK_ROUTE && to.query.page === '2') { entered = true; return guard.promise } } })
    f.pending.push(guard)
    publicPageButton(f.root, '下一页'); await routeRenderBarrier()
    assert.equal(entered, true, 'The actual Router beforeResolve must really hold the page publication')
    assert.equal(Number(f.router.currentRoute.value.query.page || '1'), 1)
    assert.equal(dispatch(f.root, '刷新'), false)
    if (change === 'context') { f.state.ctx.ctxKey = 'NEW_CONTROLLED_SCOPE'; f.state.ctx.dataScopeVersion = '2' }
    else f.state.claims.userId = 'NEW_CONTROLLED_USER'
    await routeRenderBarrier()
    assert.equal(f.requests.length, 1, 'Scope invalidation is not an automatic task query')
    guard.resolve(true); await routeRenderBarrier()
    assert.equal(Number(f.router.currentRoute.value.query.page || '1'), 1)
    assert.equal(f.router.currentRoute.value.query.returnToken, undefined)
    assert.match(text(f.root), /任务列表需刷新/)
    assert.equal(dispatch(f.root, '刷新'), true); await routeRenderBarrier()
    assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }, { page: 1, pageSize: 50 }])
    assert.equal(Number(f.router.currentRoute.value.query.page || '1'), 1)
    assert.match(taskIdentityText(f.root), /任务 #1/)
    assert.equal(f.transitions.some(x => !x.failed && x.to.includes('page=2')), false, 'Old scope URL must never commit, not merely be repaired afterwards')
  })
}

test('task position pending publication cannot steal an ordinary public departure', async t => {
  const guard = deferred(); let entered = false
  const f = await routeFixture(t, { beforeResolve(to) { if (to.path === TASK_ROUTE && to.query.page === '2') { entered = true; return guard.promise } } })
  f.pending.push(guard)
  publicPageButton(f.root, '下一页'); await routeRenderBarrier(); assert.equal(entered, true)
  await publicRouteLink(f, '离开任务页', '/declared-other-public-page')
  guard.resolve(true); await routeRenderBarrier()
  assert.equal(f.router.currentRoute.value.path, '/declared-other-public-page')
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }])
  assert.equal(f.transitions.some(x => !x.failed && x.to.includes('page=2')), false)
})

test('task position pending publication remains canceled after the actual Router application unmounts', async t => {
  const guard = deferred(); let entered = false
  const f = await routeFixture(t, { beforeResolve(to) { if (to.path === TASK_ROUTE && to.query.page === '2') { entered = true; return guard.promise } } })
  f.pending.push(guard)
  publicPageButton(f.root, '下一页'); await routeRenderBarrier(); assert.equal(entered, true)
  f.stop()
  guard.resolve(true); await routeRenderBarrier()
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }])
  assert.equal(f.router.currentRoute.value.path, '/')
  assert.equal(f.transitions.some(x => !x.failed && x.to.includes('page=2')), false)
})

for (const outcome of ['zero', 'one-shrink', 'second-shrink']) {
  test(`task position ${outcome} synchronizes the owned URL without extra automatic list reads`, async t => {
    let reads = 0
    const f = await routeFixture(t, { initial: { path: TASK_ROUTE, query: { page: outcome === 'zero' ? '2' : '4' } }, listJobs(params) {
      reads++
      if (reads === 1) return declaredPage(params.page, outcome === 'zero' ? 51 : 151, [job('INITIAL_POSITION_TASK', 'SCANNING')])
      if (outcome === 'zero') return declaredPage(params.page, 0, [])
      if (reads === 2) return declaredPage(4, 101, [])
      if (outcome === 'second-shrink' && reads === 3) return declaredPage(3, 1, [])
      return declaredPage(params.page, outcome === 'one-shrink' ? 101 : 1, [job('CURRENT_POSITION_TASK', 'SCANNING')])
    } })
    assert.equal(dispatch(f.root, '刷新'), true); await routeRenderBarrier()
    const expectedPage = outcome === 'one-shrink' ? 3 : 1
    assert.equal(Number(f.router.currentRoute.value.query.page || '1'), expectedPage)
    const token = f.router.currentRoute.value.query.returnToken
    assert.equal(typeof token, 'string')
    const reference = f.returns.resolve(token, f.identity())
    assert.ok(reference)
    assert.equal(academicRouteHelpers.academicRouteState({ query: Object.fromEntries(new URL(reference.path, 'http://academic.local').searchParams) }).page, expectedPage)
    assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
    if (outcome === 'zero') {
      assert.match(text(f.root), /暂无导入导出任务。/)
      assert.deepEqual(f.requests, [{ page: 2, pageSize: 50 }, { page: 2, pageSize: 50 }])
    } else if (outcome === 'one-shrink') {
      assert.match(taskIdentityText(f.root), /任务 #CURRENT_POSITION_TASK/)
      assert.deepEqual(f.requests, [{ page: 4, pageSize: 50 }, { page: 4, pageSize: 50 }, { page: 3, pageSize: 50 }])
    } else {
      assert.match(text(f.root), /任务数量已变化，请重试/)
      assert.deepEqual(f.requests, [{ page: 4, pageSize: 50 }, { page: 4, pageSize: 50 }, { page: 3, pageSize: 50 }])
      assert.equal(dispatch(f.root, '重试'), true); await routeRenderBarrier()
      assert.deepEqual(f.requests.at(-1), { page: 1, pageSize: 50 })
      assert.equal(f.requests.length, 4)
      assert.match(taskIdentityText(f.root), /任务 #CURRENT_POSITION_TASK/)
    }
  })
}

test('task position list failure retry keeps the committed page-two URL and query', async t => {
  let reads = 0
  const f = await routeFixture(t, { initial: TASK_ROUTE + '?page=2', listJobs(params) {
    reads++
    if (reads === 2) return { code: 1, message: '本页读取失败，请重试', data: null }
    return declaredPage(params.page, 51)
  } })
  const committed = f.router.currentRoute.value.fullPath
  assert.equal(dispatch(f.root, '刷新'), true); await routeRenderBarrier()
  assert.match(text(f.root), /本页读取失败，请重试/)
  assert.equal(f.router.currentRoute.value.fullPath, committed)
  assert.equal(dispatch(f.root, '重试'), true); await routeRenderBarrier()
  assert.deepEqual(f.requests, [{ page: 2, pageSize: 50 }, { page: 2, pageSize: 50 }, { page: 2, pageSize: 50 }])
  assert.equal(f.router.currentRoute.value.fullPath, committed)
  assert.match(taskIdentityText(f.root), /任务 #51/)
})

test('task position rejected navigation retains healthy page-one cards and does not issue a task read', async t => {
  let rejectNext = true
  const f = await routeFixture(t, { beforeResolve(to) { if (to.query.page === '2' && rejectNext) return false } })
  const committed = f.router.currentRoute.value.fullPath
  publicPageButton(f.root, '下一页'); await routeRenderBarrier()
  assert.equal(f.router.currentRoute.value.fullPath, committed)
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }])
  assert.equal(buttons(f.root, '继续处理').length, 50)
  assert.match(text(f.root), /共 51 个任务/)
  assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
  assert.equal(f.notices.length, 1)
  rejectNext = false
  publicPageButton(f.root, '下一页'); await routeRenderBarrier()
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }])
  assert.match(taskIdentityText(f.root), /任务 #51/)
})

test('task position navigation-inflight guards public refresh and paging while retaining the read cards', async t => {
  const guard = deferred(); let entered = false
  const f = await routeFixture(t, { beforeResolve(to) { if (to.query.page === '2') { entered = true; return guard.promise } } })
  f.pending.push(guard)
  publicPageButton(f.root, '下一页'); await routeRenderBarrier(); assert.equal(entered, true)
  assert.equal(buttons(f.root, '继续处理').length, 50)
  assert.match(text(f.root), /共 51 个任务/)
  assert.equal(dispatch(f.root, '刷新'), false)
  assert.equal(dispatchPaging(f.root, '下一页'), false)
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }])
  guard.resolve(true); await routeRenderBarrier()
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }, { page: 2, pageSize: 50 }])
  assert.match(taskIdentityText(f.root), /任务 #51/)
  assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
})

test('task position Router promise rejection preserves healthy data and the actual declared error', async t => {
  const f = await routeFixture(t, { beforeResolve(to) { if (to.query.page === '2') throw new Error('本次任务页无法切换，请重试') } })
  const committed = f.router.currentRoute.value.fullPath
  publicPageButton(f.root, '下一页'); await routeRenderBarrier()
  assert.equal(f.router.currentRoute.value.fullPath, committed)
  assert.deepEqual(f.requests, [{ page: 1, pageSize: 50 }])
  assert.equal(buttons(f.root, '继续处理').length, 50)
  assert.match(text(f.root), /共 51 个任务/)
  assert.deepEqual(f.notices, ['本次任务页无法切换，请重试'])
  assert.equal(f.routerErrors.length, 1)
  assert.equal(buttons(f.root, '刷新')[0].props.disabled, false)
})
