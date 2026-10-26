import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { parse } from '@vue/compiler-sfc'
import { installDirtyFormGuard } from '../src/router/dirtyFormGuard.js'

test('new academic term inputs use one authoritative guard and retain dirty on cancel or cancelled navigation', async () => {
  const previous = { window: globalThis.window, document: globalThis.document, Element: globalThis.Element }
  let before, after, input, unload, confirmCount = 0, accept = false
  const from = { name: 'aa-term-new', path: '/admin/academic-affairs/terms/new', fullPath: '/admin/academic-affairs/terms/new' }
  const to = { name: 'aa-terms', path: '/admin/academic-affairs/terms', fullPath: '/admin/academic-affairs/terms' }
  globalThis.Element = class { matches() { return true } closest() { return null } }
  globalThis.window = { addEventListener(name, fn) { if (name === 'beforeunload') unload = fn }, removeEventListener() {} }
  globalThis.document = { addEventListener(name, fn) { if (name === 'input') input = fn }, removeEventListener() {} }
  const router = { currentRoute: { value: from }, beforeEach(fn) { before = fn }, beforeResolve(fn) { this.resolveGuard = fn; return () => { if (this.resolveGuard === fn) this.resolveGuard = null } }, afterEach(fn) { after = fn } }
  let dispose
  try {
    dispose = installDirtyFormGuard(router)
    const guard = window.__SAAS_DIRTY_FORM_GUARD__
    guard.registerConfirmation(() => { confirmCount++; return accept })
    assert.equal(guard.handlesRoute(from), true)
    assert.equal(guard.handlesRoute({ name: 'aa-term-detail' }), true)
    assert.equal(await before(to, from), true)
    input({ isTrusted: true, target: new Element() })
    assert.equal(await before(to, from), false)
    assert.equal(guard.isDirty(), true)
    let prevented = false; unload({ preventDefault() { prevented = true } }); assert.equal(prevented, true)
    accept = true; assert.equal(await before(to, from), true)
    after(to, from, new Error('navigation rejected')); assert.equal(guard.isDirty(), true)
    assert.equal(await before(to, from), true); after(to, from); assert.equal(guard.isDirty(), false)
    assert.equal(confirmCount, 3)
  } finally {
    dispose?.()
    for (const [key, value] of Object.entries(previous)) { if (value === undefined) delete globalThis[key]; else globalThis[key] = value }
  }
})

function page(response) {
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaTermFormView.vue', import.meta.url), 'utf8').split('<script>')[1].split('</script>')[0].replace(/^import .*$/gm, '').replace('export default', 'globalThis.options =')
  const calls = []
  const sandbox = { ModulePageShell: {}, AppButton: {}, AppSectionCard: {}, AppSelect: {}, academicAffairsApi: { createTerm: response }, toast: { success: () => calls.push('success'), error: () => calls.push('error') }, window: { __SAAS_DIRTY_FORM_GUARD__: { markSaved: () => calls.push('saved') } } }
  vm.runInNewContext(source, sandbox)
  const ctx = { ...sandbox.options.data(), ...sandbox.options.methods, canManage: true, validate: () => true, contextKey: () => 'A', $route: { query: {} }, $router: { push: () => calls.push('navigate') } }
  ctx.form.yearCode = '2027-2028'
  return { ctx, calls }
}

test('real successful create acknowledgement clears dirty before detail navigation', async () => {
  const { ctx, calls } = page(async () => ({ code: 0, data: { termId: '9' } }))
  await ctx.submit()
  assert.deepEqual(calls, ['saved', 'success', 'navigate'])
})

test('rejected create preserves dirty and inputs', async () => {
  const { ctx, calls } = page(async () => ({ code: 409001, message: '该学年学期已存在' }))
  await ctx.submit()
  assert.deepEqual(calls, ['error']); assert.equal(ctx.form.yearCode, '2027-2028')
})

test('late successful response after context changes cannot clear the current form guard', async () => {
  let resolve
  const { ctx, calls } = page(() => new Promise(yes => { resolve = yes }))
  const pending = ctx.submit(); ctx.contextKey = () => 'B'; resolve({ code: 0, data: { termId: '9' } }); await pending
  assert.deepEqual(calls, [])
})


test('all term fields share a native pending lock which releases after rejected save without losing draft', async () => {
  const { descriptor } = parse(fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaTermFormView.vue', import.meta.url), 'utf8'))
  const fields = []
  function visit(node, lock) {
    if (node.type === 1 && node.tag === 'fieldset') lock = node.props.find(p => p.type === 7 && p.name === 'bind' && p.arg?.content === 'disabled')?.exp?.content
    if (node.type === 1 && ['input', 'AppSelect'].includes(node.tag)) fields.push(lock)
    for (const child of node.children || []) visit(child, lock)
  }
  visit(descriptor.template.ast)
  assert.equal(fields.length, 7)
  assert.ok(fields.every(Boolean), 'every native input and select must inherit a disabled fieldset')
  let finish, requests = 0
  const { ctx, calls } = page(() => { requests++; return new Promise(resolve => { finish = resolve }) })
  ctx.form.termName = '保留的草稿'
  const locks = () => fields.map(expression => vm.runInNewContext(expression, ctx))
  assert.ok(locks().every(value => value === false))
  const pending = ctx.submit()
  assert.ok(locks().every(value => value === true))
  await ctx.submit(); assert.equal(requests, 1)
  finish({ code: 409001, message: '测试拒绝' }); await pending
  assert.ok(locks().every(value => value === false))
  assert.equal(ctx.form.termName, '保留的草稿')
  assert.deepEqual(calls, ['error'])
})


function detailPage(update) {
  const source = parse(fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaTermDetailView.vue', import.meta.url), 'utf8')).descriptor.script.content
    .replace(/^import .*$/gm, '').replace(/components: \{[\s\S]*?\},/, 'components: {},').replace('export default', 'globalThis.options =')
  const calls = []
  const sandbox = { termApi: { update }, formatDateTime: () => '', toast: { success: () => calls.push('success'), error: () => calls.push('error') }, window: { __SAAS_DIRTY_FORM_GUARD__: { markSaved: () => calls.push('saved') } } }
  vm.runInNewContext(source, sandbox)
  const ctx = { ...sandbox.options.data(), ...sandbox.options.methods, canEditName: true, previewCurrent: true, preview: { canSave: true }, termId: '3', contextKey: () => 'A', detail: { version: 0 } }
  ctx.form.termName = '未保存名称'
  return { ctx, calls }
}

test('detail acknowledgement hydrates returned values before clearing dirty', async () => {
  const { ctx, calls } = detailPage(async () => ({ code: 0, data: { termId: '3', termName: '已保存名称', version: 1 } }))
  const hydrate = ctx.hydrateForm
  ctx.hydrateForm = function (value) { hydrate.call(this, value); calls.push('hydrated') }
  await ctx.save()
  assert.deepEqual(calls, ['success', 'hydrated', 'saved'])
  assert.equal(ctx.form.termName, '已保存名称')
})

test('detail failed or late acknowledgement cannot clear dirty or replace input', async () => {
  const rejected = detailPage(async () => ({ code: 409001, message: '版本冲突' }))
  await rejected.ctx.save(); assert.deepEqual(rejected.calls, ['error']); assert.equal(rejected.ctx.form.termName, '未保存名称')
  for (const change of [ctx => { ctx.contextKey = () => 'B' }, ctx => { ctx.termId = '4' }]) {
    let finish
    const { ctx, calls } = detailPage(() => new Promise(resolve => { finish = resolve }))
    const pending = ctx.save(); change(ctx); finish({ code: 0, data: { termName: '迟到名称' } }); await pending
    assert.deepEqual(calls, []); assert.equal(ctx.form.termName, '未保存名称')
  }
})

test('unconfirmed create acknowledgement preserves the draft without saved, success, or detail navigation', async () => {
  const { ctx, calls } = page(async () => ({ code: 0, data: {} }))
  ctx.form.termName = '等待确认的学期草稿'
  ctx.form.startDate = '2028-02-01'
  ctx.form.endDate = '2028-06-30'
  ctx.form.teachingWeeks = 17
  ctx.form.examWeekStart = 16
  const draft = { ...ctx.form }
  await ctx.submit()
  assert.deepEqual({ ...ctx.form }, draft)
  assert.equal(ctx.submitting, false)
  assert.equal(calls.includes('saved'), false, 'an acknowledgement without termId must not clear dirty')
  assert.equal(calls.includes('success'), false, 'an unconfirmed result must not announce success')
  assert.equal(calls.includes('navigate'), false, 'an unconfirmed result must not navigate to an unknown term')
})

test('malformed create acknowledgements release the lock and retain every input and field error', async () => {
  const invalidData = [undefined, null, {}, [], '9', 9, false,
    { termId: undefined }, { termId: null }, { termId: '' }, { termId: ' \t\n ' },
    { termId: 9 }, { termId: false }, { termId: [] }, { termId: {} }]
  for (const data of invalidData) {
    let requests = 0
    const { ctx, calls } = page(async () => { requests++; return { code: 0, data } })
    Object.assign(ctx.form, { termNo: 2, termName: '等待核对的草稿', startDate: '2028-02-01', endDate: '2028-06-30', teachingWeeks: 17, examWeekStart: 16 })
    ctx.errors = { termName: '保留的字段提示' }
    const draft = { ...ctx.form }
    const errors = ctx.errors
    await ctx.submit()
    assert.equal(requests, 1, 'an unconfirmed result must not automatically retry creation')
    assert.deepEqual(calls, ['error'])
    assert.deepEqual({ ...ctx.form }, draft)
    assert.equal(ctx.errors, errors)
    assert.equal(ctx.submitting, false)
  }
})

test('thin valid create acknowledgements preserve literal IDs and the existing return token', async () => {
  for (const termId of ['9', 'new-term', ' new-term ']) {
    const { ctx, calls } = page(async () => ({ code: 0, data: { termId } }))
    ctx.$route.query.returnToken = 'existing-local-return-token'
    const destinations = []
    ctx.$router.push = destination => { destinations.push(destination); calls.push('navigate') }
    await ctx.submit()
    assert.deepEqual(calls, ['saved', 'success', 'navigate'])
    assert.equal(destinations.length, 1)
    assert.equal(destinations[0].name, 'aa-term-detail')
    assert.equal(destinations[0].params.termId, termId)
    assert.equal(destinations[0].query.returnToken, 'existing-local-return-token')
  }
})

test('late malformed or valid create acknowledgements cannot change a different current context', async () => {
  for (const data of [{}, null, { termId: 'new-term' }]) {
    let finish
    const { ctx, calls } = page(() => new Promise(resolve => { finish = resolve }))
    const pending = ctx.submit()
    ctx.contextKey = () => 'different-current-context'
    ctx.form.termName = '新上下文当前输入'
    const errors = ctx.errors = { termName: '新上下文字段提示' }
    finish({ code: 0, data })
    await pending
    assert.deepEqual(calls, [])
    assert.equal(ctx.form.termName, '新上下文当前输入')
    assert.equal(ctx.errors, errors)
  }
})


test('unconfirmed detail update acknowledgement preserves the draft and baseline without saved or success', async () => {
  const { ctx, calls } = detailPage(async () => ({ code: 0, data: {} }))
  ctx.baselineSignature = 'authoritative-before-update-baseline'
  ctx.recoveryError = '保留的核对提示'
  const draft = { ...ctx.form }
  const detail = ctx.detail
  const baseline = ctx.baselineSignature
  await ctx.save()
  assert.equal(ctx.form.termName, draft.termName, 'an unconfirmed update must retain the unsaved name')
  assert.deepEqual({ ...ctx.form }, draft)
  assert.equal(ctx.detail, detail)
  assert.equal(ctx.baselineSignature, baseline)
  assert.equal(ctx.recoveryError, '保留的核对提示')
  assert.equal(ctx.saving, false)
  assert.equal(calls.includes('saved'), false, 'an unconfirmed update must not clear dirty')
  assert.equal(calls.includes('success'), false, 'an unconfirmed update must not announce saved')
})

test('malformed primary detail update acknowledgements preserve draft and recovery state without retry', async () => {
  const valid = { termId: '3', termName: '正式回执名称', version: 1 }
  const invalid = [undefined, null, {}, [], '3', 3,
    { ...valid, termId: undefined }, { ...valid, termId: null }, { ...valid, termId: '' },
    { ...valid, termId: ' ' }, { ...valid, termId: '4' }, { ...valid, termId: 3 },
    { ...valid, termId: [] }, { ...valid, termId: {} },
    { ...valid, termName: undefined }, { ...valid, termName: null }, { ...valid, termName: [] },
    { ...valid, version: undefined }, { ...valid, version: null }, { ...valid, version: '1' },
    { ...valid, version: -1 }, { ...valid, version: 1.5 }]
  for (const data of invalid) {
    let requests = 0
    const { ctx, calls } = detailPage(async () => { requests++; return { code: 0, data } })
    const form = ctx.form, detail = ctx.detail
    const comparison = ctx.recoveryComparison = [{ field: 'termName', retained: '未保存名称' }]
    ctx.baselineSignature = 'opaque authoritative baseline, not JSON'
    ctx.recoveryError = '保留的核对提示'
    ctx.previewSignature = 'old-confirmation'
    await ctx.save()
    assert.equal(requests, 1)
    assert.deepEqual(calls, ['error'])
    assert.equal(ctx.form, form)
    assert.equal(ctx.form.termName, '未保存名称')
    assert.equal(ctx.detail, detail)
    assert.equal(ctx.baselineSignature, 'opaque authoritative baseline, not JSON')
    assert.equal(ctx.recoveryComparison, comparison)
    assert.equal(ctx.recoveryError, '保留的核对提示')
    assert.equal(ctx.versionConflict, false)
    assert.equal(ctx.saving, false)
    assert.equal(ctx.previewSignature, '')
    assert.equal(Object.keys(ctx.preview).length, 0)
  }
})

test('detail update optional fields may be omitted only when both submitted and original values are empty', async () => {
  const values = { startDate: '2030-09-01', endDate: '2031-01-31', teachingWeeks: 17, examWeekStart: 16 }
  for (const field of Object.keys(values)) {
    for (const previousNonempty of [false, true]) {
      const { ctx, calls } = detailPage(async () => ({ code: 0, data: { termId: '3', termName: '正式名称', version: 1 } }))
      if (previousNonempty) {
        ctx.detail[field] = values[field]
        ctx.form[field] = ['startDate', 'endDate'].includes(field) ? '' : null
      } else ctx.form[field] = values[field]
      const form = ctx.form, detail = ctx.detail
      const baseline = ctx.baselineSignature = 'baseline before optional omission'
      await ctx.save()
      assert.deepEqual(calls, ['error'], field + (previousNonempty ? ' cannot omit a cleared original value' : ' cannot omit a populated submitted value'))
      assert.equal(ctx.form, form)
      assert.equal(ctx.detail, detail)
      assert.equal(ctx.baselineSignature, baseline)
      assert.equal(ctx.form[field], previousNonempty ? (['startDate', 'endDate'].includes(field) ? '' : null) : values[field])
    }
    for (const value of [undefined, {}, [], true, ...(['startDate', 'endDate'].includes(field) ? [17] : ['17', 1.5])]) {
      const { ctx, calls } = detailPage(async () => ({ code: 0, data: { termId: '3', termName: '正式名称', version: 1, [field]: value } }))
      const form = ctx.form, detail = ctx.detail
      await ctx.save()
      assert.deepEqual(calls, ['error'], field + ' must not accept an undefined or wrong-type present field')
      assert.equal(ctx.form, form)
      assert.equal(ctx.detail, detail)
    }
  }
})

test('thin empty, explicit null, normalized full and same-version detail acknowledgements remain valid', async () => {
  const responses = [
    { termId: '3', termName: '薄回执名称', version: 1 },
    { termId: '3', termName: '无变更同版本名称', version: 0 },
    { termId: '3', termName: '', version: 1, startDate: null, endDate: null, teachingWeeks: null, examWeekStart: null },
    { termId: '3', termName: '正式完整名称', version: 1, startDate: '2030-09-01T00:00:00Z', endDate: '2031-01-31T23:59:59.999999Z', teachingWeeks: 17, examWeekStart: 16 }
  ]
  for (const data of responses) {
    const { ctx, calls } = detailPage(async () => ({ code: 0, data }))
    const hydrate = ctx.hydrateForm
    ctx.hydrateForm = function (value) { hydrate.call(this, value); calls.push('hydrated') }
    await ctx.save()
    assert.deepEqual(calls, ['success', 'hydrated', 'saved'])
    assert.equal(ctx.detail, data)
    assert.equal(ctx.form.termName, data.termName)
    assert.equal(ctx.form.startDate, (data.startDate || '').slice(0, 10))
    assert.equal(ctx.form.endDate, (data.endDate || '').slice(0, 10))
    assert.equal(ctx.form.teachingWeeks, data.teachingWeeks ?? null)
    assert.equal(ctx.form.examWeekStart, data.examWeekStart ?? null)
    assert.equal(ctx.saving, false)
  }
})

test('late malformed or valid detail acknowledgements cannot mutate a changed context or term draft', async () => {
  for (const data of [{}, null, { termId: '3', termName: '迟到正式名称', version: 1 }]) {
    for (const change of [ctx => { ctx.contextKey = () => 'different-current-context' }, ctx => { ctx.termId = '4' }]) {
      let finish
      const { ctx, calls } = detailPage(() => new Promise(resolve => { finish = resolve }))
      const pending = ctx.save()
      change(ctx)
      ctx.form.termName = '新上下文当前草稿'
      const form = ctx.form, detail = ctx.detail
      ctx.baselineSignature = 'new current baseline'
      ctx.recoveryError = '新上下文提示'
      finish({ code: 0, data })
      await pending
      assert.deepEqual(calls, [])
      assert.equal(ctx.form, form)
      assert.equal(ctx.form.termName, '新上下文当前草稿')
      assert.equal(ctx.detail, detail)
      assert.equal(ctx.baselineSignature, 'new current baseline')
      assert.equal(ctx.recoveryError, '新上下文提示')
    }
  }
})

test('canonical loaded term identity confirms a valid update from an accepted noncanonical route spelling', async () => {
  const { ctx, calls } = detailPage(async () => ({ code: 0, data: { termId: '3', termName: '已确认名称', version: 1 } }))
  ctx.termId = '003'
  ctx.detail.termId = '3'
  await ctx.save()
  assert.equal(ctx.form.termName, '已确认名称', 'the canonical ID loaded by the server must confirm the valid update')
  assert.deepEqual(calls, ['success', 'saved'])
  assert.equal(ctx.detail.termId, '3')
})

test('canonical loaded term identity still rejects an acknowledgement for another term', async () => {
  const { ctx, calls } = detailPage(async () => ({ code: 0, data: { termId: '4', termName: '另一对象名称', version: 1 } }))
  ctx.termId = '003'
  ctx.detail.termId = '3'
  const form = ctx.form, detail = ctx.detail
  ctx.baselineSignature = 'original canonical object baseline'
  await ctx.save()
  assert.deepEqual(calls, ['error'])
  assert.equal(ctx.form, form)
  assert.equal(ctx.form.termName, '未保存名称')
  assert.equal(ctx.detail, detail)
  assert.equal(ctx.baselineSignature, 'original canonical object baseline')
  assert.equal(ctx.saving, false)
})

test('canonical acknowledgement ownership cannot bypass the raw route change guard', async () => {
  let finish
  const { ctx, calls } = detailPage(() => new Promise(resolve => { finish = resolve }))
  ctx.termId = '003'
  ctx.detail.termId = '3'
  const pending = ctx.save()
  ctx.termId = '004'
  ctx.form.termName = '新路由当前草稿'
  const form = ctx.form, detail = ctx.detail
  finish({ code: 0, data: { termId: '3', termName: '迟到对象名称', version: 1 } })
  await pending
  assert.deepEqual(calls, [])
  assert.equal(ctx.form, form)
  assert.equal(ctx.form.termName, '新路由当前草稿')
  assert.equal(ctx.detail, detail)
})

// Actual compiled public-control regressions. Synthetic contexts and published markDirty
// are declared unit inputs; this renderer is not a trusted browser/HTTP/IAM proof.
import { createRequire as ownedConfirmCreateRequire } from 'node:module'
import { setImmediate as ownedConfirmSetImmediate, setTimeout as ownedConfirmSetTimeout, clearTimeout as ownedConfirmClearTimeout } from 'node:timers'
import { compileTemplate as ownedConfirmCompileTemplate } from '@vue/compiler-sfc'
import * as ownedConfirmGate from '../src/security/permissionGate.js'
import { academicIdentity as ownedConfirmAcademicIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import { matchPermission as ownedConfirmMatchPermission } from '../src/config/navPlan.js'
import * as ownedConfirmDialog from '../src/services/systemDialog.js'

const ownedConfirmRequire = ownedConfirmCreateRequire(import.meta.url)
const ownedConfirmVue = ownedConfirmRequire('vue')
const ownedConfirmRouter = ownedConfirmRequire('vue-router')
const ownedConfirmRead = relative => fs.readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')
const ownedConfirmH = ownedConfirmVue.h
const ownedConfirmDeferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes }); return { promise, resolve } }
const ownedConfirmTick = async () => { await new Promise(resolve => ownedConfirmSetImmediate(resolve)); await ownedConfirmVue.nextTick() }
async function ownedConfirmBounded(promise) {
  let timer
  try { return await Promise.race([promise, new Promise((_resolve, reject) => { timer = ownedConfirmSetTimeout(() => reject(new Error('真实确认测试阶段未到达')), 3000) })]) }
  finally { ownedConfirmClearTimeout(timer) }
}
function ownedConfirmCompile(relative, bindings = {}) {
  const { descriptor, errors } = parse(ownedConfirmRead(relative), { filename: relative })
  assert.deepEqual(errors, [])
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const component = new Function(...Object.keys(bindings), `${script}\nreturn component`)(...Object.values(bindings))
  const template = ownedConfirmCompileTemplate({ source: descriptor.template.content, filename: relative, id: relative, compilerOptions: { mode: 'function' } })
  assert.deepEqual(template.errors, [])
  component.render = new Function('Vue', template.code)(ownedConfirmVue)
  return component
}
const ownedConfirmVisual = name => ({ name, inheritAttrs: false, setup(_props, { slots }) { return () => ownedConfirmH('section', {}, [slots.actions?.(), slots.default?.()]) } })
const ownedConfirmNode = (type, text = '') => ({ type, tagName: type.toUpperCase(), text, value: '', props: {}, children: [], parent: null, listeners: {},
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) },
  removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) },
  getRootNode() { return globalThis.document } })
const ownedConfirmWalk = node => [node, ...node.children.flatMap(ownedConfirmWalk)]
const ownedConfirmText = node => node.type === '#comment' ? '' : node.text + node.children.map(ownedConfirmText).join('')
const OWNED_CONFIRM_SOURCE = '/admin/academic-affairs/terms/new'
const OWNED_CONFIRM_TARGET = '/admin/academic-affairs/terms'
const OWNED_CONFIRM_OVERVIEW = '/admin/academic-affairs'
async function ownedConfirmationFixture(t, { start = OWNED_CONFIRM_SOURCE, declaredConfirm = ownedConfirmDialog.systemConfirm } = {}) {
  const previous = Object.fromEntries(['window', 'document', 'Document', 'ShadowRoot'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const install = (key, value) => Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  class DeclaredDocumentHost { constructor() { this.listeners = {}; this.activeElement = null } addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) } removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) } }
  install('Document', DeclaredDocumentHost); install('ShadowRoot', class DeclaredShadowRootHost {})
  install('document', new DeclaredDocumentHost())
  const windowListeners = {}
  install('window', { addEventListener(name, fn) { (windowListeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { windowListeners[name] = (windowListeners[name] || []).filter(value => value !== fn) } })
  const patterns = ['academicAffairs.term.view', 'academicAffairs.term.manage', 'academicAffairs.dashboard.view']
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_USER', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_CONTEXT' }
  const makeContext = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionPatterns: [...patterns], permissionVersion: 1 })
  const state = ownedConfirmVue.reactive({ ctx: makeContext('DECLARED_SCOPE_A') })
  const warnings = [], errors = [], transitions = [], mounts = [], unmounts = []
  const prohibited = () => { throw new Error('此确认回归禁止保存/创建/业务API') }
  const Button = ownedConfirmCompile('components/ui/AppButton.vue')
  const Form = ownedConfirmCompile('modules/academicAffairs/views/AaTermFormView.vue', {
    ModulePageShell: ownedConfirmVisual('DeclaredUnrelatedShellVisual'), AppButton: Button,
    AppSectionCard: ownedConfirmVisual('DeclaredUnrelatedCardVisual'), AppSelect: ownedConfirmVisual('DeclaredUnusedTermNumberVisual'),
    academicAffairsApi: { createTerm: prohibited }, toast: { success: prohibited, error: prohibited }, matchPermission: ownedConfirmMatchPermission,
    systemConfirm: declaredConfirm
  })
  const renderer = ownedConfirmVue.createRenderer({ createElement: tag => ownedConfirmNode(tag), createText: value => ownedConfirmNode('#text', value), createComment: value => ownedConfirmNode('#comment', value),
    setText(node, value) { node.text = value }, setElementText(node, value) { node.text = value; node.children = [] },
    parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    patchProp(node, key, _old, value) { node.props[key] = value },
    insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
    remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } }
  })
  const Body = { render: () => ownedConfirmH('p', '声明的只读目的页，无API') }
  const Parent = { render() { return ownedConfirmH(ownedConfirmRouter.RouterView, null, { default: ({ Component }) => {
    const owner = state.ctx?.ctxKey
    return state.ctx && Component ? ownedConfirmH(Component, { key: owner, ctx: state.ctx,
      onVnodeMounted: () => mounts.push(owner), onVnodeUnmounted: () => unmounts.push(owner) }) : ownedConfirmH('p', '声明上下文读取中，无API')
  } }) } }
  const router = ownedConfirmRouter.createRouter({ history: ownedConfirmRouter.createMemoryHistory(), routes: [{ path: OWNED_CONFIRM_OVERVIEW, component: Parent, meta: { moduleCode: 'ACADEMIC_AFFAIRS' }, children: [
    { path: '', name: 'aa-dashboard', component: Body, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.dashboard.view' } },
    { path: 'terms/new', name: 'aa-term-new', component: Form, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.manage' } },
    { path: 'terms', name: 'aa-terms', component: Body, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.view' } }
  ] }] })
  ownedConfirmGate.clearPermissionPatterns(); ownedConfirmGate.setModuleEntitlements(['academicAffairs']); ownedConfirmGate.setPermissionPatterns(patterns)
  let queuedObserver = null
  const observedTo = new WeakMap()
  const removePermission = router.beforeEach(to => {
    assert.equal(ownedConfirmGate.canEnterRoute(to.meta), true)
    if (queuedObserver) { const observer = queuedObserver; queuedObserver = null; observer.to = to; observedTo.set(to, observer); observer.entered.resolve(to) }
    return true
  })
  const disposeDirty = installDirtyFormGuard(router)
  const removeAfter = router.afterEach((to, from, failure) => {
    transitions.push({ to: to.fullPath, from: from.fullPath, failureType: failure?.type ?? null })
    const observer = observedTo.get(to)
    if (observer) { observer.result = { to, from, failure }; observer.completed.resolve(observer.result) }
  })
  const removeError = router.onError(error => errors.push({ source: 'router', message: error.message }))
  let app, stopped = false
  t.after(async () => {
    ownedConfirmDialog.finishSystemDialog(false)
    if (app && !stopped) { app.unmount(); stopped = true }
    await ownedConfirmTick(); disposeDirty(); removePermission(); removeAfter(); removeError(); ownedConfirmGate.clearPermissionPatterns()
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    assert.deepEqual(warnings, []); assert.deepEqual(errors, []); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  })
  await router.push(start); await router.isReady()
  const root = ownedConfirmNode('root')
  const Host = { setup() { ownedConfirmVue.provide('academicFlow', { identity: () => ownedConfirmAcademicIdentity(claims, state.ctx || {}) }); return () => ownedConfirmH('main', {}, [
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: OWNED_CONFIRM_TARGET }, { default: () => '声明的公开外部学期列表链接' }), ownedConfirmH(ownedConfirmRouter.RouterView)
  ]) } }
  app = renderer.createApp(Host); app.use(router)
  app.config.warnHandler = warning => warnings.push(String(warning))
  app.config.errorHandler = error => errors.push({ source: 'vue', message: error.message })
  app.mount(root); await ownedConfirmTick()
  const publicInput = () => { const fields = ownedConfirmWalk(root).filter(node => node.type === 'input' && node.props.id === 'aa-term-name'); assert.equal(fields.length, 1); assert.equal(!!fields[0].props.disabled, false); return fields[0] }
  const beginNavigation = () => { assert.equal(queuedObserver, null); const observer = { entered: ownedConfirmDeferred(), completed: ownedConfirmDeferred(), to: null, result: null }; queuedObserver = observer; return observer }
  const dispatch = node => { assert.equal(!!node.props.disabled, false); const event = { type: 'click', target: node, currentTarget: node }; const handlers = node.props.onClick; assert.ok(handlers); for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event) }
  const clickReturn = async () => { const buttons = ownedConfirmWalk(root).filter(node => node.type === 'button' && ownedConfirmText(node) === '返回列表'); assert.equal(buttons.length, 1); const observer = beginNavigation(); dispatch(buttons[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const clickExternal = async () => { const links = ownedConfirmWalk(root).filter(node => node.type === 'a' && ownedConfirmText(node) === '声明的公开外部学期列表链接'); assert.equal(links.length, 1); const observer = beginNavigation(); dispatch(links[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const waitDialog = async () => { await ownedConfirmBounded((async () => { while (!ownedConfirmDialog.systemDialogState.visible) await ownedConfirmTick() })()); assert.equal(ownedConfirmDialog.systemDialogState.title, '确认离开当前页面'); assert.equal(ownedConfirmDialog.systemDialogState.confirmText, '放弃修改并离开') }
  const fillName = async value => { const field = publicInput(); assert.ok(field.listeners.input?.length); field.value = value; for (const listener of field.listeners.input) listener({ type: 'input', target: field }); window.__SAAS_DIRTY_FORM_GUARD__.markDirty(); await ownedConfirmTick(); assert.equal(publicInput().value, value); assert.equal(window.__SAAS_DIRTY_FORM_GUARD__.isDirty(), true) }
  const replaceOwner = async () => { state.ctx = null; await ownedConfirmTick(); assert.ok(unmounts.includes('DECLARED_SCOPE_A')); state.ctx = makeContext('DECLARED_SCOPE_B'); await ownedConfirmTick(); assert.ok(mounts.includes('DECLARED_SCOPE_B')) }
  const settle = async (observer, accepted) => { ownedConfirmDialog.finishSystemDialog(accepted); const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result }
  return { router, root, state, warnings, errors, transitions, mounts, unmounts, publicInput, clickReturn, clickExternal, waitDialog, fillName, replaceOwner, settle,
    guard: window.__SAAS_DIRTY_FORM_GUARD__, finish: ownedConfirmDialog.finishSystemDialog, done: async observer => { const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result } }
}

test('owned term confirmation leaves a clean form without opening a dialog', async t => {
  const fixture = await ownedConfirmationFixture(t)
  const navigation = await fixture.clickReturn(); const result = await fixture.done(navigation)
  assert.equal(result.failure, undefined); assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false); assert.equal(fixture.guard.isDirty(), false)
})

test('owned term confirmation does not intercept a non-term source route', async t => {
  const fixture = await ownedConfirmationFixture(t, { start: OWNED_CONFIRM_OVERVIEW })
  fixture.guard.markDirty(); assert.equal(fixture.guard.isDirty(), false)
  const navigation = await fixture.clickExternal(); const result = await fixture.done(navigation)
  assert.equal(result.failure, undefined); assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
})

test('owned term confirmation cancel preserves the real input and dirty state', async t => {
  const fixture = await ownedConfirmationFixture(t); await fixture.fillName('保留原学期草稿')
  const navigation = await fixture.clickReturn(); await fixture.waitDialog(); const result = await fixture.settle(navigation, false)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE); assert.equal(fixture.publicInput().value, '保留原学期草稿'); assert.equal(fixture.guard.isDirty(), true)
})

test('owned term confirmation healthy accept keeps the original successful discard behavior', async t => {
  const fixture = await ownedConfirmationFixture(t); await fixture.fillName('明确丢弃的学期草稿')
  const navigation = await fixture.clickReturn(); await fixture.waitDialog(); const result = await fixture.settle(navigation, true)
  assert.equal(result.failure, undefined); assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET); assert.equal(fixture.guard.isDirty(), false)
})

test('owned term confirmation rejects a stale positive after same instance academic context changes', async t => {
  const fixture = await ownedConfirmationFixture(t); await fixture.fillName('旧管理范围草稿')
  const navigation = await fixture.clickReturn(); await fixture.waitDialog()
  fixture.state.ctx.permissionVersion = 2; await ownedConfirmTick(); await fixture.fillName('新管理范围草稿')
  const result = await fixture.settle(navigation, true)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE); assert.equal(fixture.publicInput().value, '新管理范围草稿'); assert.equal(fixture.guard.isDirty(), true)
})

test('owned term confirmation old unmounted scope cannot navigate or clear the new real form draft', async t => {
  const fixture = await ownedConfirmationFixture(t); await fixture.fillName('旧A学期草稿')
  const navigation = await fixture.clickReturn(); await fixture.waitDialog(); await fixture.replaceOwner(); await fixture.fillName('新B学期草稿')
  const result = await fixture.settle(navigation, true)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_SOURCE)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted); assert.equal(fixture.publicInput().value, '新B学期草稿'); assert.equal(fixture.guard.isDirty(), true)
})

test('owned term confirmation cleanup allows the new form genuine dialog and public navigation', async t => {
  const fixture = await ownedConfirmationFixture(t); await fixture.fillName('旧A等待确认')
  const oldNavigation = await fixture.clickReturn(); await fixture.waitDialog(); await fixture.replaceOwner(); await fixture.fillName('新B等待确认')
  const oldResult = await fixture.settle(oldNavigation, true); assert.equal(oldResult.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  const newNavigation = await fixture.clickReturn(); await fixture.waitDialog(); const newResult = await fixture.settle(newNavigation, true)
  assert.notEqual(oldNavigation.to, newNavigation.to); assert.equal(newResult.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET); assert.equal(fixture.guard.isDirty(), false)
})

test('owned term confirmation unmount removes only its handler and keeps a later published generic handler', async t => {
  const fixture = await ownedConfirmationFixture(t); await fixture.fillName('自有处理器卸载草稿')
  let calls = 0
  const removeGeneric = fixture.guard.registerConfirmation(() => { calls++; return false })
  fixture.state.ctx = null; await ownedConfirmTick()
  const navigation = await fixture.clickExternal(); const result = await fixture.done(navigation)
  assert.equal(calls, 1); assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE); assert.equal(fixture.guard.isDirty(), true)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false); removeGeneric()
})

test('owned term confirmation rejection reaches the original shared fail-closed catch', async t => {
  // Declared systemConfirm interface rejection, not a second fake live dialog or HTTP failure.
  const fixture = await ownedConfirmationFixture(t, { declaredConfirm: () => Promise.reject(new Error('DECLARED_CONFIRM_INTERFACE_REJECTION')) })
  await fixture.fillName('确认接口拒绝时保留草稿')
  const navigation = await fixture.clickReturn(); const result = await fixture.done(navigation)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE); assert.equal(fixture.guard.isDirty(), true)
  assert.equal(fixture.publicInput().value, '确认接口拒绝时保留草稿'); assert.deepEqual(fixture.errors, [])
})

test('owned term old dialog keeps Router cancellation8 after new public navigation commits through a declared generic confirmation handler', async t => {
  const fixture = await ownedConfirmationFixture(t); await fixture.fillName('旧A确认仍等待')
  const oldNavigation = await fixture.clickReturn(); await fixture.waitDialog(); await fixture.replaceOwner(); await fixture.fillName('新B明确允许丢弃的草稿')
  // Existing published generic handler contract; this is not a second systemDialog.
  let genericCalls = 0
  const removeGeneric = fixture.guard.registerConfirmation(() => { genericCalls++; return true })
  const newNavigation = await fixture.clickReturn(); const newResult = await fixture.done(newNavigation)
  assert.notEqual(oldNavigation.to, newNavigation.to); assert.equal(genericCalls, 1); assert.equal(newResult.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, true, 'Original actual single dialog is still pending')
  const oldResult = await fixture.settle(oldNavigation, true)
  assert.equal(oldResult.failure.type, ownedConfirmRouter.NavigationFailureType.cancelled)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET); assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_TARGET)
  removeGeneric()
})

// Detail-only owner-await regressions: actual route record reuse is distinct from scope remount.
import { formatDateTime as detailOwnedFormatDateTime } from '../src/utils/dateUtils.js'
import { presentAuditRecord as detailOwnedPresentAuditRecord, safeBusinessMessage as detailOwnedSafeBusinessMessage, safeEnumLabel as detailOwnedSafeEnumLabel } from '../src/utils/presentationSafety.js'

const DETAIL_OWNED_SOURCE3 = '/admin/academic-affairs/terms/3'
const DETAIL_OWNED_SOURCE4 = '/admin/academic-affairs/terms/4'
function detailOwnedWorkspace(id) {
  assert.ok(['3', '4'].includes(id))
  // Declared positive DTOs from workspace producer198-235 and saved termworkspace
  // name-only recovery contract. They are not existing live rows/authentication facts.
  const related = path => `${path}?termId=${id}`
  return {
    termId: id, yearCode: id === '3' ? '2030-2031' : '2031-2032', termNo: 1,
    termName: id === '3' ? '服务器名称' : '另一学期名称',
    startDate: id === '3' ? '2030-09-01T00:00:00' : '2031-09-01T00:00:00',
    endDate: id === '3' ? '2031-01-31T23:59:59' : '2032-01-31T23:59:59',
    teachingWeeks: 20, examWeekStart: null, isCurrent: false, status: 'PUBLISHED', version: 3,
    linkedData: {
      calendar: { count: 0, route: related('/admin/academic-affairs/calendar') },
      teachingTasks: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/teaching-tasks') },
      schedules: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/schedule') },
      exams: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/exam') },
      selections: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/selection') },
      grades: { count: 0, statusCounts: {}, route: related('/admin/academic-affairs/grade-overview') }
    },
    allowedActions: { editBasic: false, editNameOnly: true, publish: false, setCurrent: true, freeze: true, archive: false, viewImpact: true, hasLinkedBusiness: false },
    impactWarning: '当前尚无关联业务，草稿状态可维护基础时间轴。', timeline: [], archiveRoute: related('/admin/academic-affairs/archive/precheck')
  }
}
async function detailOwnedConfirmationFixture(t) {
  const previous = Object.fromEntries(['window', 'document', 'Document', 'ShadowRoot'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const install = (key, value) => Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  class DetailDocumentHost { constructor() { this.listeners = {}; this.activeElement = null } addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) } removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) } }
  install('Document', DetailDocumentHost); install('ShadowRoot', class DetailShadowRootHost {})
  install('document', new DetailDocumentHost())
  const windowListeners = {}
  install('window', { addEventListener(name, fn) { (windowListeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { windowListeners[name] = (windowListeners[name] || []).filter(value => value !== fn) } })
  const patterns = ['academicAffairs.term.view', 'academicAffairs.term.manage']
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_USER', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_CONTEXT' }
  const makeContext = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionPatterns: [...patterns], permissionVersion: 1 })
  const state = ownedConfirmVue.reactive({ ctx: makeContext('DECLARED_DETAIL_SCOPE_A') })
  const errors = [], warnings = [], transitions = [], reads = [], responses = [], detailMounts = [], detailUnmounts = [], detailUpdates = []
  const prohibited = () => { throw new Error('此详情确认回归禁止预览/保存/状态动作/业务请求') }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    reads.push({ path, method: options.method || 'GET' })
    if (path === '/academic-affairs/terms/current') return { termId: '1', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
    const match = /^\/academic-affairs\/terms\/(3|4)\/workspace$/.exec(path)
    assert.ok(match, 'Only the named current/workspace3/workspace4 transport reads are allowed')
    return detailOwnedWorkspace(match[1])
  }
  const detailAdapterSource = ownedConfirmRead('modules/academicAffairs/api/academic-affairs-term-detail.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ')
  const detailAdapter = new Function('request', `${detailAdapterSource}\nreturn academicAffairsTermDetailApi`)(request)
  const termApi = { ...detailAdapter, get(id) { return detailAdapter.get(id).then(response => { responses.push(structuredClone(response)); return response }) } }
  const academicAdapterSource = ownedConfirmRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const academicApi = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${academicAdapterSource}\nreturn academicAffairsApi`)(request, prohibited, prohibited, prohibited, prohibited, prohibited)
  const Button = ownedConfirmCompile('components/ui/AppButton.vue')
  const Detail = ownedConfirmCompile('modules/academicAffairs/views/AaTermDetailView.vue', {
    ModulePageShell: ownedConfirmVisual('DeclaredDetailShellVisual'), AppButton: Button,
    LoadingState: ownedConfirmVisual('DeclaredDetailLoadingVisual'), ErrorState: ownedConfirmVisual('DeclaredDetailErrorVisual'), EmptyState: ownedConfirmVisual('DeclaredDetailEmptyVisual'),
    AppSectionCard: ownedConfirmVisual('DeclaredDetailCardVisual'), AppStatusTag: ownedConfirmVisual('DeclaredDetailStatusVisual'), AppConfirmDialog: ownedConfirmVisual('DeclaredUnopenedDetailActionDialog'),
    academicAffairsApi: academicApi, termApi, toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission: ownedConfirmMatchPermission,
    formatDateTime: detailOwnedFormatDateTime, presentAuditRecord: detailOwnedPresentAuditRecord, safeBusinessMessage: detailOwnedSafeBusinessMessage, safeEnumLabel: detailOwnedSafeEnumLabel,
    systemConfirm: ownedConfirmDialog.systemConfirm
  })
  const renderer = ownedConfirmVue.createRenderer({ createElement: tag => ownedConfirmNode(tag), createText: value => ownedConfirmNode('#text', value), createComment: value => ownedConfirmNode('#comment', value),
    setText(node, value) { node.text = value }, setElementText(node, value) { node.text = value; node.children = [] },
    parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    patchProp(node, key, _old, value) { node.props[key] = value },
    insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
    remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } }
  })
  const Parent = { render() { return ownedConfirmH(ownedConfirmRouter.RouterView, null, { default: ({ Component }) => {
    const owner = state.ctx?.ctxKey
    return state.ctx && Component ? ownedConfirmH(Component, { key: owner, ctx: state.ctx,
      onVnodeMounted(vnode) { if (vnode.type?.name === 'AaTermDetailView') detailMounts.push({ owner, uid: vnode.component.uid }) },
      onVnodeUpdated(vnode) { if (vnode.type?.name === 'AaTermDetailView') detailUpdates.push({ owner, uid: vnode.component.uid, termId: String(router.currentRoute.value.params.termId || '') }) },
      onVnodeUnmounted(vnode) { if (vnode.type?.name === 'AaTermDetailView') detailUnmounts.push({ owner, uid: vnode.component.uid }) }
    }) : ownedConfirmH('p', '声明上下文读取中，无API')
  } }) } }
  const router = ownedConfirmRouter.createRouter({ history: ownedConfirmRouter.createMemoryHistory(), routes: [{ path: '/admin/academic-affairs', component: Parent, meta: { moduleCode: 'ACADEMIC_AFFAIRS' }, children: [
    { path: 'terms/:termId', name: 'aa-term-detail', component: Detail, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.view' } },
    { path: 'terms', name: 'aa-terms', component: { name: 'DeclaredDetailDestination', render: () => ownedConfirmH('p', '声明只读学期列表，无API') }, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.view' } }
  ] }] })
  ownedConfirmGate.clearPermissionPatterns(); ownedConfirmGate.setModuleEntitlements(['academicAffairs']); ownedConfirmGate.setPermissionPatterns(patterns)
  let queuedObserver = null
  const observedTo = new WeakMap()
  const removePermission = router.beforeEach(to => {
    assert.equal(ownedConfirmGate.canEnterRoute(to.meta), true)
    if (queuedObserver) { const observer = queuedObserver; queuedObserver = null; observer.to = to; observedTo.set(to, observer); observer.entered.resolve(to) }
    return true
  })
  const disposeDirty = installDirtyFormGuard(router)
  const removeAfter = router.afterEach((to, from, failure) => {
    transitions.push({ to: to.fullPath, from: from.fullPath, failureType: failure?.type ?? null })
    const observer = observedTo.get(to)
    if (observer) { observer.result = { to, from, failure }; observer.completed.resolve(observer.result) }
  })
  const removeError = router.onError(error => errors.push({ source: 'router', message: error.message }))
  let app, stopped = false
  t.after(async () => {
    ownedConfirmDialog.finishSystemDialog(false)
    if (app && !stopped) { app.unmount(); stopped = true }
    await ownedConfirmTick(); disposeDirty(); removePermission(); removeAfter(); removeError(); ownedConfirmGate.clearPermissionPatterns()
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  })
  await router.push(DETAIL_OWNED_SOURCE3); await router.isReady()
  const root = ownedConfirmNode('root')
  const Host = { setup() { ownedConfirmVue.provide('academicFlow', { identity: () => ownedConfirmAcademicIdentity(claims, state.ctx || {}), restorePosition() {} }); return () => ownedConfirmH('main', {}, [
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: DETAIL_OWNED_SOURCE4 }, { default: () => '声明的公开记录4链接' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: OWNED_CONFIRM_TARGET }, { default: () => '声明的公开详情外部列表链接' }), ownedConfirmH(ownedConfirmRouter.RouterView)
  ]) } }
  app = renderer.createApp(Host); app.use(router)
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ source: 'vue', message: error.message })
  app.mount(root); await ownedConfirmTick()
  const publicInput = () => { const inputs = ownedConfirmWalk(root).filter(node => node.type === 'input' && node.props.placeholder === '填写学校正式使用的学期名称'); assert.equal(inputs.length, 1); assert.equal(!!inputs[0].props.disabled, false); return inputs[0] }
  assert.equal(publicInput().value, detailOwnedWorkspace('3').termName)
  assert.deepEqual(responses.map(response => response.data), [detailOwnedWorkspace('3')]); assert.equal(reads.length, 2)
  const fillName = async value => {
    const input = publicInput(); assert.ok(input.listeners.input?.length); input.value = value
    const event = { type: 'input', target: input, currentTarget: input }
    for (const listener of input.listeners.input) listener(event)
    const handlers = input.props.onInput; assert.ok(handlers)
    for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event)
    // Published unit API declaration, not a forged trusted DOM event.
    window.__SAAS_DIRTY_FORM_GUARD__.markDirty(); await ownedConfirmTick()
    assert.equal(publicInput().value, value); assert.equal(window.__SAAS_DIRTY_FORM_GUARD__.isDirty(), true)
  }
  const beginNavigation = () => { assert.equal(queuedObserver, null); const observer = { entered: ownedConfirmDeferred(), completed: ownedConfirmDeferred(), to: null, result: null }; queuedObserver = observer; return observer }
  const dispatch = node => { assert.equal(!!node.props.disabled, false); const event = { type: 'click', target: node, currentTarget: node }; const handlers = node.props.onClick; assert.ok(handlers); for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event) }
  const click = async (tag, label) => { const nodes = ownedConfirmWalk(root).filter(node => node.type === tag && ownedConfirmText(node) === label); assert.equal(nodes.length, 1); const observer = beginNavigation(); dispatch(nodes[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const clickReturn = () => click('button', '返回学期列表')
  const clickRecord4 = () => click('a', '声明的公开记录4链接')
  const clickExternal = () => click('a', '声明的公开详情外部列表链接')
  const waitDialog = async () => { await ownedConfirmBounded((async () => { while (!ownedConfirmDialog.systemDialogState.visible) await ownedConfirmTick() })()); assert.equal(ownedConfirmDialog.systemDialogState.title, '确认离开当前页面'); assert.equal(ownedConfirmDialog.systemDialogState.confirmText, '放弃修改并离开') }
  const done = async observer => { const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result }
  const settle = async (observer, accepted) => { ownedConfirmDialog.finishSystemDialog(accepted); return done(observer) }
  const replaceOwner = async () => { state.ctx = null; await ownedConfirmTick(); assert.equal(detailUnmounts.length, 1); state.ctx = makeContext('DECLARED_DETAIL_SCOPE_B'); await ownedConfirmTick(); assert.equal(detailMounts.length, 2); assert.notEqual(detailMounts[0].uid, detailMounts[1].uid); assert.equal(publicInput().value, detailOwnedWorkspace('3').termName); assert.equal(reads.length, 4) }
  const assertRecord4Reuse = () => {
    assert.equal(state.ctx.ctxKey, 'DECLARED_DETAIL_SCOPE_A'); assert.equal(detailMounts.length, 1); assert.equal(detailUnmounts.length, 0)
    assert.equal(router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE4)
    const record4Updates = detailUpdates.filter(event => event.termId === '4')
    assert.ok(record4Updates.length > 0, 'Actual record4 VNode updated event occurred')
    assert.equal(record4Updates.at(-1).uid, detailMounts[0].uid, 'Current record4 VNode UID equals initial record3 UID')
    assert.deepEqual(responses.map(response => response.data), [detailOwnedWorkspace('3'), detailOwnedWorkspace('4')])
    assert.deepEqual(reads.map(row => row.path), ['/academic-affairs/terms/current', '/academic-affairs/terms/3/workspace', '/academic-affairs/terms/current', '/academic-affairs/terms/4/workspace'])
    assert.equal(publicInput().value, detailOwnedWorkspace('4').termName)
  }
  return { router, state, root, reads, responses, detailMounts, detailUnmounts, detailUpdates, publicInput, fillName, clickReturn, clickRecord4, clickExternal, waitDialog, done, settle, replaceOwner, assertRecord4Reuse,
    guard: window.__SAAS_DIRTY_FORM_GUARD__ }
}

test('detail owned confirmation clean record public return opens no dialog', async t => {
  const fixture = await detailOwnedConfirmationFixture(t)
  const navigation = await fixture.clickReturn(); const result = await fixture.done(navigation)
  assert.equal(result.failure, undefined); assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false); assert.equal(fixture.guard.isDirty(), false)
})

test('detail owned confirmation same record cancel preserves input and healthy accept discards normally', async t => {
  const fixture = await detailOwnedConfirmationFixture(t); await fixture.fillName('同记录未保存名称')
  const cancelled = await fixture.clickReturn(); await fixture.waitDialog(); const cancelResult = await fixture.settle(cancelled, false)
  assert.equal(cancelResult.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE3); assert.equal(fixture.publicInput().value, '同记录未保存名称'); assert.equal(fixture.guard.isDirty(), true)
  const accepted = await fixture.clickReturn(); await fixture.waitDialog(); const acceptResult = await fixture.settle(accepted, true)
  assert.notEqual(cancelled.to, accepted.to); assert.equal(acceptResult.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET); assert.equal(fixture.guard.isDirty(), false)
})

test('detail owned old unmounted positive keeps B draft and permits B genuine new confirmation', async t => {
  const fixture = await detailOwnedConfirmationFixture(t); await fixture.fillName('旧A名称草稿')
  const oldNavigation = await fixture.clickReturn(); await fixture.waitDialog(); await fixture.replaceOwner(); await fixture.fillName('新B名称草稿')
  const oldResult = await fixture.settle(oldNavigation, true)
  assert.equal(oldResult.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE3); assert.equal(fixture.router.options.history.location, DETAIL_OWNED_SOURCE3)
  assert.equal(fixture.publicInput().value, '新B名称草稿'); assert.equal(fixture.guard.isDirty(), true)
  const newCancelled = await fixture.clickReturn(); await fixture.waitDialog(); const cancelResult = await fixture.settle(newCancelled, false)
  assert.equal(cancelResult.failure.type, ownedConfirmRouter.NavigationFailureType.aborted); assert.equal(fixture.publicInput().value, '新B名称草稿'); assert.equal(fixture.guard.isDirty(), true)
  const newAccepted = await fixture.clickReturn(); await fixture.waitDialog(); const acceptResult = await fixture.settle(newAccepted, true)
  assert.notEqual(oldNavigation.to, newAccepted.to); assert.equal(acceptResult.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET); assert.equal(fixture.guard.isDirty(), false)
})

test('detail owned old unmounted negative keeps replacement scoped record draft', async t => {
  const fixture = await detailOwnedConfirmationFixture(t); await fixture.fillName('旧A等待取消')
  const navigation = await fixture.clickReturn(); await fixture.waitDialog(); await fixture.replaceOwner(); await fixture.fillName('新B不能被旧取消清掉')
  const result = await fixture.settle(navigation, false)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE3); assert.equal(fixture.publicInput().value, '新B不能被旧取消清掉'); assert.equal(fixture.guard.isDirty(), true)
})

test('detail owned positive invalidated by same-instance academic context does not navigate or clear new input', async t => {
  const fixture = await detailOwnedConfirmationFixture(t); const uid = fixture.detailMounts[0].uid
  await fixture.fillName('旧权限版本名称')
  const navigation = await fixture.clickReturn(); await fixture.waitDialog()
  const originalContext = fixture.state.ctx
  fixture.state.ctx = { ...fixture.state.ctx, permissionVersion: 2 }
  assert.notEqual(fixture.state.ctx, originalContext)
  assert.equal(fixture.state.ctx.ctxKey, originalContext.ctxKey)
  await ownedConfirmBounded((async () => { while (fixture.responses.length < 2) await ownedConfirmTick() })())
  await ownedConfirmTick()
  assert.deepEqual(fixture.responses.map(response => response.data), [detailOwnedWorkspace('3'), detailOwnedWorkspace('3')])
  assert.deepEqual(fixture.reads.map(row => row.path), ['/academic-affairs/terms/current', '/academic-affairs/terms/3/workspace', '/academic-affairs/terms/current', '/academic-affairs/terms/3/workspace'])
  assert.equal(fixture.publicInput().value, detailOwnedWorkspace('3').termName)
  await fixture.fillName('新权限版本名称')
  assert.equal(fixture.detailMounts.length, 1); assert.equal(fixture.detailMounts[0].uid, uid); assert.equal(fixture.detailUnmounts.length, 0)
  assert.ok(fixture.detailUpdates.length > 0); assert.equal(fixture.detailUpdates.at(-1).termId, '3')
  assert.equal(fixture.detailUpdates.at(-1).uid, uid, 'Current context-updated VNode UID was sampled from real component')
  const result = await fixture.settle(navigation, true)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE3); assert.equal(fixture.publicInput().value, '新权限版本名称'); assert.equal(fixture.guard.isDirty(), true)
})

test('detail owned old positive after actual same-instance record3 to record4 commit keeps record4 draft and Router cancellation8', async t => {
  const fixture = await detailOwnedConfirmationFixture(t); const uid = fixture.detailMounts[0].uid
  await fixture.fillName('记录3旧确认草稿')
  const oldNavigation = await fixture.clickReturn(); await fixture.waitDialog()
  // Existing published generic handler permits a new real public link navigation;
  // no second systemDialog is opened and no fake pair of concurrent dialog promises is made.
  const removeGeneric = fixture.guard.registerConfirmation(() => true)
  const newNavigation = await fixture.clickRecord4(); const newResult = await fixture.done(newNavigation)
  assert.equal(newResult.failure, undefined); assert.notEqual(oldNavigation.to, newNavigation.to)
  fixture.assertRecord4Reuse(); assert.equal(fixture.detailMounts[0].uid, uid)
  await fixture.fillName('记录4当前草稿'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  const oldResult = await fixture.settle(oldNavigation, true)
  assert.equal(oldResult.failure.type, ownedConfirmRouter.NavigationFailureType.cancelled)
  assert.equal(fixture.router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE4); assert.equal(fixture.router.options.history.location, DETAIL_OWNED_SOURCE4)
  assert.equal(fixture.publicInput().value, '记录4当前草稿'); assert.equal(fixture.guard.isDirty(), true); assert.equal(fixture.detailUnmounts.length, 0)
  removeGeneric()
})

test('detail owned old negative after actual same-instance record3 to record4 commit keeps new draft with aborted4', async t => {
  const fixture = await detailOwnedConfirmationFixture(t); const uid = fixture.detailMounts[0].uid
  await fixture.fillName('记录3旧取消草稿')
  const oldNavigation = await fixture.clickReturn(); await fixture.waitDialog()
  const removeGeneric = fixture.guard.registerConfirmation(() => true)
  const newNavigation = await fixture.clickRecord4(); const newResult = await fixture.done(newNavigation)
  assert.equal(newResult.failure, undefined); assert.notEqual(oldNavigation.to, newNavigation.to)
  fixture.assertRecord4Reuse(); assert.equal(fixture.detailMounts[0].uid, uid)
  await fixture.fillName('记录4旧取消不能清除'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  const oldResult = await fixture.settle(oldNavigation, false)
  assert.equal(oldResult.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE4); assert.equal(fixture.router.options.history.location, DETAIL_OWNED_SOURCE4)
  assert.equal(fixture.publicInput().value, '记录4旧取消不能清除'); assert.equal(fixture.guard.isDirty(), true); assert.equal(fixture.detailUnmounts.length, 0)
  removeGeneric()
})

test('detail owned registration cleanup cannot remove a later published confirmation handler', async t => {
  const fixture = await detailOwnedConfirmationFixture(t); await fixture.fillName('卸载前已有草稿')
  let calls = 0
  const removeGeneric = fixture.guard.registerConfirmation(() => { calls++; return false })
  fixture.state.ctx = null; await ownedConfirmTick(); assert.equal(fixture.detailUnmounts.length, 1)
  const navigation = await fixture.clickExternal(); const result = await fixture.done(navigation)
  assert.equal(calls, 1); assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, DETAIL_OWNED_SOURCE3); assert.equal(fixture.guard.isDirty(), true)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false); removeGeneric()
})

// Teaching-week confirmation owns only its actual instance/context while the single
// system dialog awaits. Declared DRAFT101/102 transport is not live database authority.
import { createAcademicReturnStore as teachingOwnedReturnStore } from '../src/modules/academicAffairs/academicFlowContext.js'
import { academicStatusLabel as teachingOwnedStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'
import { SCHEDULE_BATCH_STATUS as teachingOwnedScheduleStatus } from '../src/modules/academicAffairs/constants/teaching.js'

const TEACHING_OWNED_TARGET = '/admin/academic-affairs/terms'
const teachingOwnedSource = id => `/admin/academic-affairs/terms/teaching-weeks?termId=${id}&returnToken=DECLARED_WEEK_RETURN_POSITION`
const TEACHING_OWNED_NONTERM = '/admin/academic-affairs/declared-week?termId=101&returnToken=DECLARED_WEEK_RETURN_POSITION'
function teachingOwnedTerm(id) {
  assert.ok(['101', '102'].includes(String(id)))
  return { termId: String(id), yearCode: '2027-2028', termNo: id === '101' ? 1 : 2,
    termName: `声明独立草稿学期${id}`, startDate: id === '101' ? '2027-09-01T00:00:00' : '2028-02-01T00:00:00',
    endDate: id === '101' ? '2028-01-31T23:59:59' : '2028-06-30T23:59:59',
    teachingWeeks: 20, examWeekStart: 18, isCurrent: false, status: 'DRAFT' }
}
const teachingOwnedCurrent = { termId: '1', yearCode: '2025-2026', termNo: 2, termName: '声明当前学期1',
  startDate: '2026-02-01T00:00:00', endDate: '2026-06-30T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: true, status: 'PUBLISHED' }
const teachingOwnedCatalog = () => [teachingOwnedCurrent, teachingOwnedTerm('101'), teachingOwnedTerm('102')]
const teachingOwnedCurrentDTO = { termId: '1', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
function teachingOwnedWorkspace(id) {
  const related = path => `${path}?termId=${id}`
  return { ...teachingOwnedTerm(id), version: 4,
    linkedData: {
      calendar: { count: 0, route: related('/admin/academic-affairs/calendar') },
      teachingTasks: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/teaching-tasks') },
      schedules: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/schedule') },
      exams: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/exam') },
      selections: { batchCount: 0, recordCount: 0, statusCounts: {}, route: related('/admin/academic-affairs/selection') },
      grades: { count: 0, statusCounts: {}, route: related('/admin/academic-affairs/grade-overview') }
    },
    allowedActions: { editBasic: true, editNameOnly: false, publish: true, setCurrent: false, freeze: false, archive: false, viewImpact: true, hasLinkedBusiness: false },
    impactWarning: '当前尚无关联业务，草稿状态可维护基础时间轴。', timeline: [], archiveRoute: related('/admin/academic-affairs/archive/precheck') }
}
// Synthetic complete positive read rows, not a replacement for the calendar producer.
function teachingOwnedWeeks(id) {
  const start = Date.parse(teachingOwnedTerm(id).startDate + 'Z')
  return Array.from({ length: 20 }, (_, index) => ({ weekNo: index + 1,
    startDate: new Date(start + index * 7 * 86400000).toISOString().slice(0, 10),
    endDate: new Date(start + (index * 7 + 6) * 86400000).toISOString().slice(0, 10),
    weekType: index + 1 >= 18 ? 'EXAM' : 'TEACHING', remark: '', teachingDayCount: 5, exceptionSummary: '无例外安排', isCurrent: false }))
}
async function teachingOwnedFixture(t, { start = teachingOwnedSource('101') } = {}) {
  const previous = Object.fromEntries(['window', 'document', 'Document', 'ShadowRoot'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const install = (key, value) => Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  class TeachingDocumentHost { constructor() { this.listeners = {}; this.activeElement = null } addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) } removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) } }
  install('Document', TeachingDocumentHost); install('ShadowRoot', class TeachingShadowRootHost {})
  install('document', new TeachingDocumentHost())
  const windowListeners = {}
  install('window', { addEventListener(name, fn) { (windowListeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { windowListeners[name] = (windowListeners[name] || []).filter(value => value !== fn) } })
  const patterns = ['academicAffairs.term.view', 'academicAffairs.term.manage']
  const claims = ownedConfirmVue.reactive({ tenantId: 'DECLARED_TENANT', userId: 'DECLARED_USER', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_CONTEXT_A' })
  const makeContext = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionPatterns: [...patterns], permissionVersion: 1 })
  const state = ownedConfirmVue.reactive({ ctx: makeContext('DECLARED_TEACHING_SCOPE_A') })
  const reads = [], workspaceResponses = [], catalogResponses = [], currentResponses = [], weeksResponses = [], mounts = [], unmounts = [], updates = [], transitions = [], warnings = [], errors = []
  const prohibited = () => { throw new Error('此教学周确认回归禁止预览/保存/业务写入') }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    reads.push({ path, params: options.params || {}, method: options.method || 'GET' })
    if (path === '/academic-affairs/terms') {
      assert.deepEqual(options.params, { resolveValue: undefined, keyword: '', page: 1, pageSize: 100 })
      return { items: structuredClone(teachingOwnedCatalog()), total: 3, page: 1, pageSize: 100 }
    }
    assert.equal(options.params, undefined)
    if (path === '/academic-affairs/terms/current') return structuredClone(teachingOwnedCurrentDTO)
    const match = /^\/academic-affairs\/terms\/(101|102)\/(workspace|weeks)$/.exec(path)
    assert.ok(match, 'Only original catalog/current and named DRAFT101/102 workspace/weeks reads')
    return match[2] === 'workspace' ? teachingOwnedWorkspace(match[1]) : { items: teachingOwnedWeeks(match[1]) }
  }
  const detailSource = ownedConfirmRead('modules/academicAffairs/api/academic-affairs-term-detail.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ')
  const detailAPI = new Function('request', `${detailSource}\nreturn academicAffairsTermDetailApi`)(request)
  const termApi = { ...detailAPI, get(id) { return detailAPI.get(id).then(response => { workspaceResponses.push(structuredClone(response)); return response }) } }
  const apiSource = ownedConfirmRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const apiModules = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn { academicAffairsApi, academicAffairsOrgApi, academicAffairsLabApi, academicAffairsEquipmentApi, academicAffairsExamApi, academicAffairsSelectionApi, academicAffairsMakeupApi, academicAffairsArchiveApi }`)(request, prohibited, prohibited, prohibited, prohibited, prohibited)
  const academicApi = { ...apiModules.academicAffairsApi,
    getCurrentTerm() { return apiModules.academicAffairsApi.getCurrentTerm().then(response => { currentResponses.push(structuredClone(response)); return response }) },
    getTermWeeks(id) { return apiModules.academicAffairsApi.getTermWeeks(id).then(response => { weeksResponses.push(structuredClone(response)); return response }) } }
  const pickerSource = ownedConfirmRead('modules/academicAffairs/pickerAdapters.js').replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '').replace(/^export (async function|function|const) /gm, '$1 ')
  const pickerBindings = { ...apiModules, academicAffairsApi: academicApi, academicStatusLabel: teachingOwnedStatusLabel, SCHEDULE_BATCH_STATUS: teachingOwnedScheduleStatus }
  const originalCatalog = new Function(...Object.keys(pickerBindings), `${pickerSource}\nreturn loadAcademicTermCatalog`)(...Object.values(pickerBindings))
  const loadCatalog = (...args) => originalCatalog(...args).then(rows => { catalogResponses.push(structuredClone(rows)); return rows })
  const Button = ownedConfirmCompile('components/ui/AppButton.vue')
  const NumberInput = ownedConfirmCompile('components/common/form/AppNumberInput.vue')
  const FieldHint = ownedConfirmCompile('components/common/AppFieldHint.vue')
  const FormItem = ownedConfirmCompile('components/common/form/AppFormItem.vue', { AppHelpTooltip: ownedConfirmVisual('DeclaredUnusedTeachingHelp'), AppFieldHint: FieldHint })
  const Week = ownedConfirmCompile('modules/academicAffairs/views/AaTeachingWeekConfigView.vue', {
    ModulePageShell: ownedConfirmVisual('DeclaredTeachingShell'), AppButton: Button,
    LoadingState: ownedConfirmVisual('DeclaredTeachingLoading'), ErrorState: ownedConfirmVisual('DeclaredTeachingError'), EmptyState: ownedConfirmVisual('DeclaredTeachingEmpty'),
    AppSectionCard: ownedConfirmVisual('DeclaredTeachingCard'), AppFormItem: FormItem, AppNumberInput: NumberInput,
    AppInlineAlert: ownedConfirmVisual('DeclaredTeachingAlert'), AppTermEntityPicker: ownedConfirmVisual('DeclaredUnopenedTeachingPicker'), AaCalendarMonth: ownedConfirmVisual('DeclaredTeachingCalendar'),
    academicAffairsApi: academicApi, termApi, loadAcademicTermCatalog: loadCatalog,
    toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission: ownedConfirmMatchPermission, systemConfirm: ownedConfirmDialog.systemConfirm
  })
  const renderer = ownedConfirmVue.createRenderer({ createElement: tag => ownedConfirmNode(tag), createText: value => ownedConfirmNode('#text', value), createComment: value => ownedConfirmNode('#comment', value),
    setText(node, value) { node.text = value }, setElementText(node, value) { node.text = value; node.children = [] },
    parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    patchProp(node, key, _old, value) { node.props[key] = value },
    insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
    remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } }
  })
  const Parent = { render() { return ownedConfirmH(ownedConfirmRouter.RouterView, null, { default: ({ Component }) => {
    const owner = state.ctx?.ctxKey
    return state.ctx && Component ? ownedConfirmH(Component, { key: owner, ctx: state.ctx,
      onVnodeMounted(vnode) { if (vnode.type?.name === 'AaTeachingWeekConfigView') mounts.push({ owner, uid: vnode.component.uid }) },
      onVnodeUpdated(vnode) { if (vnode.type?.name === 'AaTeachingWeekConfigView') updates.push({ owner, uid: vnode.component.uid, termId: String(router.currentRoute.value.query.termId || '') }) },
      onVnodeUnmounted(vnode) { if (vnode.type?.name === 'AaTeachingWeekConfigView') unmounts.push({ owner, uid: vnode.component.uid }) }
    }) : ownedConfirmH('p', '声明上下文读取中，无API')
  } }) } }
  const router = ownedConfirmRouter.createRouter({ history: ownedConfirmRouter.createMemoryHistory(), routes: [{ path: '/admin/academic-affairs', component: Parent, meta: { moduleCode: 'ACADEMIC_AFFAIRS' }, children: [
    { path: 'terms/teaching-weeks', name: 'aa-term-teaching-weeks', component: Week, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.manage' } },
    { path: 'declared-week', name: 'declared-teaching-week-nonterm', component: Week, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.manage' } },
    { path: 'terms', name: 'aa-terms', component: { render: () => ownedConfirmH('p', '声明只读学期列表，无API') }, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.view' } }
  ] }] })
  ownedConfirmGate.clearPermissionPatterns(); ownedConfirmGate.setModuleEntitlements(['academicAffairs']); ownedConfirmGate.setPermissionPatterns(patterns)
  let queuedObserver = null
  const observedTo = new WeakMap()
  const removePermission = router.beforeEach(to => { assert.equal(ownedConfirmGate.canEnterRoute(to.meta), true); if (queuedObserver) { const observer = queuedObserver; queuedObserver = null; observer.to = to; observedTo.set(to, observer); observer.entered.resolve(to) } return true })
  const disposeDirty = installDirtyFormGuard(router)
  const removeAfter = router.afterEach((to, from, failure) => { transitions.push({ to: to.fullPath, from: from.fullPath, failureType: failure?.type ?? null }); const observer = observedTo.get(to); if (observer) { observer.result = { to, from, failure }; observer.completed.resolve(observer.result) } })
  const removeError = router.onError(error => errors.push({ source: 'router', message: error.message }))
  const storage = new Map()
  const returns = teachingOwnedReturnStore({ getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }, { now: () => 0, token: () => 'DECLARED_WEEK_RETURN_POSITION' })
  const identity = () => ownedConfirmAcademicIdentity(claims, state.ctx || {})
  assert.equal(returns.remember({ path: TEACHING_OWNED_TARGET, query: {} }, identity()), 'DECLARED_WEEK_RETURN_POSITION')
  let app, stopped = false
  t.after(async () => {
    ownedConfirmDialog.finishSystemDialog(false)
    if (app && !stopped) { app.unmount(); stopped = true }
    await ownedConfirmTick(); disposeDirty(); removePermission(); removeAfter(); removeError(); ownedConfirmGate.clearPermissionPatterns()
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  })
  await router.push(start); await router.isReady()
  const root = ownedConfirmNode('root')
  const Host = { setup() { ownedConfirmVue.provide('academicFlow', { identity, returns,
    back: async (token, fallback) => { const position = returns.resolve(token, identity()); await router.push(position?.path || fallback) }, restorePosition() {}
  }); return () => ownedConfirmH('main', {}, [
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: teachingOwnedSource('102') }, { default: () => '声明的公开草稿学期102链接' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: TEACHING_OWNED_TARGET }, { default: () => '声明的公开教学周外部列表链接' }), ownedConfirmH(ownedConfirmRouter.RouterView)
  ]) } }
  app = renderer.createApp(Host); app.use(router)
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ source: 'vue', message: error.message })
  app.mount(root); await ownedConfirmTick()
  const guard = window.__SAAS_DIRTY_FORM_GUARD__
  const publicGroup = () => { const groups = ownedConfirmWalk(root).filter(node => node.type === 'div' && String(node.props.class || '').split(/\s+/).includes('app-form-item') && ownedConfirmWalk(node).some(child => child.type === 'label' && ownedConfirmText(child).trim().endsWith('教学周总数'))); assert.equal(groups.length, 1); return groups[0] }
  const publicInput = () => { const fields = ownedConfirmWalk(publicGroup()).filter(node => node.type === 'input' && String(node.props.class || '').split(/\s+/).includes('app-number-input__el')); assert.equal(fields.length, 1); assert.equal(!!fields[0].props.disabled, false); return fields[0] }
  const assertDraft = value => { assert.equal(publicInput().props.value, String(value)); assert.deepEqual(ownedConfirmWalk(root).filter(node => node.type === 'input' && String(node.props.class || '').split(/\s+/).includes('app-number-input__el')).map(node => node.props.value), [String(value), '18']); assert.equal(guard.isDirty(), true); assert.equal(router.options.history.location, router.currentRoute.value.fullPath) }
  const dispatch = node => { assert.equal(!!node.props.disabled, false); const event = { type: 'click', target: node, currentTarget: node }; const handlers = node.props.onClick; assert.ok(handlers); for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event) }
  const increase = async (count = 1, expectedDirty = true) => { for (let index = 0; index < count; index++) { const buttons = ownedConfirmWalk(publicGroup()).filter(node => node.type === 'button' && node.props['aria-label'] === '增加'); assert.equal(buttons.length, 1); dispatch(buttons[0]); await ownedConfirmTick() } assert.equal(guard.isDirty(), expectedDirty) }
  const waitReadback = async (id, expectedReads) => {
    await ownedConfirmBounded((async () => { while (reads.length < expectedReads || workspaceResponses.at(-1)?.data?.termId !== id || weeksResponses.length < workspaceResponses.length) await ownedConfirmTick() })())
    await ownedConfirmTick()
    assert.equal(reads.length, expectedReads); assert.deepEqual(workspaceResponses.at(-1).data, teachingOwnedWorkspace(id)); assert.deepEqual(weeksResponses.at(-1).data, teachingOwnedWeeks(id))
    for (const rows of catalogResponses) assert.deepEqual(rows, teachingOwnedCatalog())
    for (const response of currentResponses) assert.deepEqual(response.data, teachingOwnedCurrentDTO)
    assert.equal(publicInput().props.value, '20')
  }
  await waitReadback('101', 4)
  assert.equal(catalogResponses.length, 1); assert.equal(currentResponses.length, 1); assert.equal(workspaceResponses.length, 1); assert.equal(weeksResponses.length, 1)
  const beginNavigation = () => { assert.equal(queuedObserver, null); const observer = { entered: ownedConfirmDeferred(), completed: ownedConfirmDeferred(), to: null, result: null }; queuedObserver = observer; return observer }
  const click = async (tag, label) => { const nodes = ownedConfirmWalk(root).filter(node => node.type === tag && ownedConfirmText(node) === label); assert.equal(nodes.length, 1); const observer = beginNavigation(); dispatch(nodes[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const clickReturn = () => click('button', '返回原位置')
  const click102 = () => click('a', '声明的公开草稿学期102链接')
  const clickExternal = () => click('a', '声明的公开教学周外部列表链接')
  const waitDialog = async () => { await ownedConfirmBounded((async () => { while (!ownedConfirmDialog.systemDialogState.visible) await ownedConfirmTick() })()); assert.equal(ownedConfirmDialog.systemDialogState.title, '确认离开当前页面'); assert.equal(ownedConfirmDialog.systemDialogState.confirmText, '放弃修改并离开') }
  const done = async observer => { const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result }
  const settle = async (observer, accepted) => { ownedConfirmDialog.finishSystemDialog(accepted); return done(observer) }
  const replaceOwner = async () => { state.ctx = null; await ownedConfirmTick(); assert.equal(unmounts.length, 1); state.ctx = makeContext('DECLARED_TEACHING_SCOPE_B'); await waitReadback('101', 8); assert.equal(mounts.length, 2); assert.notEqual(mounts[0].uid, mounts[1].uid); assert.equal(catalogResponses.length, 2); assert.equal(currentResponses.length, 2) }
  const assert102Reuse = () => {
    assert.equal(state.ctx.ctxKey, 'DECLARED_TEACHING_SCOPE_A'); assert.equal(mounts.length, 1); assert.equal(unmounts.length, 0)
    const currentUpdates = updates.filter(event => event.termId === '102'); assert.ok(currentUpdates.length > 0); assert.equal(currentUpdates.at(-1).uid, mounts[0].uid)
    assert.equal(router.currentRoute.value.fullPath, teachingOwnedSource('102')); assert.equal(router.options.history.location, teachingOwnedSource('102'))
    assert.equal(catalogResponses.length, 1); assert.equal(currentResponses.length, 1)
    assert.deepEqual(workspaceResponses.map(response => response.data), [teachingOwnedWorkspace('101'), teachingOwnedWorkspace('102')])
    assert.deepEqual(weeksResponses.map(response => response.data), [teachingOwnedWeeks('101'), teachingOwnedWeeks('102')])
    assert.deepEqual(reads.map(row => row.path), ['/academic-affairs/terms', '/academic-affairs/terms/current', '/academic-affairs/terms/101/workspace', '/academic-affairs/terms/101/weeks', '/academic-affairs/terms/102/workspace', '/academic-affairs/terms/102/weeks'])
  }
  return { router, state, claims, identity, root, guard, reads, workspaceResponses, catalogResponses, currentResponses, weeksResponses, mounts, unmounts, updates, transitions,
    publicInput, increase, assertDraft, waitReadback, clickReturn, click102, clickExternal, waitDialog, done, settle, replaceOwner, assert102Reuse }
}

test('teaching week old unmounted positive preserves B numeric draft and permits B genuine fresh confirmation', async t => {
  const f = await teachingOwnedFixture(t); await f.increase(); f.assertDraft(21)
  const old = await f.clickReturn(); await f.waitDialog(); await f.replaceOwner(); await f.increase(2); f.assertDraft(22)
  const result = await f.settle(old, true)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('101')); assert.equal(f.router.options.history.location, teachingOwnedSource('101')); f.assertDraft(22)
  const next = await f.clickReturn(); await f.waitDialog(); const accepted = await f.settle(next, true)
  assert.equal(accepted.failure, undefined); assert.equal(f.router.currentRoute.value.fullPath, TEACHING_OWNED_TARGET); assert.equal(f.guard.isDirty(), false)
})

test('teaching week clean public return opens no dialog', async t => {
  const f = await teachingOwnedFixture(t); const navigation = await f.clickReturn(); const result = await f.done(navigation)
  assert.equal(result.failure, undefined); assert.equal(f.router.currentRoute.value.fullPath, TEACHING_OWNED_TARGET); assert.equal(f.guard.isDirty(), false); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
})

test('teaching week non guarded source route keeps original navigation semantics', async t => {
  const f = await teachingOwnedFixture(t, { start: TEACHING_OWNED_NONTERM }); await f.increase(1, false)
  assert.equal(f.publicInput().props.value, '21'); assert.equal(f.guard.handlesRoute(f.router.currentRoute.value), false)
  const result = await f.done(await f.clickReturn())
  assert.equal(result.failure, undefined); assert.equal(f.router.currentRoute.value.fullPath, TEACHING_OWNED_TARGET); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
})

test('teaching week same record cancel preserves actual input and healthy accept discards normally', async t => {
  const f = await teachingOwnedFixture(t); await f.increase(); const cancelled = await f.clickReturn(); await f.waitDialog()
  assert.equal((await f.settle(cancelled, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('101')); f.assertDraft(21)
  const accepted = await f.clickReturn(); await f.waitDialog(); assert.equal((await f.settle(accepted, true)).failure, undefined)
  assert.equal(f.router.currentRoute.value.fullPath, TEACHING_OWNED_TARGET); assert.equal(f.guard.isDirty(), false)
})

test('teaching week same mounted context reload invalidates old positive', async t => {
  const f = await teachingOwnedFixture(t); const uid = f.mounts[0].uid; await f.increase(); const old = await f.clickReturn(); await f.waitDialog()
  f.state.ctx = { ...f.state.ctx, permissionVersion: 2 }; await f.waitReadback('101', 8); await f.increase(2)
  assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0); assert.ok(f.updates.length > 0); assert.equal(f.updates.at(-1).uid, uid)
  assert.equal(f.state.ctx.ctxKey, 'DECLARED_TEACHING_SCOPE_A'); assert.equal(f.catalogResponses.length, 2); assert.equal(f.currentResponses.length, 2)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('101')); f.assertDraft(22)
})

test('teaching week old unmounted negative preserves replacement numeric draft', async t => {
  const f = await teachingOwnedFixture(t); await f.increase(); const old = await f.clickReturn(); await f.waitDialog(); await f.replaceOwner(); await f.increase(2)
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('101')); f.assertDraft(22)
})

test('teaching week owned cleanup preserves a later published generic confirmation handler', async t => {
  const f = await teachingOwnedFixture(t); await f.increase(); let calls = 0
  const removeGeneric = f.guard.registerConfirmation(() => { calls++; return false })
  f.state.ctx = null; await ownedConfirmTick(); assert.equal(f.unmounts.length, 1)
  const result = await f.done(await f.clickExternal())
  assert.equal(calls, 1); assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('101')); assert.equal(f.guard.isDirty(), true); assert.equal(ownedConfirmDialog.systemDialogState.visible, false); removeGeneric()
})

test('teaching week same mounted unchanged context rejects old positive after published Flow identity changes', async t => {
  const f = await teachingOwnedFixture(t); const ctx = f.state.ctx, uid = f.mounts[0].uid, identity = f.identity()
  await f.increase(); const old = await f.clickReturn(); await f.waitDialog()
  // Declared identity input changes; no role/permission/IAM or context object mutation.
  f.claims.activeContextId = 'DECLARED_CONTEXT_B'; await ownedConfirmTick()
  assert.notEqual(f.identity(), identity); assert.equal(f.state.ctx, ctx); assert.equal(f.reads.length, 4); assert.equal(f.mounts.length, 1); assert.equal(f.mounts[0].uid, uid); assert.equal(f.unmounts.length, 0)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('101')); f.assertDraft(21)
})

test('teaching week old positive after new legitimate URL commit retains Router cancellation8', async t => {
  const f = await teachingOwnedFixture(t); await f.increase(); const old = await f.clickReturn(); await f.waitDialog(); await f.replaceOwner()
  // Public generic discard collaborator allows the new real link; no second real dialog.
  const removeGeneric = f.guard.registerConfirmation(() => true)
  const current = await f.clickExternal(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  assert.equal(f.router.currentRoute.value.fullPath, TEACHING_OWNED_TARGET); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.cancelled)
  assert.equal(f.router.currentRoute.value.fullPath, TEACHING_OWNED_TARGET); assert.equal(f.router.options.history.location, TEACHING_OWNED_TARGET); removeGeneric()
})

test('teaching week real query101 to102 same instance keeps new numeric draft after old positive Router cancellation8', async t => {
  const f = await teachingOwnedFixture(t); await f.increase(); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true)
  const current = await f.click102(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  await f.waitReadback('102', 6); f.assert102Reuse(); await f.increase(2); f.assertDraft(22)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.cancelled)
  assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('102')); assert.equal(f.router.options.history.location, teachingOwnedSource('102')); f.assertDraft(22); assert.equal(f.unmounts.length, 0); removeGeneric()
})

test('teaching week real query101 to102 same instance keeps new numeric draft after old negative abort4', async t => {
  const f = await teachingOwnedFixture(t); await f.increase(); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true)
  const current = await f.click102(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  await f.waitReadback('102', 6); f.assert102Reuse(); await f.increase(2); f.assertDraft(22)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(f.router.currentRoute.value.fullPath, teachingOwnedSource('102')); assert.equal(f.router.options.history.location, teachingOwnedSource('102')); f.assertDraft(22); assert.equal(f.unmounts.length, 0); removeGeneric()
})

// Calendar owns the existing single shared confirmation only while its actual
// instance/context/term/tab remain current. These transports are declared unit
// inputs; actual Drawer/Transition/TextInput/Router are compiled without substitutes.
import { clearImmediate as calendarOwnedClearImmediate } from 'node:timers'
const calendarOwnedSource = (id = '101', tab = 'events') => `/admin/academic-affairs/calendar?termId=${id}&tab=${tab}&returnToken=DECLARED_CALENDAR_RETURN_POSITION`
const CALENDAR_OWNED_TARGET = '/admin/academic-affairs/terms'
const calendarOwnedCatalog = () => teachingOwnedCatalog().map(row => row.status === 'DRAFT' ? { ...row, termName: `声明独立校历草稿学期${row.termId}` } : { ...row })
const calendarOwnedNode = (type, text = '') => {
  const classes = new Set()
  return { ...ownedConfirmNode(type, text), style: {}, ownerDocument: globalThis.document || null,
    classList: { add(value) { classes.add(value) }, remove(value) { classes.delete(value) }, contains(value) { return classes.has(value) } } }
}
async function calendarOwnedFixture(t) {
  const globalKeys = ['window', 'document', 'Document', 'ShadowRoot', 'sessionStorage', 'requestAnimationFrame', 'cancelAnimationFrame']
  const previous = Object.fromEntries(globalKeys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const install = (key, value) => Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  class CalendarDocumentHost {
    constructor() { this.listeners = {}; this.activeElement = null; this.body = calendarOwnedNode('body'); this.body.ownerDocument = this; this.body.offsetHeight = 0 }
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) }
    removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) }
  }
  install('Document', CalendarDocumentHost); install('ShadowRoot', class CalendarShadowRootHost {})
  install('document', new CalendarDocumentHost())
  const windowListeners = {}, storage = new Map(), rafJobs = new Set()
  install('window', { addEventListener(name, fn) { (windowListeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { windowListeners[name] = (windowListeners[name] || []).filter(value => value !== fn) },
    getComputedStyle() { return { transitionDelay: '0s', transitionDuration: '0s', animationDelay: '0s', animationDuration: '0s' } } })
  install('sessionStorage', { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, String(value)), removeItem: key => storage.delete(key) })
  install('requestAnimationFrame', fn => { const job = ownedConfirmSetImmediate(() => { rafJobs.delete(job); fn(0) }); rafJobs.add(job); return job })
  install('cancelAnimationFrame', job => { calendarOwnedClearImmediate(job); rafJobs.delete(job) })
  const patterns = ['academicAffairs.term.view', 'academicAffairs.calendar.view', 'academicAffairs.calendar.manage']
  // Intentionally non-reactive: confirmation must freshly call the existing Flow
  // identity provider, rather than trust its previously cached computed result.
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_USER', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_CONTEXT_A' }
  const makeContext = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionPatterns: [...patterns] })
  const state = ownedConfirmVue.reactive({ ctx: makeContext('DECLARED_CALENDAR_SCOPE_A') })
  const identity = () => ownedConfirmAcademicIdentity(claims, state.ctx || {})
  const reads = [], catalogResponses = [], currentResponses = [], calendarResponses = [], mounts = [], unmounts = [], updates = [], transitions = [], errors = [], warnings = []
  const prohibited = () => { throw new Error('校历确认回归禁止添加/保存/复制/发布/归档及其他业务请求') }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    reads.push({ path, params: options.params || {}, method: options.method || 'GET' })
    if (path === '/academic-affairs/terms') {
      assert.deepEqual(options.params, { resolveValue: undefined, keyword: '', page: 1, pageSize: 100 })
      return { items: calendarOwnedCatalog(), total: 3, page: 1, pageSize: 100 }
    }
    if (path === '/academic-affairs/terms/current') { assert.equal(options.params, undefined); return structuredClone(teachingOwnedCurrentDTO) }
    const match = /^\/academic-affairs\/terms\/(101|102)\/calendar$/.exec(path)
    assert.ok(match, 'Only catalog/current and declared DRAFT101/102 empty calendar reads')
    assert.deepEqual(options.params, {})
    return { items: [] }
  }
  const apiSource = ownedConfirmRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const modules = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn { academicAffairsApi, academicAffairsOrgApi, academicAffairsLabApi, academicAffairsEquipmentApi, academicAffairsExamApi, academicAffairsSelectionApi, academicAffairsMakeupApi, academicAffairsArchiveApi }`)(request, prohibited, prohibited, prohibited, prohibited, prohibited)
  const academicApi = { ...modules.academicAffairsApi,
    getCurrentTerm() { return modules.academicAffairsApi.getCurrentTerm().then(response => { currentResponses.push(structuredClone(response)); return response }) },
    getCalendar(id, type) { assert.ok(['101', '102'].includes(String(id))); assert.equal(type, undefined); return modules.academicAffairsApi.getCalendar(id, type).then(response => { calendarResponses.push({ termId: String(id), response: structuredClone(response) }); return response }) } }
  const detailSource = ownedConfirmRead('modules/academicAffairs/api/academic-affairs-term-detail.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ')
  const termApi = new Function('request', `${detailSource}\nreturn academicAffairsTermDetailApi`)(request)
  const pickerSource = ownedConfirmRead('modules/academicAffairs/pickerAdapters.js').replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '').replace(/^export (async function|function|const) /gm, '$1 ')
  const pickerBindings = { ...modules, academicAffairsApi: academicApi, academicStatusLabel: teachingOwnedStatusLabel, SCHEDULE_BATCH_STATUS: teachingOwnedScheduleStatus }
  const originalCatalog = new Function(...Object.keys(pickerBindings), `${pickerSource}\nreturn loadAcademicTermCatalog`)(...Object.values(pickerBindings))
  const loadCatalog = (...args) => originalCatalog(...args).then(rows => { catalogResponses.push(structuredClone(rows)); return rows })
  const Button = ownedConfirmCompile('components/ui/AppButton.vue')
  const Drawer = ownedConfirmCompile('components/ui/AppDrawer.vue')
  const TextInput = ownedConfirmCompile('components/common/form/AppTextInput.vue')
  const FieldHint = ownedConfirmCompile('components/common/AppFieldHint.vue')
  const FormItem = ownedConfirmCompile('components/common/form/AppFormItem.vue', { AppHelpTooltip: ownedConfirmVisual('DeclaredUnusedCalendarHelp'), AppFieldHint: FieldHint })
  const Calendar = ownedConfirmCompile('modules/academicAffairs/views/AaCalendarView.vue', {
    ModulePageShell: ownedConfirmVisual('DeclaredCalendarShell'), AppButton: Button, AppDrawer: Drawer,
    DataTable: ownedConfirmVisual('DeclaredEmptyCalendarTable'), StatusTag: ownedConfirmVisual('DeclaredCalendarStatus'),
    LoadingState: ownedConfirmVisual('DeclaredCalendarLoading'), ErrorState: ownedConfirmVisual('DeclaredCalendarError'), EmptyState: ownedConfirmVisual('DeclaredCalendarEmpty'),
    AppSectionCard: ownedConfirmVisual('DeclaredCalendarCard'), AppFormItem: FormItem, AppSelect: ownedConfirmVisual('DeclaredUnchangedEventType'), AppTextInput: TextInput,
    AppDatePicker: ownedConfirmVisual('DeclaredUnchangedBlankEventDates'), AppTermEntityPicker: ownedConfirmVisual('DeclaredUnopenedCalendarPicker'), AppConfirmDialog: ownedConfirmVisual('DeclaredUnopenedCalendarActionDialog'), AppInlineAlert: ownedConfirmVisual('DeclaredCalendarAlert'),
    AaCalendarCopyPanel: ownedConfirmVisual('DeclaredUnopenedCalendarCopy'), AaCalendarMonth: ownedConfirmVisual('DeclaredCalendarMonth'), AaCalendarArchivePanel: ownedConfirmVisual('DeclaredUnopenedCalendarArchive'),
    academicAffairsApi: academicApi, academicAffairsTermDetailApi: termApi, loadAcademicTermCatalog: loadCatalog,
    toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission: ownedConfirmMatchPermission, currentUserFromToken: () => claims, systemConfirm: ownedConfirmDialog.systemConfirm
  })
  const renderer = ownedConfirmVue.createRenderer({ createElement: tag => calendarOwnedNode(tag), createText: value => calendarOwnedNode('#text', value), createComment: value => calendarOwnedNode('#comment', value),
    setText(node, value) { node.text = value }, setElementText(node, value) { node.text = value; node.children = [] },
    parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    querySelector(selector) { assert.equal(selector, 'body'); return document.body }, patchProp(node, key, _old, value) { node.props[key] = value },
    insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
    remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } }
  })
  const Parent = { render() { return ownedConfirmH(ownedConfirmRouter.RouterView, null, { default: ({ Component }) => {
    const owner = state.ctx?.ctxKey
    return state.ctx && Component ? ownedConfirmH(Component, { key: owner, ctx: state.ctx,
      onVnodeMounted(vnode) { if (vnode.type?.name === 'AaCalendarView') mounts.push({ owner, uid: vnode.component.uid }) },
      onVnodeUpdated(vnode) { if (vnode.type?.name === 'AaCalendarView') updates.push({ owner, uid: vnode.component.uid, termId: String(router.currentRoute.value.query.termId || ''), tab: String(router.currentRoute.value.query.tab || '') }) },
      onVnodeUnmounted(vnode) { if (vnode.type?.name === 'AaCalendarView') unmounts.push({ owner, uid: vnode.component.uid }) }
    }) : ownedConfirmH('p', '声明上下文读取中，无API')
  } }) } }
  const router = ownedConfirmRouter.createRouter({ history: ownedConfirmRouter.createMemoryHistory(), routes: [{ path: '/admin/academic-affairs', component: Parent, meta: { moduleCode: 'ACADEMIC_AFFAIRS' }, children: [
    { path: 'calendar', name: 'aa-calendar', component: Calendar, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.calendar.view' } },
    { path: 'terms', name: 'aa-terms', component: { render: () => ownedConfirmH('p', '声明只读学期列表，无API') }, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.view' } }
  ] }] })
  ownedConfirmGate.clearPermissionPatterns(); ownedConfirmGate.setModuleEntitlements(['academicAffairs']); ownedConfirmGate.setPermissionPatterns(patterns)
  let queuedObserver = null
  const observedTo = new WeakMap()
  const removePermission = router.beforeEach(to => { assert.equal(ownedConfirmGate.canEnterRoute(to.meta), true); if (queuedObserver) { const observer = queuedObserver; queuedObserver = null; observer.to = to; observedTo.set(to, observer); observer.entered.resolve(to) } return true })
  const disposeDirty = installDirtyFormGuard(router)
  const removeAfter = router.afterEach((to, from, failure) => { transitions.push({ to: to.fullPath, from: from.fullPath, failureType: failure?.type ?? null }); const observer = observedTo.get(to); if (observer) { observer.result = { to, from, failure }; observer.completed.resolve(observer.result) } })
  const removeError = router.onError(error => errors.push({ source: 'router', message: error.message }))
  const returnStorage = new Map()
  const returns = teachingOwnedReturnStore({ getItem: key => returnStorage.get(key) || null, setItem: (key, value) => returnStorage.set(key, value), removeItem: key => returnStorage.delete(key) }, { now: () => 0, token: () => 'DECLARED_CALENDAR_RETURN_POSITION' })
  assert.equal(returns.remember({ path: CALENDAR_OWNED_TARGET, query: {} }, identity()), 'DECLARED_CALENDAR_RETURN_POSITION')
  const remarkInputs = () => ownedConfirmWalk(document.body).filter(node => node.type === 'input' && node.props.placeholder === '选填，如 国庆假期 / 国庆调休')
  const drawerMasks = () => ownedConfirmWalk(document.body).filter(node => node.type === 'div' && String(node.props.class || '').split(/\s+/).includes('app-drawer-mask'))
  const overlayIdle = async () => { await ownedConfirmBounded((async () => { while (remarkInputs().length || drawerMasks().length || rafJobs.size) await ownedConfirmTick() })()) }
  const waitSingleCreate = async () => { await ownedConfirmBounded((async () => { while (remarkInputs().length !== 1 || drawerMasks().length !== 1 || rafJobs.size) await ownedConfirmTick() })()) }
  let app, stopped = false
  t.after(async () => {
    ownedConfirmDialog.finishSystemDialog(false)
    if (app && !stopped) { app.unmount(); stopped = true }
    await overlayIdle(); await ownedConfirmTick(); disposeDirty(); removePermission(); removeAfter(); removeError(); ownedConfirmGate.clearPermissionPatterns()
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  })
  await router.push(calendarOwnedSource()); await router.isReady()
  const root = calendarOwnedNode('root')
  const Host = { setup() { ownedConfirmVue.provide('academicFlow', { identity, returns,
    back: async (token, fallback) => { const position = returns.resolve(token, identity()); await router.push(position?.path || fallback) }, restorePosition() {}
  }); return () => ownedConfirmH('main', {}, [
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: calendarOwnedSource('102') }, { default: () => '声明的公开校历学期102链接' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: calendarOwnedSource('101', 'holiday') }, { default: () => '声明的公开节假日配置链接' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: CALENDAR_OWNED_TARGET }, { default: () => '声明的公开校历外部列表链接' }), ownedConfirmH(ownedConfirmRouter.RouterView)
  ]) } }
  app = renderer.createApp(Host); app.use(router)
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ source: 'vue', message: error.message })
  app.mount(root)
  const guard = window.__SAAS_DIRTY_FORM_GUARD__
  const dispatch = node => { assert.equal(!!node.props.disabled, false); const handlers = node.props.onClick; assert.ok(handlers); const event = { type: 'click', target: node, currentTarget: node }; for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event) }
  const createTitle = () => router.currentRoute.value.query.tab === 'holiday' ? '新增节假日' : '新增校历事件'
  const publicInput = () => {
    const drawers = ownedConfirmWalk(document.body).filter(node => node.type === 'aside' && node.props.role === 'dialog' && node.props['aria-label'] === createTitle()); assert.equal(drawers.length, 1)
    const fields = ownedConfirmWalk(drawers[0]).filter(node => node.type === 'input' && node.props.placeholder === '选填，如 国庆假期 / 国庆调休'); assert.equal(fields.length, 1); assert.equal(!!fields[0].props.disabled, false); return fields[0]
  }
  const waitReadback = async (count, id = '101', catalogCount = 1) => {
    await ownedConfirmBounded((async () => { while (reads.length < count || calendarResponses.at(-1)?.termId !== id) await ownedConfirmTick() })())
    await ownedConfirmTick(); assert.equal(reads.length, count); assert.equal(catalogResponses.length, catalogCount); assert.equal(currentResponses.length, catalogCount)
    for (const rows of catalogResponses) assert.deepEqual(rows, calendarOwnedCatalog())
    for (const response of currentResponses) assert.deepEqual(response.data, teachingOwnedCurrentDTO)
    for (const result of calendarResponses) assert.deepEqual(result.response, { code: 0, data: [], message: 'ok' })
  }
  await waitReadback(3); assert.equal(mounts.length, 1); assert.equal(unmounts.length, 0); assert.equal(remarkInputs().length, 0)
  const openCreate = async () => { const buttons = ownedConfirmWalk(root).filter(node => node.type === 'button' && ownedConfirmText(node) === createTitle()); assert.equal(buttons.length, 1); dispatch(buttons[0]); await ownedConfirmTick(); assert.equal(publicInput().props.value, '') }
  const fillRemark = async value => { const field = publicInput(); const handlers = field.props.onInput; assert.ok(handlers); field.value = value; const event = { type: 'input', target: field, currentTarget: field }; for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event); await ownedConfirmTick(); assert.equal(publicInput().props.value, value); assert.equal(guard.isDirty(), true) }
  const assertDraft = (value, source = calendarOwnedSource()) => { assert.equal(router.currentRoute.value.fullPath, source); assert.equal(router.options.history.location, source); assert.equal(publicInput().props.value, value); assert.equal(remarkInputs().length, 1); assert.equal(guard.isDirty(), true) }
  const beginNavigation = () => { assert.equal(queuedObserver, null); const observer = { entered: ownedConfirmDeferred(), completed: ownedConfirmDeferred(), to: null, result: null }; queuedObserver = observer; return observer }
  const click = async (tag, label) => { const nodes = ownedConfirmWalk(root).filter(node => node.type === tag && ownedConfirmText(node) === label); assert.equal(nodes.length, 1); const observer = beginNavigation(); dispatch(nodes[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const clickReturn = () => click('button', '返回原位置')
  const click102 = () => click('a', '声明的公开校历学期102链接')
  const clickHoliday = () => click('a', '声明的公开节假日配置链接')
  const clickExternal = () => click('a', '声明的公开校历外部列表链接')
  const waitDialog = async () => { await ownedConfirmBounded((async () => { while (!ownedConfirmDialog.systemDialogState.visible) await ownedConfirmTick() })()); assert.equal(ownedConfirmDialog.systemDialogState.title, '确认离开当前页面'); assert.equal(ownedConfirmDialog.systemDialogState.confirmText, '放弃修改并离开') }
  const done = async observer => { const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result }
  const settle = async (observer, accepted) => { ownedConfirmDialog.finishSystemDialog(accepted); return done(observer) }
  const replaceOwner = async () => { state.ctx = null; await ownedConfirmTick(); assert.equal(unmounts.length, 1); await overlayIdle(); state.ctx = makeContext('DECLARED_CALENDAR_SCOPE_B'); await waitReadback(6, '101', 2); assert.equal(mounts.length, 2); assert.notEqual(mounts[0].uid, mounts[1].uid); assert.equal(remarkInputs().length, 0) }
  const assertQueryReuse = async (id, tab) => {
    await waitReadback(4, id); await overlayIdle()
    assert.equal(state.ctx.ctxKey, 'DECLARED_CALENDAR_SCOPE_A'); assert.equal(mounts.length, 1); assert.equal(unmounts.length, 0)
    const current = updates.filter(event => event.termId === id && event.tab === tab); assert.ok(current.length > 0); assert.equal(current.at(-1).uid, mounts[0].uid)
    assert.equal(router.currentRoute.value.fullPath, calendarOwnedSource(id, tab)); assert.equal(router.options.history.location, calendarOwnedSource(id, tab))
    assert.deepEqual(reads.map(row => row.path), ['/academic-affairs/terms', '/academic-affairs/terms/current', '/academic-affairs/terms/101/calendar', `/academic-affairs/terms/${id}/calendar`])
    assert.deepEqual(calendarResponses.map(result => result.termId), ['101', id]); assert.equal(remarkInputs().length, 0)
  }
  return { router, state, claims, identity, guard, reads, catalogResponses, currentResponses, calendarResponses, mounts, unmounts, updates, transitions, publicInput,
    openCreate, fillRemark, assertDraft, waitReadback, overlayIdle, waitSingleCreate, clickReturn, click102, clickHoliday, clickExternal, waitDialog, done, settle, replaceOwner, assertQueryReuse }
}

test('calendar old unmounted positive preserves B public remark and permits B genuine fresh confirmation', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('声明A旧校历备注')
  const old = await f.clickReturn(); await f.waitDialog(); await f.replaceOwner(); await f.openCreate(); await f.fillRemark('声明B当前校历备注')
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明B当前校历备注')
  const current = await f.clickReturn(); await f.waitDialog(); assert.equal((await f.settle(current, true)).failure, undefined)
  assert.equal(f.router.currentRoute.value.fullPath, CALENDAR_OWNED_TARGET); assert.equal(f.guard.isDirty(), false)
})

test('calendar old unmounted negative preserves replacement remark draft', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('声明A旧否定备注')
  const old = await f.clickReturn(); await f.waitDialog(); await f.replaceOwner(); await f.openCreate(); await f.fillRemark('声明B新否定备注')
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明B新否定备注')
})

test('calendar normal same owner cancel and healthy accept retain original behavior', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('正常取消仍保留')
  const cancel = await f.clickReturn(); await f.waitDialog(); assert.equal((await f.settle(cancel, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('正常取消仍保留')
  const accept = await f.clickReturn(); await f.waitDialog(); assert.equal((await f.settle(accept, true)).failure, undefined)
  assert.equal(f.router.currentRoute.value.fullPath, CALENDAR_OWNED_TARGET); assert.equal(f.guard.isDirty(), false)
})

test('calendar same mounted context readback invalidates old positive and preserves current remark', async t => {
  const f = await calendarOwnedFixture(t); const uid = f.mounts[0].uid; await f.openCreate(); await f.fillRemark('原上下文备注不能私自清空')
  const old = await f.clickReturn(); await f.waitDialog()
  f.state.ctx = { ...f.state.ctx, dataScope: { ...f.state.ctx.dataScope, scopeName: '声明新的学校范围名称' } }
  await f.waitReadback(6, '101', 2); await f.waitSingleCreate()
  assert.equal(f.publicInput().props.value, '原上下文备注不能私自清空', 'Original context reload does not reset draft or createVisible')
  assert.equal(f.state.ctx.ctxKey, 'DECLARED_CALENDAR_SCOPE_A'); assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0); assert.ok(f.updates.length > 0); assert.equal(f.updates.at(-1).uid, uid)
  await f.fillRemark('相同实例新上下文备注')
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('相同实例新上下文备注')
})

test('calendar freshly called non reactive Flow identity invalidates old positive without extra reads', async t => {
  const f = await calendarOwnedFixture(t); const identity = f.identity(), ctx = f.state.ctx, uid = f.mounts[0].uid
  await f.openCreate(); await f.fillRemark('旧非响应式身份备注'); const old = await f.clickReturn(); await f.waitDialog()
  f.claims.activeContextId = 'DECLARED_CONTEXT_B'; assert.notEqual(f.identity(), identity)
  assert.equal(f.state.ctx, ctx); assert.equal(f.reads.length, 3); assert.equal(f.mounts.length, 1); assert.equal(f.mounts[0].uid, uid); assert.equal(f.unmounts.length, 0)
  await f.fillRemark('当前非响应式身份备注')
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('当前非响应式身份备注')
})

test('calendar own cleanup preserves a later published generic handler', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('卸载前真实备注'); let calls = 0
  const removeGeneric = f.guard.registerConfirmation(() => { calls++; return false })
  f.state.ctx = null; await ownedConfirmTick(); await f.overlayIdle(); assert.equal(f.unmounts.length, 1)
  assert.equal((await f.done(await f.clickExternal())).failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(calls, 1); assert.equal(f.router.currentRoute.value.fullPath, calendarOwnedSource()); assert.equal(f.guard.isDirty(), true); assert.equal(ownedConfirmDialog.systemDialogState.visible, false); removeGeneric()
})

test('calendar real queryterm101 to102 same instance preserves new remark after old true cancellation8', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('旧学期101备注'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true); const current = await f.click102(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  await f.assertQueryReuse('102', 'events'); await f.openCreate(); await f.fillRemark('当前学期102备注'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.cancelled); f.assertDraft('当前学期102备注', calendarOwnedSource('102')); assert.equal(f.unmounts.length, 0); removeGeneric()
})

test('calendar real queryterm101 to102 same instance preserves new remark after old false abort4', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('旧学期101否定备注'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true); const current = await f.click102(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  await f.assertQueryReuse('102', 'events'); await f.openCreate(); await f.fillRemark('当前学期102否定备注'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('当前学期102否定备注', calendarOwnedSource('102')); assert.equal(f.unmounts.length, 0); removeGeneric()
})

test('calendar real events to holiday tab same instance preserves new remark after old true cancellation8', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('旧事件页备注'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true); const current = await f.clickHoliday(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  await f.assertQueryReuse('101', 'holiday'); await f.openCreate(); await f.fillRemark('当前节假日页备注'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.cancelled); f.assertDraft('当前节假日页备注', calendarOwnedSource('101', 'holiday')); assert.equal(f.unmounts.length, 0); removeGeneric()
})

test('calendar real events to holiday tab same instance preserves new remark after old false abort4', async t => {
  const f = await calendarOwnedFixture(t); await f.openCreate(); await f.fillRemark('旧事件页否定备注'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true); const current = await f.clickHoliday(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  await f.assertQueryReuse('101', 'holiday'); await f.openCreate(); await f.fillRemark('当前节假日页否定备注'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('当前节假日页否定备注', calendarOwnedSource('101', 'holiday')); assert.equal(f.unmounts.length, 0); removeGeneric()
})

// TimeSlot owns only its existing shared confirmation callback. All transports
// below are declared read-only inputs, not real account authorization or database rows.
// RouterLink query changes exercise actual page watchers, not a substituted picker.
const timeslotOwnedSource = (tab = 'periods', id = '') => `/admin/academic-affairs/time-slots?tab=${tab}${id ? `&slotId=${id}` : ''}&returnToken=DECLARED_TIMESLOT_RETURN_POSITION`
const TIMESLOT_OWNED_TARGET = '/admin/academic-affairs/calendar'
const timeslotOwnedSlots = () => ['101', '102'].map((slotId, index) => ({ slotId, slotNo: index + 1, slotName: `声明独立节次${slotId}`, startTime: '', endTime: '', campusCode: '', enabled: true, status: 'ENABLED', version: 0, timeBandCount: 0, referenceCount: 0, referenceStatus: 'UNUSED' }))
async function timeslotOwnedFixture(t, { bands = false, start = timeslotOwnedSource() } = {}) {
  const keys = ['window', 'document', 'Document', 'ShadowRoot', 'requestAnimationFrame', 'cancelAnimationFrame']
  const previous = Object.fromEntries(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const install = (key, value) => Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  class TimeSlotDocumentHost {
    constructor() { this.listeners = {}; this.activeElement = null; this.body = calendarOwnedNode('body'); this.body.ownerDocument = this; this.body.offsetHeight = 0 }
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) }
    removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) }
  }
  install('Document', TimeSlotDocumentHost); install('ShadowRoot', class TimeSlotShadowRootHost {})
  install('document', new TimeSlotDocumentHost())
  const listeners = {}, rafJobs = new Set()
  install('window', { addEventListener(name, fn) { (listeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { listeners[name] = (listeners[name] || []).filter(value => value !== fn) }, getComputedStyle() { return { transitionDelay: '0s', transitionDuration: '0s', animationDelay: '0s', animationDuration: '0s' } } })
  install('requestAnimationFrame', fn => { const job = ownedConfirmSetImmediate(() => { rafJobs.delete(job); fn(0) }); rafJobs.add(job); return job })
  install('cancelAnimationFrame', job => { calendarOwnedClearImmediate(job); rafJobs.delete(job) })
  const patterns = ['academicAffairs.timeslot.view', 'academicAffairs.timeslot.manage', 'academicAffairs.calendar.view', ...(bands ? ['academicAffairs.classTimeBand.view', 'academicAffairs.classTimeBand.manage'] : [])]
  // Nonreactive claims intentionally prove fresh Flow identity reads.
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_USER', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_CONTEXT_A' }
  const context = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionPatterns: [...patterns] })
  const state = ownedConfirmVue.reactive({ ctx: context('DECLARED_TIMESLOT_SCOPE_A') })
  const identity = () => ownedConfirmAcademicIdentity(claims, state.ctx || {})
  const reads = [], slotResponses = [], bandResponses = [], mounts = [], unmounts = [], updates = [], transitions = [], errors = [], warnings = []
  const prohibited = () => { throw new Error('作息确认回归禁止新增/保存/启停/删除/模板检查应用及其他业务请求') }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    reads.push({ path, method: options.method || 'GET', params: options.params || {} })
    assert.ok(reads.length <= 4, 'Exact case maximum is one/two/three/four natural reads')
    if (path === '/academic-affairs/time-slots') {
      assert.deepEqual(options.params, options.params?.includeDisabled ? { includeDisabled: true } : {})
      return { items: bands ? timeslotOwnedSlots() : [] }
    }
    const match = /^\/academic-affairs\/time-slots\/(101|102)\/time-bands$/.exec(path)
    assert.ok(bands && match, 'Only declared full slots list and selected 101/102 empty bands')
    assert.equal(options.params, undefined)
    return { items: [] }
  }
  const source = ownedConfirmRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const originalAPI = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${source}\nreturn academicAffairsApi`)(request, prohibited, prohibited, prohibited, prohibited, prohibited)
  const api = { ...originalAPI,
    getTimeSlots(includeDisabled) { return originalAPI.getTimeSlots(includeDisabled).then(response => { slotResponses.push({ includeDisabled, response: structuredClone(response) }); return response }) },
    getTimeBands(id) { return originalAPI.getTimeBands(id).then(response => { bandResponses.push({ id: String(id), response: structuredClone(response) }); return response }) }
  }
  const Button = ownedConfirmCompile('components/ui/AppButton.vue'), Drawer = ownedConfirmCompile('components/ui/AppDrawer.vue')
  const TextInput = ownedConfirmCompile('components/common/form/AppTextInput.vue'), NumberInput = ownedConfirmCompile('components/common/form/AppNumberInput.vue')
  const FieldHint = ownedConfirmCompile('components/common/AppFieldHint.vue')
  const FormItem = ownedConfirmCompile('components/common/form/AppFormItem.vue', { AppHelpTooltip: ownedConfirmVisual('DeclaredUnusedTimeSlotHelp'), AppFieldHint: FieldHint })
  const TimeSlot = ownedConfirmCompile('modules/academicAffairs/views/AaTimeSlotView.vue', {
    ModulePageShell: ownedConfirmVisual('DeclaredTimeSlotShell'), AppButton: Button, AppDrawer: Drawer,
    DataTable: ownedConfirmVisual('DeclaredUnopenedSlotRows'), StatusTag: ownedConfirmVisual('DeclaredTimeSlotStatus'),
    LoadingState: ownedConfirmVisual('DeclaredTimeSlotLoading'), ErrorState: ownedConfirmVisual('DeclaredTimeSlotError'), EmptyState: ownedConfirmVisual('DeclaredTimeSlotEmpty'),
    AppSectionCard: ownedConfirmVisual('DeclaredTimeSlotCardWithoutHeaderExtra'), AppTextInput: TextInput, AppNumberInput: NumberInput, AppFormItem: FormItem,
    AppTimePicker: ownedConfirmVisual('DeclaredUnchangedBlankSlotTimes'), AppDatePicker: ownedConfirmVisual('DeclaredUnchangedBlankBandDates'), AppTimeSlotPicker: ownedConfirmVisual('DeclaredUnusedBandPicker'),
    AppConfirmDialog: ownedConfirmVisual('DeclaredUnopenedObjectSwitchDialog'), AppInlineAlert: ownedConfirmVisual('DeclaredTimeSlotAlert'), AaTimeSlotTemplatePanel: ownedConfirmVisual('DeclaredUnopenedTemplate'),
    academicAffairsApi: api, toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission: ownedConfirmMatchPermission, systemConfirm: ownedConfirmDialog.systemConfirm
  })
  const renderer = ownedConfirmVue.createRenderer({ createElement: tag => calendarOwnedNode(tag), createText: value => calendarOwnedNode('#text', value), createComment: value => calendarOwnedNode('#comment', value),
    setText(node, value) { node.text = value }, setElementText(node, value) { node.text = value; node.children = [] },
    parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    querySelector(selector) { assert.equal(selector, 'body'); return document.body }, patchProp(node, key, _old, value) { node.props[key] = value },
    insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
    remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } }
  })
  const Parent = { render() { return ownedConfirmH(ownedConfirmRouter.RouterView, null, { default: ({ Component }) => {
    const owner = state.ctx?.ctxKey
    return state.ctx && Component ? ownedConfirmH(Component, { key: owner, ctx: state.ctx,
      onVnodeMounted(vnode) { if (vnode.type?.name === 'AaTimeSlotView') mounts.push({ owner, uid: vnode.component.uid }) },
      onVnodeUpdated(vnode) { if (vnode.type?.name === 'AaTimeSlotView') updates.push({ owner, uid: vnode.component.uid, tab: String(router.currentRoute.value.query.tab || ''), slotId: String(router.currentRoute.value.query.slotId || '') }) },
      onVnodeUnmounted(vnode) { if (vnode.type?.name === 'AaTimeSlotView') unmounts.push({ owner, uid: vnode.component.uid }) }
    }) : ownedConfirmH('p', '声明上下文读取中，无API')
  } }) } }
  const router = ownedConfirmRouter.createRouter({ history: ownedConfirmRouter.createMemoryHistory(), routes: [{ path: '/admin/academic-affairs', component: Parent, meta: { moduleCode: 'ACADEMIC_AFFAIRS' }, children: [
    { path: 'time-slots', name: 'aa-time-slots', component: TimeSlot, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.timeslot.view' } },
    { path: 'calendar', name: 'aa-calendar', component: { render: () => ownedConfirmH('p', '声明只读校历目的页，无API') }, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.calendar.view' } }
  ] }] })
  ownedConfirmGate.clearPermissionPatterns(); ownedConfirmGate.setModuleEntitlements(['academicAffairs']); ownedConfirmGate.setPermissionPatterns(patterns)
  let queuedObserver = null
  const observedTo = new WeakMap()
  const removePermission = router.beforeEach(to => { assert.equal(ownedConfirmGate.canEnterRoute(to.meta), true); if (queuedObserver) { const observer = queuedObserver; queuedObserver = null; observer.to = to; observedTo.set(to, observer); observer.entered.resolve(to) } return true })
  const disposeDirty = installDirtyFormGuard(router)
  const removeAfter = router.afterEach((to, from, failure) => { transitions.push({ to: to.fullPath, from: from.fullPath, failureType: failure?.type ?? null }); const observer = observedTo.get(to); if (observer) { observer.result = { to, from, failure }; observer.completed.resolve(observer.result) } })
  const removeError = router.onError(error => errors.push({ source: 'router', message: error.message }))
  const storage = new Map()
  const returns = teachingOwnedReturnStore({ getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }, { now: () => 0, token: () => 'DECLARED_TIMESLOT_RETURN_POSITION' })
  assert.equal(returns.remember({ path: TIMESLOT_OWNED_TARGET, query: {} }, identity()), 'DECLARED_TIMESLOT_RETURN_POSITION')
  const slotInputs = () => ownedConfirmWalk(document.body).filter(node => node.type === 'input' && node.props.placeholder === '选填，如 第一大节')
  const masks = () => ownedConfirmWalk(document.body).filter(node => node.type === 'div' && String(node.props.class || '').split(/\s+/).includes('app-drawer-mask'))
  const overlayIdle = async () => { await ownedConfirmBounded((async () => { while (slotInputs().length || masks().length || rafJobs.size) await ownedConfirmTick() })()) }
  let app, stopped = false
  t.after(async () => {
    ownedConfirmDialog.finishSystemDialog(false)
    if (app && !stopped) { app.unmount(); stopped = true }
    await overlayIdle(); await ownedConfirmTick(); disposeDirty(); removePermission(); removeAfter(); removeError(); ownedConfirmGate.clearPermissionPatterns()
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  })
  await router.push(start); await router.isReady()
  const root = calendarOwnedNode('root')
  const Host = { setup() { ownedConfirmVue.provide('academicFlow', { identity, returns,
    back: async (token, fallback) => { const position = returns.resolve(token, identity()); await router.push(position?.path || fallback) }, restorePosition() {}
  }); return () => ownedConfirmH('main', {}, [
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: timeslotOwnedSource('bands', '101') }, { default: () => '声明的公开时间段配置链接' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: timeslotOwnedSource('bands', '102') }, { default: () => '声明的公开节次102配置链接' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: TIMESLOT_OWNED_TARGET }, { default: () => '声明的公开作息外部链接' }), ownedConfirmH(ownedConfirmRouter.RouterView)
  ]) } }
  app = renderer.createApp(Host); app.use(router)
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ source: 'vue', message: error.message })
  app.mount(root)
  const guard = window.__SAAS_DIRTY_FORM_GUARD__
  const dispatch = node => { assert.equal(!!node.props.disabled, false); const handlers = node.props.onClick; assert.ok(handlers); const event = { type: 'click', target: node, currentTarget: node }; for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event) }
  const publicInput = () => {
    const tab = router.currentRoute.value.query.tab
    const container = tab === 'bands' ? root : document.body
    if (tab !== 'bands') { const drawers = ownedConfirmWalk(document.body).filter(node => node.type === 'aside' && node.props.role === 'dialog' && node.props['aria-label'] === '新增节次'); assert.equal(drawers.length, 1) }
    const fields = ownedConfirmWalk(container).filter(node => node.type === 'input' && node.props.placeholder === (tab === 'bands' ? '选填，如 夏季作息' : '选填，如 第一大节'))
    assert.equal(fields.length, 1); assert.equal(!!fields[0].props.disabled, false); return fields[0]
  }
  const waitReadback = async (count, selected = '') => {
    await ownedConfirmBounded((async () => { while (reads.length < count || (selected && bandResponses.at(-1)?.id !== selected)) await ownedConfirmTick() })())
    await ownedConfirmTick(); assert.equal(reads.length, count)
    for (const { response } of slotResponses) assert.deepEqual(response, { code: 0, data: bands ? timeslotOwnedSlots() : [], message: 'ok' })
    for (const { response } of bandResponses) assert.deepEqual(response, { code: 0, data: [], message: 'ok' })
    assert.equal(slotResponses.length + bandResponses.length, count)
  }
  const selected = router.currentRoute.value.query.slotId || ''
  await waitReadback(selected ? 2 : 1, selected); assert.equal(mounts.length, 1); assert.equal(unmounts.length, 0); assert.equal(slotInputs().length, 0)
  const openDraft = async () => {
    if (router.currentRoute.value.query.tab !== 'bands') { const buttons = ownedConfirmWalk(root).filter(node => node.type === 'button' && ownedConfirmText(node) === '新增节次'); assert.equal(buttons.length, 1); dispatch(buttons[0]); await ownedConfirmTick() }
    assert.equal(publicInput().props.value, '')
  }
  const fillName = async value => { const field = publicInput(); const handlers = field.props.onInput; assert.ok(handlers); field.value = value; const event = { type: 'input', target: field, currentTarget: field }; for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event); await ownedConfirmTick(); assert.equal(publicInput().props.value, value); assert.equal(guard.isDirty(), true) }
  const assertDraft = (value, source = start) => { assert.equal(router.currentRoute.value.fullPath, source); assert.equal(router.options.history.location, source); assert.equal(publicInput().props.value, value); assert.equal(guard.isDirty(), true) }
  const begin = () => { assert.equal(queuedObserver, null); const observer = { entered: ownedConfirmDeferred(), completed: ownedConfirmDeferred(), to: null, result: null }; queuedObserver = observer; return observer }
  const click = async (tag, label) => { const nodes = ownedConfirmWalk(root).filter(node => node.type === tag && ownedConfirmText(node) === label); assert.equal(nodes.length, 1); const observer = begin(); dispatch(nodes[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const clickReturn = () => click('button', '返回原位置'), clickExternal = () => click('a', '声明的公开作息外部链接')
  const clickBands = () => click('a', '声明的公开时间段配置链接'), click102 = () => click('a', '声明的公开节次102配置链接')
  const waitDialog = async () => { await ownedConfirmBounded((async () => { while (!ownedConfirmDialog.systemDialogState.visible) await ownedConfirmTick() })()); assert.equal(ownedConfirmDialog.systemDialogState.title, '确认离开当前页面'); assert.equal(ownedConfirmDialog.systemDialogState.confirmText, '放弃修改并离开') }
  const done = async observer => { const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result }
  const settle = async (observer, accepted) => { ownedConfirmDialog.finishSystemDialog(accepted); return done(observer) }
  const replaceOwner = async () => { state.ctx = null; await ownedConfirmTick(); assert.equal(unmounts.length, 1); await overlayIdle(); state.ctx = context('DECLARED_TIMESLOT_SCOPE_B'); await waitReadback(2); assert.equal(mounts.length, 2); assert.notEqual(mounts[0].uid, mounts[1].uid); assert.equal(slotInputs().length, 0) }
  const assertQueryReuse = async (id, count) => {
    await waitReadback(count, id); await overlayIdle()
    assert.equal(state.ctx.ctxKey, 'DECLARED_TIMESLOT_SCOPE_A'); assert.equal(mounts.length, 1); assert.equal(unmounts.length, 0)
    const active = updates.filter(event => event.tab === 'bands' && event.slotId === id); assert.ok(active.length > 0); assert.equal(active.at(-1).uid, mounts[0].uid)
    assert.equal(router.currentRoute.value.fullPath, timeslotOwnedSource('bands', id)); assert.equal(router.options.history.location, timeslotOwnedSource('bands', id))
    assert.equal(slotResponses.at(-1).includeDisabled, true); assert.equal(bandResponses.at(-1).id, id)
  }
  return { router, state, claims, identity, guard, reads, slotResponses, bandResponses, mounts, unmounts, updates, transitions, publicInput, openDraft, fillName, assertDraft, clickReturn, clickExternal, clickBands, click102, waitDialog, done, settle, replaceOwner, assertQueryReuse }
}

test('timeslot old unmounted positive preserves B public slot-name draft', async t => {
  const f = await timeslotOwnedFixture(t); await f.openDraft(); await f.fillName('声明A旧节次名称'); const old = await f.clickReturn(); await f.waitDialog()
  await f.replaceOwner(); await f.openDraft(); await f.fillName('声明B当前节次名称')
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  f.assertDraft('声明B当前节次名称'); assert.equal(f.reads.length, 2)
})

test('timeslot old unmounted negative preserves B and B genuine new confirmation remains effective', async t => {
  const f = await timeslotOwnedFixture(t); await f.openDraft(); await f.fillName('声明A旧名称'); const old = await f.clickReturn(); await f.waitDialog()
  await f.replaceOwner(); await f.openDraft(); await f.fillName('声明B当前名称')
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明B当前名称')
  const current = await f.clickReturn(); await f.waitDialog(); assert.notEqual(old.to, current.to)
  assert.equal((await f.settle(current, true)).failure, undefined)
  assert.equal(f.router.currentRoute.value.fullPath, TIMESLOT_OWNED_TARGET); assert.equal(f.guard.isDirty(), false); assert.equal(f.reads.length, 2)
})

test('timeslot same-instance actual context prop update refuses an old positive without extra list reads', async t => {
  const f = await timeslotOwnedFixture(t); await f.openDraft(); await f.fillName('声明原范围名称'); const old = await f.clickReturn(); await f.waitDialog()
  const uid = f.mounts[0].uid, key = f.state.ctx.ctxKey
  f.state.ctx = { ...f.state.ctx, dataScope: { ...f.state.ctx.dataScope, scopeName: '声明更新范围' } }; await ownedConfirmTick()
  assert.equal(f.state.ctx.ctxKey, key); assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0)
  assert.ok(f.updates.length > 0); assert.equal(f.updates.at(-1).uid, uid); assert.equal(f.reads.length, 1)
  await f.fillName('声明更新范围新名称')
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明更新范围新名称')
})

test('timeslot fresh nonreactive Flow identity invalidates old positive with unchanged context and instance', async t => {
  const f = await timeslotOwnedFixture(t); const ctx = f.state.ctx, uid = f.mounts[0].uid, identity = f.identity()
  await f.openDraft(); await f.fillName('声明身份A名称'); const old = await f.clickReturn(); await f.waitDialog()
  f.claims.activeContextId = 'DECLARED_CONTEXT_B'; await ownedConfirmTick()
  assert.notEqual(f.identity(), identity); assert.equal(f.state.ctx, ctx); assert.equal(f.mounts.length, 1); assert.equal(f.mounts[0].uid, uid); assert.equal(f.unmounts.length, 0); assert.equal(f.reads.length, 1)
  await f.fillName('声明身份B名称')
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明身份B名称')
})

test('timeslot healthy same-owner actual positive keeps normal public navigation', async t => {
  const f = await timeslotOwnedFixture(t); await f.openDraft(); await f.fillName('声明健康名称'); const current = await f.clickReturn(); await f.waitDialog()
  assert.equal((await f.settle(current, true)).failure, undefined); assert.equal(f.router.currentRoute.value.fullPath, TIMESLOT_OWNED_TARGET); assert.equal(f.guard.isDirty(), false); assert.equal(f.reads.length, 1)
})

test('timeslot healthy same-owner actual cancel retains its public draft', async t => {
  const f = await timeslotOwnedFixture(t); await f.openDraft(); await f.fillName('声明取消后名称'); const current = await f.clickReturn(); await f.waitDialog()
  assert.equal((await f.settle(current, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明取消后名称'); assert.equal(f.reads.length, 1)
})

test('timeslot old positive after a newer generic-published valid URL commit retains Router cancellation8', async t => {
  const f = await timeslotOwnedFixture(t); await f.openDraft(); await f.fillName('声明旧名称'); const old = await f.clickReturn(); await f.waitDialog(); await f.replaceOwner()
  await f.openDraft(); await f.fillName('声明新范围名称')
  // Public generic discard collaborator allows the newer link, not a second real dialog.
  const removeGeneric = f.guard.registerConfirmation(() => true)
  const current = await f.clickExternal(); assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to)
  assert.equal(f.router.currentRoute.value.fullPath, TIMESLOT_OWNED_TARGET); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.cancelled)
  assert.equal(f.router.currentRoute.value.fullPath, TIMESLOT_OWNED_TARGET); assert.equal(f.router.options.history.location, TIMESLOT_OWNED_TARGET); assert.equal(f.reads.length, 2); removeGeneric()
})

test('timeslot real periods-to-bands query reuse preserves new public band draft after old positive cancellation8', async t => {
  const f = await timeslotOwnedFixture(t, { bands: true }); await f.openDraft(); await f.fillName('声明旧节次名称'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true), current = await f.clickBands()
  assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to); await f.assertQueryReuse('101', 3)
  assert.deepEqual(f.reads.map(row => row.path), ['/academic-affairs/time-slots', '/academic-affairs/time-slots', '/academic-affairs/time-slots/101/time-bands'])
  await f.openDraft(); await f.fillName('声明101新时间段名称'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.cancelled); f.assertDraft('声明101新时间段名称', timeslotOwnedSource('bands', '101')); removeGeneric()
})

test('timeslot real periods-to-bands query reuse preserves new public band draft after old negative abort4', async t => {
  const f = await timeslotOwnedFixture(t, { bands: true }); await f.openDraft(); await f.fillName('声明旧节次名称'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true), current = await f.clickBands()
  assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to); await f.assertQueryReuse('101', 3)
  assert.deepEqual(f.reads.map(row => row.path), ['/academic-affairs/time-slots', '/academic-affairs/time-slots', '/academic-affairs/time-slots/101/time-bands'])
  await f.openDraft(); await f.fillName('声明101新时间段名称'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明101新时间段名称', timeslotOwnedSource('bands', '101')); removeGeneric()
})

test('timeslot real selected slot101-to102 query reuse preserves new band draft after old positive cancellation8', async t => {
  const f = await timeslotOwnedFixture(t, { bands: true, start: timeslotOwnedSource('bands', '101') }); await f.openDraft(); await f.fillName('声明101旧时间段名称'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true), current = await f.click102()
  assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to); await f.assertQueryReuse('102', 4)
  assert.deepEqual(f.reads.map(row => row.path), ['/academic-affairs/time-slots', '/academic-affairs/time-slots/101/time-bands', '/academic-affairs/time-slots', '/academic-affairs/time-slots/102/time-bands'])
  assert.deepEqual(f.bandResponses.map(row => row.id), ['101', '102']); await f.openDraft(); await f.fillName('声明102新时间段名称'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure.type, ownedConfirmRouter.NavigationFailureType.cancelled); f.assertDraft('声明102新时间段名称', timeslotOwnedSource('bands', '102')); removeGeneric()
})

test('timeslot real selected slot101-to102 query reuse preserves new band draft after old negative abort4', async t => {
  const f = await timeslotOwnedFixture(t, { bands: true, start: timeslotOwnedSource('bands', '101') }); await f.openDraft(); await f.fillName('声明101旧时间段名称'); const old = await f.clickReturn(); await f.waitDialog()
  const removeGeneric = f.guard.registerConfirmation(() => true), current = await f.click102()
  assert.equal((await f.done(current)).failure, undefined); assert.notEqual(old.to, current.to); await f.assertQueryReuse('102', 4)
  assert.deepEqual(f.reads.map(row => row.path), ['/academic-affairs/time-slots', '/academic-affairs/time-slots/101/time-bands', '/academic-affairs/time-slots', '/academic-affairs/time-slots/102/time-bands'])
  assert.deepEqual(f.bandResponses.map(row => row.id), ['101', '102']); await f.openDraft(); await f.fillName('声明102新时间段名称'); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, false)).failure.type, ownedConfirmRouter.NavigationFailureType.aborted); f.assertDraft('声明102新时间段名称', timeslotOwnedSource('bands', '102')); removeGeneric()
})


// Original A7 shared approval concurrency: these declared public input callers do
// not model native trusted events or a business page. The original shared guard,
// original systemDialog and installed RouterLink/MemoryRouter run unchanged.
async function sharedDiscardApprovalFixture(t) {
  const source = '/admin/academic-affairs/terms/new'
  const targetA = '/admin/academic-affairs/terms', targetB = '/admin/academic-affairs/calendar'
  const previous = Object.fromEntries(['window', 'document', 'Element'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const documentListeners = new Map(), windowListeners = new Map()
  const listenerHost = listeners => ({
    addEventListener(name, fn) { (listeners.get(name) || (listeners.set(name, []), listeners.get(name))).push(fn) },
    removeEventListener(name, fn) { listeners.set(name, (listeners.get(name) || []).filter(value => value !== fn)) }
  })
  const install = (key, value) => Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  install('window', listenerHost(windowListeners)); install('document', listenerHost(documentListeners)); install('Element', class DeclaredSharedDiscardElement {})
  const node = (type, text = '') => ({ type, text, props: {}, children: [], parent: null, value: '', getAttribute(key) { return this.props[key] ?? null } })
  const renderer = ownedConfirmVue.createRenderer({
    createElement: tag => node(tag), createText: value => node('#text', value), createComment: value => node('#comment', value),
    setText(n, value) { n.text = value }, setElementText(n, value) { n.text = value; n.children = [] },
    parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
    patchProp(n, key, _old, value) { n.props[key] = value; if (key === 'value') n.value = value },
    insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(n); else parent.children.splice(index, 0, n) },
    remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } }
  })
  const root = node('root'), draft = ownedConfirmVue.reactive({ name: '' }), warnings = [], errors = [], transitions = [], openings = []
  const DeclaredSource = { name: 'DeclaredSharedDiscardPublicInput', setup() { return () => ownedConfirmH('section', [
    ownedConfirmH('input', { 'aria-label': '声明并发草稿名称', value: draft.name, onInput(event) { draft.name = event.target.value; window.__SAAS_DIRTY_FORM_GUARD__.markDirty() } }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: targetA }, { default: () => '声明返回学期列表' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: targetB }, { default: () => '声明查看校历' })
  ]) } }
  const DeclaredTarget = { name: 'DeclaredReadOnlySharedDiscardTarget', setup: () => () => ownedConfirmH('p', '只读目标；无业务请求') }
  const history = ownedConfirmRouter.createMemoryHistory()
  const router = ownedConfirmRouter.createRouter({ history, routes: [
    { path: source, name: 'aa-term-new', component: DeclaredSource },
    { path: targetA, name: 'aa-terms', component: DeclaredTarget },
    { path: targetB, name: 'aa-calendar', component: DeclaredTarget }
  ] })
  const aHeld = ownedConfirmDeferred(), bHeld = ownedConfirmDeferred(), releaseA = ownedConfirmDeferred(), releaseB = ownedConfirmDeferred()
  const promises = []
  let exactA = null, exactB = null, visitsB = 0, app = null
  const disposeGuard = installDirtyFormGuard(router)
  const guard = window.__SAAS_DIRTY_FORM_GUARD__
  const removeDialog = ownedConfirmVue.watch(() => ownedConfirmDialog.systemDialogState.visible, visible => { if (visible) openings.push(true) }, { flush: 'sync' })
  const removeLate = router.beforeResolve(to => {
    if (to.fullPath === targetA) { exactA = to; aHeld.resolve(); return releaseA.promise }
    if (to.fullPath === targetB && ++visitsB === 1) { exactB = to; bHeld.resolve(); return releaseB.promise }
    return true
  })
  const removeAfter = router.afterEach((to, from, failure) => transitions.push({ to, from, failure, dirtyAfterOriginalGuard: guard.isDirty() }))
  const removeError = router.onError(error => errors.push({ source: 'router', message: error.message }))
  t.after(async () => {
    releaseA.resolve(true); releaseB.resolve(true); ownedConfirmDialog.finishSystemDialog(false)
    await ownedConfirmBounded(Promise.allSettled(promises))
    app?.unmount(); removeDialog(); removeAfter(); removeLate(); removeError(); disposeGuard(); history.destroy()
    const cleaned = [...documentListeners.values(), ...windowListeners.values()].every(list => list.length === 0)
    const guardRemoved = !Object.hasOwn(window, '__SAAS_DIRTY_FORM_GUARD__')
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    assert.deepEqual(warnings, []); assert.deepEqual(errors, []); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
    assert.equal(cleaned, true); assert.equal(guardRemoved, true)
    for (const [key, descriptor] of Object.entries(previous)) assert.deepEqual(Object.getOwnPropertyDescriptor(globalThis, key), descriptor)
  })
  assert.equal(await router.push(source), undefined); await router.isReady()
  app = renderer.createApp({ render: () => ownedConfirmH(ownedConfirmRouter.RouterView) })
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ source: 'vue', message: error.message })
  app.use(router); app.mount(root); await ownedConfirmTick()
  const input = () => { const fields = ownedConfirmWalk(root).filter(n => n.type === 'input' && n.props['aria-label'] === '声明并发草稿名称'); assert.equal(fields.length, 1); return fields[0] }
  input().value = '公开输入的合成草稿'
  input().props.onInput({ type: 'input', target: input(), currentTarget: input() }); await ownedConfirmTick()
  assert.equal(input().value, draft.name); assert.equal(guard.isDirty(), true)
  const click = label => {
    const links = ownedConfirmWalk(root).filter(n => n.type === 'a' && ownedConfirmText(n) === label)
    assert.equal(links.length, 1)
    const event = { type: 'click', button: 0, target: links[0], currentTarget: links[0], defaultPrevented: false, preventDefault() { this.defaultPrevented = true } }
    const promise = links[0].props.onClick(event)
    assert.equal(typeof promise?.then, 'function'); assert.equal(event.defaultPrevented, true); promises.push(promise)
    return promise
  }
  const waitDialog = async () => {
    await ownedConfirmBounded((async () => { while (!ownedConfirmDialog.systemDialogState.visible) await ownedConfirmTick() })())
    assert.equal(ownedConfirmDialog.systemDialogState.title, '确认离开当前页面')
    assert.equal(ownedConfirmDialog.systemDialogState.confirmText, '放弃修改并离开')
  }
  const done = async promise => { const result = await ownedConfirmBounded(promise); await ownedConfirmTick(); return result }
  const startBoth = async () => {
    const promiseA = click('声明返回学期列表'); await waitDialog(); assert.equal(openings.length, 1)
    ownedConfirmDialog.finishSystemDialog(true); await ownedConfirmBounded(aHeld.promise); await ownedConfirmTick()
    assert.equal(ownedConfirmDialog.systemDialogState.visible, false); assert.equal(router.currentRoute.value.fullPath, source)
    const promiseB = click('声明查看校历'); await waitDialog(); assert.equal(openings.length, 2)
    ownedConfirmDialog.finishSystemDialog(true); await ownedConfirmBounded(bHeld.promise); await ownedConfirmTick()
    assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
    assert.ok(exactA && exactB && exactA !== exactB, 'Only actual distinct normalized request references establish identity')
    assert.equal(router.currentRoute.value.fullPath, source); assert.equal(history.location, source); assert.equal(guard.isDirty(), true)
    return { promiseA, promiseB }
  }
  return { router, history, guard, source, targetA, targetB, transitions, openings, releaseA, releaseB, startBoth, done, input, click, waitDialog,
    exactA: () => exactA, exactB: () => exactB, visibleInputs: () => ownedConfirmWalk(root).filter(n => n.type === 'input').map(n => n.value) }
}

test('shared discard approval survives an older actual cancelled8 afterEach until the newer accepted navigation commits', async t => {
  const f = await sharedDiscardApprovalFixture(t), { promiseA, promiseB } = await f.startBoth()
  f.releaseA.resolve(true)
  const resultA = await f.done(promiseA)
  assert.equal(ownedConfirmRouter.isNavigationFailure(resultA, ownedConfirmRouter.NavigationFailureType.cancelled), true); assert.equal(resultA.type, 8)
  assert.equal(f.transitions.filter(row => row.to === f.exactA() && row.failure?.type === 8).length, 1)
  assert.equal(f.transitions.filter(row => row.to === f.exactB()).length, 0)
  assert.equal(f.router.currentRoute.value.fullPath, f.source); assert.equal(f.guard.isDirty(), true)
  f.releaseB.resolve(true)
  assert.equal(await f.done(promiseB), undefined)
  assert.equal(f.router.currentRoute.value.fullPath, f.targetB); assert.equal(f.history.location, f.targetB)
  assert.equal(f.transitions.filter(row => row.to === f.exactB() && !row.failure).length, 1)
  assert.equal(f.guard.isDirty(), false, 'Older failed afterEach cannot erase the newer accepted discard approval')
  assert.deepEqual(f.visibleInputs(), []); assert.equal(f.openings.length, 2)
})

test('a newer accepted commit remains clean when the older real navigation completes cancelled8 afterward', async t => {
  const f = await sharedDiscardApprovalFixture(t), { promiseA, promiseB } = await f.startBoth()
  f.releaseB.resolve(true)
  assert.equal(await f.done(promiseB), undefined)
  assert.equal(f.router.currentRoute.value.fullPath, f.targetB); assert.equal(f.history.location, f.targetB); assert.equal(f.guard.isDirty(), false)
  f.releaseA.resolve(true)
  const resultA = await f.done(promiseA)
  assert.equal(ownedConfirmRouter.isNavigationFailure(resultA, ownedConfirmRouter.NavigationFailureType.cancelled), true); assert.equal(resultA.type, 8)
  assert.equal(f.router.currentRoute.value.fullPath, f.targetB); assert.equal(f.history.location, f.targetB); assert.equal(f.guard.isDirty(), false)
  assert.deepEqual(f.visibleInputs(), []); assert.equal(f.openings.length, 2)
})

test('a rejected newer leave keeps its draft and a fresh independently confirmed retry can discard successfully', async t => {
  const f = await sharedDiscardApprovalFixture(t), { promiseA, promiseB } = await f.startBoth()
  f.releaseA.resolve(true)
  const resultA = await f.done(promiseA); assert.equal(resultA.type, 8)
  f.releaseB.resolve(false)
  const resultB = await f.done(promiseB)
  assert.equal(ownedConfirmRouter.isNavigationFailure(resultB, ownedConfirmRouter.NavigationFailureType.aborted), true); assert.equal(resultB.type, 4)
  assert.equal(f.router.currentRoute.value.fullPath, f.source); assert.equal(f.history.location, f.source)
  assert.equal(f.input().value, '公开输入的合成草稿'); assert.equal(f.guard.isDirty(), true)
  const retry = f.click('声明查看校历'); await f.waitDialog(); assert.equal(f.openings.length, 3)
  ownedConfirmDialog.finishSystemDialog(true)
  assert.equal(await f.done(retry), undefined)
  assert.equal(f.router.currentRoute.value.fullPath, f.targetB); assert.equal(f.history.location, f.targetB); assert.equal(f.guard.isDirty(), false)
  assert.deepEqual(f.visibleInputs(), [])
})


// Confirmation-await draft revisions are separate from source-owner changes and
// input after confirmation during a later guard. These are supported component
// events in the actual SFC, not native input through the modal mask.
test('a later public slot-name input invalidates the pending positive and a fresh actual confirmation can leave normally', async t => {
  const f = await timeslotOwnedFixture(t), source = f.router.currentRoute.value.fullPath, ctx = f.state.ctx, identity = f.identity()
  await f.openDraft(); await f.fillName('确认前的名称A')
  const field = f.publicInput(), old = await f.clickReturn(); await f.waitDialog()
  assert.equal(f.guard.isDirty(), true)
  await f.fillName('确认等待期间的新名称B')
  assert.equal(f.publicInput(), field); assert.equal(f.state.ctx, ctx); assert.equal(f.identity(), identity)
  assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0); assert.equal(f.reads.length, 1)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  const rejected = await f.settle(old, true)
  assert.equal(rejected.failure?.type, ownedConfirmRouter.NavigationFailureType.aborted)
  f.assertDraft('确认等待期间的新名称B', source)
  assert.equal(f.publicInput(), field); assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0); assert.equal(f.reads.length, 1)
  const fresh = await f.clickReturn(); await f.waitDialog()
  assert.notEqual(fresh.to, old.to, 'The next actual confirmation belongs to a fresh normalized attempt')
  assert.equal((await f.settle(fresh, true)).failure, undefined)
  assert.equal(f.router.currentRoute.value.fullPath, TIMESLOT_OWNED_TARGET); assert.equal(f.router.options.history.location, TIMESLOT_OWNED_TARGET)
  assert.equal(f.guard.isDirty(), false); assert.equal(f.reads.length, 1)
})

test('published markSaved during a pending confirmation keeps clean navigation healthy despite the changed revision', async t => {
  const f = await timeslotOwnedFixture(t)
  await f.openDraft(); await f.fillName('声明已确认保存的名称')
  const old = await f.clickReturn(); await f.waitDialog()
  // Existing published acknowledgment API only: no actual save request, database
  // write or persistence success is represented by this declared collaborator.
  f.guard.markSaved()
  assert.equal(f.guard.isDirty(), false); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure, undefined)
  assert.equal(f.router.currentRoute.value.fullPath, TIMESLOT_OWNED_TARGET); assert.equal(f.router.options.history.location, TIMESLOT_OWNED_TARGET)
  assert.equal(f.guard.isDirty(), false); assert.equal(f.reads.length, 1)
})

test('public input after a published saved acknowledgment still invalidates the older pending confirmation', async t => {
  const f = await timeslotOwnedFixture(t), source = f.router.currentRoute.value.fullPath, ctx = f.state.ctx, identity = f.identity()
  await f.openDraft(); await f.fillName('声明已保存的旧名称')
  const field = f.publicInput(), old = await f.clickReturn(); await f.waitDialog()
  // The published markSaved API is an explicit unit-contract input, not a fake
  // business save. The later name uses the actual TextInput producer naturally.
  f.guard.markSaved(); assert.equal(f.guard.isDirty(), false)
  await f.fillName('保存确认后新输入的名称B')
  assert.equal(f.publicInput(), field); assert.equal(f.state.ctx, ctx); assert.equal(f.identity(), identity)
  assert.equal(f.guard.isDirty(), true); assert.equal(ownedConfirmDialog.systemDialogState.visible, true)
  assert.equal((await f.settle(old, true)).failure?.type, ownedConfirmRouter.NavigationFailureType.aborted)
  f.assertDraft('保存确认后新输入的名称B', source)
  assert.equal(f.publicInput(), field); assert.equal(f.mounts.length, 1); assert.equal(f.unmounts.length, 0); assert.equal(f.reads.length, 1)
})


// The public route.component Promise declares a cold dynamic-import scheduling window.
// This is after the real dialog settles, before Router's beforeResolve phase, not
// measured network latency, trusted browser input or an arbitrary later-guard fix.
async function lazyConfirmationFixture(t) {
  const previous = Object.fromEntries(['window', 'document', 'Document', 'ShadowRoot'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const install = (key, value) => Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  class DeclaredDocumentHost { constructor() { this.listeners = {}; this.activeElement = null } addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) } removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) } }
  install('Document', DeclaredDocumentHost); install('ShadowRoot', class DeclaredShadowRootHost {})
  install('document', new DeclaredDocumentHost())
  const windowListeners = {}
  install('window', { addEventListener(name, fn) { (windowListeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { windowListeners[name] = (windowListeners[name] || []).filter(value => value !== fn) } })
  const patterns = ['academicAffairs.term.view', 'academicAffairs.term.manage', 'academicAffairs.dashboard.view']
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_USER', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_CONTEXT' }
  const makeContext = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionPatterns: [...patterns], permissionVersion: 1 })
  const state = ownedConfirmVue.reactive({ ctx: makeContext('DECLARED_SCOPE_A') })
  const warnings = [], errors = [], transitions = [], mounts = [], unmounts = []
  const prohibited = () => { throw new Error('此确认回归禁止保存/创建/业务API') }
  const Button = ownedConfirmCompile('components/ui/AppButton.vue')
  const Form = ownedConfirmCompile('modules/academicAffairs/views/AaTermFormView.vue', {
    ModulePageShell: ownedConfirmVisual('DeclaredUnrelatedShellVisual'), AppButton: Button,
    AppSectionCard: ownedConfirmVisual('DeclaredUnrelatedCardVisual'), AppSelect: ownedConfirmVisual('DeclaredUnusedTermNumberVisual'),
    academicAffairsApi: { createTerm: prohibited }, toast: { success: prohibited, error: prohibited }, matchPermission: ownedConfirmMatchPermission,
    systemConfirm: ownedConfirmDialog.systemConfirm
  })
  const renderer = ownedConfirmVue.createRenderer({ createElement: tag => ownedConfirmNode(tag), createText: value => ownedConfirmNode('#text', value), createComment: value => ownedConfirmNode('#comment', value),
    setText(node, value) { node.text = value }, setElementText(node, value) { node.text = value; node.children = [] },
    parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
    patchProp(node, key, _old, value) { node.props[key] = value },
    insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
    remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } }
  })
  const lazyTarget = ownedConfirmDeferred(), loaderEntered = ownedConfirmDeferred()
  const loader = { calls: 0, dialogVisibleAtEntry: null }
  const loadTarget = () => { loader.calls++; loader.dialogVisibleAtEntry = ownedConfirmDialog.systemDialogState.visible; loaderEntered.resolve(); return lazyTarget.promise }
  const attempts = []
  const Body = { render: () => ownedConfirmH('p', '声明的只读目的页，无API') }
  const Parent = { render() { return ownedConfirmH(ownedConfirmRouter.RouterView, null, { default: ({ Component }) => {
    const owner = state.ctx?.ctxKey
    return state.ctx && Component ? ownedConfirmH(Component, { key: owner, ctx: state.ctx,
      onVnodeMounted: () => mounts.push(owner), onVnodeUnmounted: () => unmounts.push(owner) }) : ownedConfirmH('p', '声明上下文读取中，无API')
  } }) } }
  const router = ownedConfirmRouter.createRouter({ history: ownedConfirmRouter.createMemoryHistory(), routes: [{ path: OWNED_CONFIRM_OVERVIEW, component: Parent, meta: { moduleCode: 'ACADEMIC_AFFAIRS' }, children: [
    { path: '', name: 'aa-dashboard', component: Body, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.dashboard.view' } },
    { path: 'terms/new', name: 'aa-term-new', component: Form, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.manage' } },
    { path: 'terms', name: 'aa-terms', component: loadTarget, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.view' } },
    { path: 'terms/:termId', name: 'aa-term-detail', component: Body, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.term.view' } }
  ] }] })
  ownedConfirmGate.clearPermissionPatterns(); ownedConfirmGate.setModuleEntitlements(['academicAffairs']); ownedConfirmGate.setPermissionPatterns(patterns)
  let queuedObserver = null
  const observedTo = new WeakMap()
  const removePermission = router.beforeEach(to => {
    assert.equal(ownedConfirmGate.canEnterRoute(to.meta), true)
    if (queuedObserver) { const observer = queuedObserver; queuedObserver = null; observer.to = to; observedTo.set(to, observer); observer.entered.resolve(to) }
    return true
  })
  const disposeDirty = installDirtyFormGuard(router)
  const removeAfter = router.afterEach((to, from, failure) => {
    transitions.push({ to: to.fullPath, from: from.fullPath, failureType: failure?.type ?? null })
    const observer = observedTo.get(to)
    if (observer) { observer.result = { to, from, failure }; observer.completed.resolve(observer.result) }
  })
  const removeError = router.onError(error => errors.push({ source: 'router', message: error.message }))
  let app, stopped = false
  t.after(async () => {
    ownedConfirmDialog.finishSystemDialog(false)
    lazyTarget.resolve(Body)
    for (const observer of attempts) { if (observer.to) await ownedConfirmBounded(observer.completed.promise) }
    if (app && !stopped) { app.unmount(); stopped = true }
    await ownedConfirmTick(); disposeDirty(); removePermission(); removeAfter(); removeError(); ownedConfirmGate.clearPermissionPatterns(); router.options.history.destroy()
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
    assert.deepEqual(warnings, []); assert.deepEqual(errors, []); assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  })
  await router.push(OWNED_CONFIRM_SOURCE); await router.isReady()
  const root = ownedConfirmNode('root')
  const Host = { setup() { ownedConfirmVue.provide('academicFlow', { identity: () => ownedConfirmAcademicIdentity(claims, state.ctx || {}) }); return () => ownedConfirmH('main', {}, [
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: OWNED_CONFIRM_TARGET }, { default: () => '声明的公开外部学期列表链接' }),
    ownedConfirmH(ownedConfirmRouter.RouterLink, { to: '/admin/academic-affairs/terms/3' }, { default: () => '声明的公开只读详情链接' }), ownedConfirmH(ownedConfirmRouter.RouterView)
  ]) } }
  app = renderer.createApp(Host); app.use(router)
  app.config.warnHandler = warning => warnings.push(String(warning))
  app.config.errorHandler = error => errors.push({ source: 'vue', message: error.message })
  app.mount(root); await ownedConfirmTick()
  const publicInput = () => { const fields = ownedConfirmWalk(root).filter(node => node.type === 'input' && node.props.id === 'aa-term-name'); assert.equal(fields.length, 1); assert.equal(!!fields[0].props.disabled, false); return fields[0] }
  const beginNavigation = () => { assert.equal(queuedObserver, null); const observer = { entered: ownedConfirmDeferred(), completed: ownedConfirmDeferred(), to: null, result: null }; queuedObserver = observer; attempts.push(observer); return observer }
  const dispatch = node => { assert.equal(!!node.props.disabled, false); const event = { type: 'click', target: node, currentTarget: node }; const handlers = node.props.onClick; assert.ok(handlers); for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event) }
  const clickReturn = async () => { const buttons = ownedConfirmWalk(root).filter(node => node.type === 'button' && ownedConfirmText(node) === '返回列表'); assert.equal(buttons.length, 1); const observer = beginNavigation(); dispatch(buttons[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const clickExternal = async () => { const links = ownedConfirmWalk(root).filter(node => node.type === 'a' && ownedConfirmText(node) === '声明的公开外部学期列表链接'); assert.equal(links.length, 1); const observer = beginNavigation(); dispatch(links[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const clickDetail = async () => { const links = ownedConfirmWalk(root).filter(node => node.type === 'a' && ownedConfirmText(node) === '声明的公开只读详情链接'); assert.equal(links.length, 1); const observer = beginNavigation(); dispatch(links[0]); await ownedConfirmBounded(observer.entered.promise); return observer }
  const waitDialog = async () => { await ownedConfirmBounded((async () => { while (!ownedConfirmDialog.systemDialogState.visible) await ownedConfirmTick() })()); assert.equal(ownedConfirmDialog.systemDialogState.title, '确认离开当前页面'); assert.equal(ownedConfirmDialog.systemDialogState.confirmText, '放弃修改并离开') }
  const fillName = async value => { const field = publicInput(); assert.ok(field.listeners.input?.length); field.value = value; for (const listener of field.listeners.input) listener({ type: 'input', target: field }); window.__SAAS_DIRTY_FORM_GUARD__.markDirty(); await ownedConfirmTick(); assert.equal(publicInput().value, value); assert.equal(window.__SAAS_DIRTY_FORM_GUARD__.isDirty(), true) }
  const replaceOwner = async () => { state.ctx = null; await ownedConfirmTick(); assert.ok(unmounts.includes('DECLARED_SCOPE_A')); state.ctx = makeContext('DECLARED_SCOPE_B'); await ownedConfirmTick(); assert.ok(mounts.includes('DECLARED_SCOPE_B')) }
  const settle = async (observer, accepted) => { ownedConfirmDialog.finishSystemDialog(accepted); const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result }
  return { router, root, state, loader, clickDetail, resolveTarget: () => lazyTarget.resolve(Body), waitLoader: async () => { await ownedConfirmBounded(loaderEntered.promise); await ownedConfirmTick(); assert.equal(loader.calls, 1); assert.equal(loader.dialogVisibleAtEntry, false); assert.equal(ownedConfirmDialog.systemDialogState.visible, false); assert.equal(router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE) }, warnings, errors, transitions, mounts, unmounts, publicInput, clickReturn, clickExternal, waitDialog, fillName, replaceOwner, settle,
    guard: window.__SAAS_DIRTY_FORM_GUARD__, finish: ownedConfirmDialog.finishSystemDialog, done: async observer => { const result = await ownedConfirmBounded(observer.completed.promise); await ownedConfirmTick(); return result } }
}

test('new public term name during post-confirm component resolution aborts only that request and a fresh confirmation still succeeds', async t => {
  const fixture = await lazyConfirmationFixture(t)
  await fixture.fillName('确认前的学期名称A')
  const field = fixture.publicInput(), identity = JSON.stringify(fixture.state.ctx)
  const oldNavigation = await fixture.clickReturn(); await fixture.waitDialog()
  assert.equal(fixture.loader.calls, 0)
  fixture.finish(true); await fixture.waitLoader()
  assert.equal(fixture.publicInput(), field)
  assert.equal(fixture.mounts.length, 1); assert.equal(fixture.unmounts.length, 0)
  await fixture.fillName('组件加载期间的新学期名称B')
  assert.equal(fixture.publicInput(), field); assert.equal(JSON.stringify(fixture.state.ctx), identity)
  fixture.resolveTarget(); const oldResult = await fixture.done(oldNavigation)
  assert.equal(oldResult.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_SOURCE)
  assert.equal(fixture.publicInput(), field); assert.equal(field.value, '组件加载期间的新学期名称B')
  assert.equal(fixture.guard.isDirty(), true)
  assert.equal(fixture.mounts.length, 1); assert.equal(fixture.unmounts.length, 0)
  const freshNavigation = await fixture.clickReturn(); await fixture.waitDialog()
  assert.notEqual(oldNavigation.to, freshNavigation.to)
  const freshResult = await fixture.settle(freshNavigation, true)
  assert.equal(freshResult.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.guard.isDirty(), false); assert.equal(fixture.loader.calls, 1)
})

test('published markSaved while confirmation waits and during lazy resolution keeps clean leaving healthy', async t => {
  const fixture = await lazyConfirmationFixture(t); await fixture.fillName('声明保存前的学期草稿')
  const navigation = await fixture.clickReturn(); await fixture.waitDialog()
  // Published API contract only: no actual database save or acknowledgement is claimed.
  fixture.guard.markSaved(); assert.equal(fixture.guard.isDirty(), false)
  fixture.finish(true); await fixture.waitLoader()
  fixture.guard.markSaved(); assert.equal(fixture.guard.isDirty(), false)
  fixture.resolveTarget(); const result = await fixture.done(navigation)
  assert.equal(result.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.guard.isDirty(), false)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
})

test('accepted saved-clean early return still revokes later new public input during lazy component resolution', async t => {
  const fixture = await lazyConfirmationFixture(t); await fixture.fillName('确认时的学期名称A')
  const field = fixture.publicInput()
  const navigation = await fixture.clickReturn(); await fixture.waitDialog()
  fixture.guard.markSaved(); assert.equal(fixture.guard.isDirty(), false)
  fixture.finish(true); await fixture.waitLoader()
  assert.equal(fixture.guard.isDirty(), false)
  fixture.guard.markSaved()
  await fixture.fillName('保存后加载期间新输入的学期名称B')
  assert.equal(fixture.publicInput(), field)
  fixture.resolveTarget(); const result = await fixture.done(navigation)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_SOURCE)
  assert.equal(fixture.publicInput().value, '保存后加载期间新输入的学期名称B')
  assert.equal(fixture.guard.isDirty(), true)
  assert.equal(fixture.mounts.length, 1); assert.equal(fixture.unmounts.length, 0)
})

test('a newer public navigation committed during old component resolution retains natural cancelled8 and its new dirty revision', async t => {
  const fixture = await lazyConfirmationFixture(t); await fixture.fillName('旧请求确认的学期名称')
  const oldNavigation = await fixture.clickReturn(); await fixture.waitDialog()
  fixture.finish(true); await fixture.waitLoader()
  // Existing published generic handler contract authorizes the new link; this is
  // neither a second fake dialog nor an actual Detail business-page interaction.
  const release = fixture.guard.registerConfirmation(() => true)
  try {
    const newNavigation = await fixture.clickDetail(); const newer = await fixture.done(newNavigation)
    assert.notEqual(oldNavigation.to, newNavigation.to)
    assert.equal(newer.failure, undefined)
    assert.equal(fixture.router.currentRoute.value.fullPath, '/admin/academic-affairs/terms/3')
    assert.equal(fixture.router.options.history.location, '/admin/academic-affairs/terms/3')
    fixture.guard.markDirty(); assert.equal(fixture.guard.isDirty(), true)
    fixture.resolveTarget(); const old = await fixture.done(oldNavigation)
    assert.equal(old.failure.type, ownedConfirmRouter.NavigationFailureType.cancelled)
    assert.equal(fixture.router.currentRoute.value.fullPath, '/admin/academic-affairs/terms/3')
    assert.equal(fixture.router.options.history.location, '/admin/academic-affairs/terms/3')
    assert.equal(fixture.guard.isDirty(), true)
    assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  } finally { release() }
})


test('a pristine public Form return preserves new input during component loading and then permits a fresh actual confirmation', async t => {
  const fixture = await lazyConfirmationFixture(t)
  const field = fixture.publicInput(), context = JSON.stringify(fixture.state.ctx)
  assert.equal(field.value, ''); assert.equal(fixture.guard.isDirty(), false)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  const old = await fixture.clickReturn(); await fixture.waitLoader()
  assert.equal(fixture.publicInput(), field); assert.equal(field.value, '')
  assert.equal(fixture.guard.isDirty(), false)
  assert.equal(fixture.mounts.length, 1); assert.equal(fixture.unmounts.length, 0)
  await fixture.fillName('初始无草稿导航加载期间的新名称B')
  assert.equal(fixture.publicInput(), field); assert.equal(JSON.stringify(fixture.state.ctx), context)
  fixture.resolveTarget(); const result = await fixture.done(old)
  assert.equal(result.failure.type, ownedConfirmRouter.NavigationFailureType.aborted)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_SOURCE)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_SOURCE)
  assert.equal(fixture.publicInput(), field); assert.equal(field.value, '初始无草稿导航加载期间的新名称B')
  assert.equal(fixture.guard.isDirty(), true)
  assert.equal(fixture.mounts.length, 1); assert.equal(fixture.unmounts.length, 0)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  const fresh = await fixture.clickReturn(); await fixture.waitDialog()
  assert.notEqual(fresh.to, old.to)
  assert.equal((await fixture.settle(fresh, true)).failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.guard.isDirty(), false); assert.equal(fixture.loader.calls, 1)
})

test('a pristine public Form departure without new input completes normally without a confirmation', async t => {
  const fixture = await lazyConfirmationFixture(t)
  assert.equal(fixture.publicInput().value, ''); assert.equal(fixture.guard.isDirty(), false)
  const navigation = await fixture.clickReturn(); await fixture.waitLoader()
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
  assert.equal(fixture.guard.isDirty(), false)
  fixture.resolveTarget(); const result = await fixture.done(navigation)
  assert.equal(result.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.guard.isDirty(), false)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
})

test('published markSaved after a new public input during pristine component loading preserves clean successful navigation', async t => {
  const fixture = await lazyConfirmationFixture(t)
  assert.equal(fixture.guard.isDirty(), false)
  const navigation = await fixture.clickReturn(); await fixture.waitLoader()
  await fixture.fillName('加载期间已由声明保存回调确认的新名称')
  assert.equal(fixture.guard.isDirty(), true)
  // Existing published API only; no save request, persistence or DB success claim.
  fixture.guard.markSaved(); assert.equal(fixture.guard.isDirty(), false)
  fixture.resolveTarget(); const result = await fixture.done(navigation)
  assert.equal(result.failure, undefined)
  assert.equal(fixture.router.currentRoute.value.fullPath, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.router.options.history.location, OWNED_CONFIRM_TARGET)
  assert.equal(fixture.guard.isDirty(), false)
  assert.equal(ownedConfirmDialog.systemDialogState.visible, false)
})

test('clean-entry revision checks preserve same-reference and internship exemptions and ignore unguarded sources', async () => {
  const previous = Object.fromEntries(['window', 'document'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const term = { name: 'aa-term-new', path: OWNED_CONFIRM_SOURCE, fullPath: OWNED_CONFIRM_SOURCE, query: {} }
  const rows = [
    { label: 'same fullPath', from: term, to: { ...term }, expectedDirty: true, expectedResolve: true },
    { label: 'internship plans same batch', from: { name: 'internship-plans', path: '/admin/internship/plans', fullPath: '/admin/internship/plans?batchId=7&tab=list', query: { batchId: '7', tab: 'list' } },
      to: { name: 'internship-plans', path: '/admin/internship/plans', fullPath: '/admin/internship/plans?batchId=7&tab=overview', query: { batchId: '7', tab: 'overview' } }, expectedDirty: true, expectedResolve: true },
    { label: 'internship student section only', from: { name: 'internship-student-detail', path: '/admin/internship/students/9', fullPath: '/admin/internship/students/9?section=overview', query: { section: 'overview' } },
      to: { name: 'internship-student-detail', path: '/admin/internship/students/9', fullPath: '/admin/internship/students/9?section=profile', query: { section: 'profile' } }, expectedDirty: true, expectedResolve: true },
    { label: 'unguarded source', from: { name: 'aa-dashboard', path: OWNED_CONFIRM_OVERVIEW, fullPath: OWNED_CONFIRM_OVERVIEW, query: {} },
      to: { name: 'aa-terms', path: OWNED_CONFIRM_TARGET, fullPath: OWNED_CONFIRM_TARGET, query: {} }, expectedDirty: false, expectedResolve: true },
    { label: 'ordinary guarded control', from: term, to: { name: 'aa-terms', path: OWNED_CONFIRM_TARGET, fullPath: OWNED_CONFIRM_TARGET, query: {} }, expectedDirty: true, expectedResolve: false }
  ]
  try {
    for (const row of rows) {
      Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: { addEventListener() {}, removeEventListener() {} } })
      Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { addEventListener() {}, removeEventListener() {} } })
      let before, resolve, after
      // Focused registration-predicate contract only. No actual Router navigation,
      // native UI or artificially held asynchronous guard is claimed for this table.
      const router = { currentRoute: { value: row.from },
        beforeEach(fn) { before = fn; return () => { if (before === fn) before = null } },
        beforeResolve(fn) { resolve = fn; return () => { if (resolve === fn) resolve = null } },
        afterEach(fn) { after = fn; return () => { if (after === fn) after = null } } }
      const dispose = installDirtyFormGuard(router)
      try {
        const guard = window.__SAAS_DIRTY_FORM_GUARD__
        assert.equal(guard.isDirty(), false, row.label)
        assert.equal(await before(row.to, row.from), true, row.label)
        assert.equal(ownedConfirmDialog.systemDialogState.visible, false, row.label)
        guard.markDirty()
        assert.equal(guard.isDirty(), row.expectedDirty, row.label)
        assert.equal(await resolve(row.to, row.from), row.expectedResolve, row.label)
        assert.equal(guard.isDirty(), row.expectedDirty, row.label)
      } finally { dispose() }
      assert.equal(before, null); assert.equal(resolve, null); assert.equal(after, null)
    }
  } finally {
    for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] }
  }
})
