import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission, findActiveInPlan } from '../src/config/navPlan.js'
import { createMemoryHistory, createRouter } from 'vue-router'
import { academicAffairsRoutes } from '../src/modules/academicAffairs/academic-affairs.routes.js'
import * as flow from '../src/modules/academicAffairs/academicFlowContext.js'
import { parse } from '@vue/compiler-sfc'
import { installDirtyFormGuard } from '../src/router/dirtyFormGuard.js'

function page(name, dependencies = {}, extra = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { window: { __SAAS_DIRTY_FORM_GUARD__: dependencies.dirtyGuard || { markSaved() {} } }, dependencies: { ...flow, currentUserFromToken: () => ({ tenantId: 'school', userId: 'staff', currentRoleCode: 'SCHOOL_ADMIN' }), matchPermission, toast: { success() {}, error() {}, warning() {} }, ...dependencies } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = Object.assign(component.data(), component.methods, {
    ctx: { permissionPatterns: ['academicAffairs.term.*'], dataScope: { scope: 'SCHOOL' } },
    $route: { params: { termId: 'term-a' }, query: {} }, $router: { push() {} }, $options: component
  }, extra)
  for (const [key, getter] of Object.entries(component.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state), configurable: true })
  if (name === 'AaTermListView') state.currentGate = flow.createAcademicRequestGate(() => state.contextKey())
  return state
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

for (const name of ['AaTermWeeksView', 'AaTeachingWeekConfigView']) {
  test(`${name} does not replace an unavailable explicit term with an editable default`, async () => {
    const state = page(name, { loadAcademicTermCatalog: async () => [{ termId: 'other', status: 'DRAFT' }],
      academicAffairsApi: { getCurrentTerm: async () => ({ code: 0, data: { termId: 'other' } }) } },
      { $route: { query: { termId: 'missing' } } })
    await state.refreshTermCatalog()
    assert.equal(state.termId, ''); assert.match(state.catalogError, /入口指定的学期不可用/)
  })
}

test('term status commands require manage permission and retain the confirmed object', async () => {
  const writes = [], reply = deferred()
  const state = page('AaTermStatusView', { academicAffairsApi: { freezeTerm: id => { writes.push(id); return reply.promise } } })
  state.load = () => {}
  const row = { termId: 'confirmed-term', status: 'PUBLISHED' }
  state.ctx.permissionPatterns = ['academicAffairs.term.view']; state.askFreeze(row)
  assert.equal(state.freezeDialog.visible, false)
  state.ctx.permissionPatterns = ['academicAffairs.term.manage']; state.askFreeze(row)
  row.termId = 'changed-row'
  const pending = state.doFreeze(); await state.doFreeze()
  assert.deepEqual(writes, ['confirmed-term'])
  reply.resolve({ code: 0 }); await pending
})

test('a term status confirmation is invalid after the scope changes away and back', async () => {
  let writes = 0
  const state = page('AaTermStatusView', { academicAffairsApi: { freezeTerm: async () => { writes++; return { code: 0 } } } })
  state.askFreeze({ termId: 'a', status: 'PUBLISHED' }); state.scopeVersion += 2
  await state.doFreeze(); assert.equal(writes, 0)
})

test('the status workspace requires a real unfreeze reason and sends it with the frozen term', async () => {
  const writes = []
  const state = page('AaTermStatusView', { academicAffairsApi: { unfreezeTerm: async (...args) => { writes.push(args); return { code: 0 } } } })
  state.load = () => {}; state.askUnfreeze({ termId: 'frozen', status: 'FROZEN' })
  await state.doUnfreeze(); assert.equal(writes.length, 0)
  state.unfreezeReason = '隔离验证恢复办理'; await state.doUnfreeze()
  assert.deepEqual(writes, [['frozen', '隔离验证恢复办理']])
})

test('a stale current authority cannot replace the result of a newer scope read', async () => {
  const old = deferred(), latest = deferred(); let calls = 0
  const state = page('AaTermCurrentView', { academicAffairsApi: {
    getCurrentTerm: () => (++calls === 1 ? old.promise : latest.promise),
    getTermSwitchLog: async () => ({ code: 0, data: { list: [] } })
  } })
  const first = state.loadCurrent(); state.scopeVersion++
  const second = state.loadCurrent()
  latest.resolve({ code: 0, data: { termId: 'new-term', currentAuthority: 'CALENDAR_GOVERNANCE' } }); await second
  old.resolve({ code: 0, data: { termId: 'old-term', canDirectSwitch: true } }); await first
  assert.equal(state.current.termId, 'new-term'); assert.equal(state.directSwitchAllowed, false)
})

test('late authority response cannot restore publication permission in a changed scope', async () => {
  const response = deferred()
  const state = page('AaTermListView', { academicAffairsApi: { getCurrentTerm: () => response.promise } })
  const pending = state.loadCurrentContext()
  state.ctx = { permissionPatterns: ['academicAffairs.term.view'], dataScope: { scope: 'COLLEGE' } }
  response.resolve({ code: 0, data: { canDirectSwitch: true, currentAuthority: 'AA_TERM_COMPAT' } })
  await pending
  assert.equal(state.currentContext, null); assert.equal(state.publishAllowed, false)
})

test('term detail confirmation cannot be submitted for a newly selected term', async () => {
  const writes = []
  const state = page('AaTermDetailView', { academicAffairsApi: { freezeTerm: async id => { writes.push(id); return { code: 0 } } } },
    { loading: false, detail: { allowedActions: { freeze: true } } })
  state.hydrateForm({}); state.openAction('FREEZE')
  state.$route.params.termId = 'term-b'; await state.confirmAction()
  assert.deepEqual(writes, [])
})

test('late term save cannot replace a new scope draft', async () => {
  const response = deferred()
  const state = page('AaTermDetailView', { academicAffairsTermDetailApi: { update: () => response.promise } },
    { loading: false, detail: { allowedActions: { editBasic: true }, version: 1 } })
  state.hydrateForm({ termName: '旧名称' }); state.form.termName = '提交的名称'
  state.preview = { canSave: true }; state.previewSignature = state.currentSignature
  const pending = state.save(); state.pageEpoch += 1; state.form.termName = '新上下文草稿'
  response.resolve({ code: 0, data: { termName: '旧请求结果' } }); await pending
  assert.equal(state.form.termName, '新上下文草稿')
})

test('term list carries its captured return position into creation and details', () => {
  const destinations = []
  const state = page('AaTermListView', {}, { academicFlow: { captureReturn: () => 'saved-page-2' }, $router: { push: route => destinations.push(route) } })
  state.goCreate(); state.goDetail({ termId: 'term-a' })
  assert.equal(destinations[0].query.returnToken, 'saved-page-2')
  assert.equal(destinations[1].query.returnToken, 'saved-page-2')
  const backs = []
  const detail = page('AaTermDetailView', {}, { $route: { params: { termId: 'term-a' }, query: { returnToken: 'saved-page-2' } },
    academicFlow: { back: (token, fallback) => backs.push({ token, fallback }) } })
  detail.goBack(); assert.equal(backs[0].token, 'saved-page-2')
})

test('all term entry pages require known authority, school scope and manage permission before current-changing actions', () => {
  const list = page('AaTermListView')
  assert.equal(list.directSwitchAllowed, false)
  list.currentLoading = false
  assert.equal(list.directSwitchAllowed, false)
  list.currentContext = { currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
  assert.equal(list.directSwitchAllowed, true)
  list.ctx.dataScope.scope = 'COLLEGE'
  assert.equal(list.directSwitchAllowed, false)
  list.ctx.dataScope.scope = 'SCHOOL'
  list.ctx.permissionPatterns = ['academicAffairs.term.view']
  assert.equal(list.directSwitchAllowed, false)
  assert.equal(list.publishAllowed, false)
  const current = page('AaTermCurrentView', {}, { loadingCurrent: false, current: { canDirectSwitch: true }, currentError: '冲突' })
  assert.equal(current.directSwitchAllowed, false)
  const detail = page('AaTermDetailView', {}, { loading: false, currentContextLoading: false, detail: { allowedActions: { editBasic: true, freeze: true } }, ctx: { permissionPatterns: ['academicAffairs.term.view'], dataScope: { scope: 'SCHOOL' } } })
  assert.equal(detail.canEditName, false)
  assert.equal(detail.actionAllowed('FREEZE'), false)
})

test('governance draft publication does not offer or call the direct current-term command', async () => {
  let publishes = 0
  const state = page('AaTermListView', { academicAffairsApi: {
    publishTerm: async () => { publishes++; return { code: 0 } },
    setCurrentTerm() { throw new Error('governance must not switch here') }
  } }, { currentLoading: false, currentContext: { currentAuthority: 'CALENDAR_GOVERNANCE', canDirectSwitch: false } })
  state.loadCurrentContext = async () => {}
  state.load = async () => {}
  assert.equal(state.directSwitchAllowed, false)
  assert.equal(state.publishAllowed, true)
  state.askPublish({ termId: 'draft', status: 'DRAFT', yearCode: '2026-2027', termNo: 1 })
  assert.equal(state.publishDialog.title, '发布学期')
  await state.doPublish()
  assert.equal(publishes, 1)
  state.currentContext.canDirectSwitch = true
  const published = { termId: 'published', status: 'PUBLISHED' }
  state.askPublish(published)
  assert.equal(state.publishDialog.visible, false, '统一管理时不得打开直接切换确认')
  state.publishDialog = { visible: true, submitting: false, row: published, contextKey: state.contextKey() }
  await state.doPublish()
  assert.equal(publishes, 1, '强行调用提交方法也不能绕过统一管理')
})

test('a pending context refresh immediately disables current-changing actions', async () => {
  const response = deferred()
  const state = page('AaTermListView', { academicAffairsApi: { getCurrentTerm: () => response.promise } }, { currentLoading: false, currentContext: { canDirectSwitch: true } })
  assert.equal(state.directSwitchAllowed, true)
  const pending = state.loadCurrentContext()
  assert.equal(state.directSwitchAllowed, false)
  response.resolve({ code: 409, message: '多个当前学期' })
  await pending
  assert.equal(state.currentError, '多个当前学期')
  assert.equal(state.directSwitchAllowed, false)
})

test('changing detail route while loading cannot show or edit the previous term', async () => {
  const responses = [deferred(), deferred()]
  let call = 0
  const state = page('AaTermDetailView', { academicAffairsTermDetailApi: { get: () => responses[call++].promise } })
  const first = state.load()
  state.$route.params.termId = 'term-b'
  const second = state.load()
  responses[1].resolve({ code: 0, data: { termId: 'term-b', termName: '乙学期' } })
  await second
  responses[0].resolve({ code: 0, data: { termId: 'term-a', termName: '甲学期' } })
  await first
  assert.equal(state.detail.termId, 'term-b')
  assert.equal(state.form.termName, '乙学期')
})

test('editing during impact preview invalidates the returned approval to save', async () => {
  const response = deferred()
  const state = page('AaTermDetailView', { academicAffairsTermDetailApi: { preview: () => response.promise } }, { loading: false, detail: { allowedActions: { editBasic: true } } })
  state.hydrateForm({ termName: '原名称' })
  state.form.termName = '第一个名称'
  const pending = state.previewChange()
  state.form.termName = '第二个名称'
  response.resolve({ code: 0, data: { canSave: true } })
  await pending
  assert.equal(state.previewCurrent, false)
})

test('version conflict retains the user draft and requires a new preview', async () => {
  const state = page('AaTermDetailView', { academicAffairsTermDetailApi: {
    update: async (id, body) => { assert.equal(id, 'term-a'); assert.equal(body.expectedVersion, 3); return { code: 'APPROVAL_VERSION_CONFLICT', message: '已被其他人修改' } }
  } }, { loading: false, detail: { version: 3, allowedActions: { editBasic: true } } })
  state.hydrateForm({ termName: '原名称' })
  state.form.termName = '我的修改'
  state.preview = { canSave: true }
  state.previewSignature = state.currentSignature
  await state.save()
  assert.equal(state.form.termName, '我的修改')
  assert.equal(state.previewCurrent, false)
})

test('unfreeze sends the actual operator reason and rejects an empty one', async () => {
  let calls = 0
  const state = page('AaTermDetailView', { academicAffairsApi: { unfreezeTerm: async (id, reason) => { calls++; assert.equal(reason, '恢复本学期业务办理'); return { code: 0 } } } }, { loading: false, detail: { status: 'FROZEN' } })
  state.loadCurrentContext = async () => {}
  state.load = async () => {}
  state.hydrateForm({})
  state.openAction('UNFREEZE')
  await state.confirmAction({ reason: '' })
  assert.equal(calls, 0)
  await state.confirmAction({ reason: '恢复本学期业务办理' })
  assert.equal(calls, 1)
})

test('new term validates whole teaching weeks and exam placement, then opens the created detail', async () => {
  let target, saved = 0
  const state = page('AaTermFormView', { dirtyGuard: { markSaved() { saved++ } }, academicAffairsApi: { createTerm: async () => ({ code: 0, data: { termId: 'new-term' } }) } }, { $router: { push: route => { target = route } } })
  Object.assign(state.form, { yearCode: '2026-2027', teachingWeeks: 17.5 })
  assert.equal(state.validate(), false)
  Object.assign(state.form, { teachingWeeks: 17, examWeekStart: 18 })
  assert.equal(state.validate(), false)
  state.form.examWeekStart = 17
  await state.submit()
  assert.equal(target.name, 'aa-term-detail')
  assert.equal(target.params.termId, 'new-term')
  assert.equal(saved, 1)
})

test('detail route coexists with all static term menus', () => {
  const router = createRouter({ history: createMemoryHistory(), routes: academicAffairsRoutes })
  for (const path of ['new', 'years', 'current', 'weeks', 'teaching-weeks', 'status', 'archive-status', 'switch-log']) assert.notEqual(router.resolve(`/admin/academic-affairs/terms/${path}`).name, 'aa-term-detail')
  assert.equal(router.resolve('/admin/academic-affairs/terms/123').name, 'aa-term-detail')
  for (const path of ['new', '123']) assert.equal(findActiveInPlan(`/admin/academic-affairs/terms/${path}`).modKey, 'aa-terms')
})

test('changing week selection while a request is pending cannot show the old term weeks', async () => {
  const old = deferred()
  const state = page('AaTermWeeksView', { academicAffairsApi: { getTermWeeks: id => id === 'old' ? old.promise : Promise.resolve({ code: 0, data: [{ weekNo: 1, remark: '新学期' }] }) } })
  state.termId = 'old'
  const pending = state.loadWeeks()
  state.termId = 'new'
  await state.loadWeeks()
  old.resolve({ code: 0, data: [{ weekNo: 1, remark: '旧学期' }] })
  await pending
  assert.equal(state.weeks[0].remark, '新学期')
})

test('saving teaching weeks explicitly clears optional exam start and preserves the selected draft', async () => {
  let body
  const rows = [{ termId: 'current', status: 'PUBLISHED' }, { termId: 'draft', status: 'DRAFT', teachingWeeks: 20, examWeekStart: null }]
  const state = page('AaTeachingWeekConfigView', { loadAcademicTermCatalog: async () => rows,
    academicAffairsTermDetailApi: {
      get: async id => ({ code: 0, data: { termId: id, version: 4, status: 'DRAFT', teachingWeeks: 20, examWeekStart: null, allowedActions: { editBasic: true } } }),
      update: async (id, payload) => { assert.equal(id, 'draft'); body = payload; return { code: 0, data: { termId: id, version: 4, status: 'DRAFT', ...payload, allowedActions: { editBasic: true } } } }
    }, academicAffairsApi: {
    getTermWeeks: async () => ({ code: 0, data: [] }),
    getCurrentTerm: async () => ({ code: 0, data: { termId: 'current' } })
  } }, { termsLoading: false, terms: rows, termId: 'draft', detail: { version: 3, status: 'DRAFT', allowedActions: { editBasic: true } }, form: { teachingWeeks: 20, examWeekStart: null } })
  state.preview = { canSave: true }; state.previewSignature = state.signature
  await state.submit()
  await state.refreshTermCatalog()
  assert.equal(body.examWeekStart, null)
  assert.equal(body.expectedVersion, 3)
  assert.equal(state.termId, 'draft')
})

test('teaching week changes invalidate an earlier impact preview and block replay', async () => {
  let writes = 0
  const state = page('AaTeachingWeekConfigView', { academicAffairsTermDetailApi: { update: async () => { writes++; return { code: 0 } } } },
    { termsLoading: false, terms: [{ termId: 'draft', status: 'DRAFT' }], termId: 'draft', detail: { version: 2, status: 'DRAFT', allowedActions: { editBasic: true } }, form: { teachingWeeks: 20 } })
  state.preview = { canSave: true }; state.previewSignature = state.signature
  state.form.teachingWeeks = 10
  await state.submit(); assert.equal(writes, 0)
})

test('teaching week impact from an old object cannot approve the new object', async () => {
  const reply = deferred()
  const state = page('AaTeachingWeekConfigView', { academicAffairsTermDetailApi: { preview: () => reply.promise } },
    { termsLoading: false, terms: [{ termId: 'draft', status: 'DRAFT' }], termId: 'draft', detail: { version: 2, status: 'DRAFT', allowedActions: { editBasic: true } }, form: { teachingWeeks: 20 } })
  const pending = state.previewChange(); state.termId = 'other'
  reply.resolve({ code: 0, data: { termId: 'draft', canSave: true } }); await pending
  assert.equal(state.previewCurrent, false)
})

test('year aggregation cannot apply an earlier scope response', async () => {
  const reply = deferred()
  const state = page('AaAcademicYearView', { academicAffairsApi: { getAcademicYears: () => reply.promise, getCurrentTerm: async () => ({ code: 0, data: {} }) } })
  const pending = state.load(); state.ctx.dataScope.scope = 'COLLEGE'
  reply.resolve({ code: 0, data: [{ yearCode: 'old-scope' }] }); await pending
  assert.equal(state.rows.length, 0)
})

test('year detail return preserves the year filter within the academic boundary', () => {
  assert.equal(flow.academicReturnPath({ path: '/admin/academic-affairs/terms/years', query: { year: '2099', external: 'discard' } }), '/admin/academic-affairs/terms/years?year=2099')
})

function conflictPage(api = {}) {
  let saved = 0
  const state = page('AaTermDetailView', {
    academicAffairsTermDetailApi: api,
    dirtyGuard: { markSaved() { saved++ } }
  }, { loading: false, detail: { version: 2, termName: '原名称', allowedActions: { editBasic: true } } })
  state.hydrateForm(state.detail)
  state.form.termName = '我的修改'
  state.preview = { canSave: true }; state.previewSignature = state.currentSignature
  return { state, saved: () => saved }
}

test('only explicit version conflicts enable recovery; other409 retains ordinary error behavior', async () => {
  for (const bizCode of ['DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT']) {
    const { state } = conflictPage({ update: async () => ({ code: 409001, bizCode }) })
    await state.save()
    assert.equal(state.versionConflict, bizCode === 'APPROVAL_VERSION_CONFLICT')
    assert.equal(state.form.termName, '我的修改'); assert.equal(state.previewCurrent, false)
  }
})

test('recovery reads latest workspace and three-way merges only locally modified fields without clearing dirty', async () => {
  const latest = { termName: '服务器修改', version: 3, teachingWeeks: 20, allowedActions: { editBasic: true } }
  const { state, saved } = conflictPage({ get: async () => ({ code: 0, data: latest }) })
  state.versionConflict = true
  await state.recoverVersion()
  assert.equal(state.form.termName, '我的修改'); assert.equal(state.form.teachingWeeks, 20)
  assert.equal(state.detail.version, 3); assert.equal(state.previewCurrent, false)
  assert.equal(state.versionConflict, false); assert.equal(saved(), 0)
  assert.equal(state.recoveryComparison.find(row => row.field === 'termName').latest, '服务器修改')
  assert.equal(state.recoveryComparison.find(row => row.field === 'termName').retained, '我的修改')
})

test('failed recovery and duplicate clicks preserve draft, baseline and version', async () => {
  const wait = deferred(); let reads = 0
  const { state } = conflictPage({ get: () => { reads++; return wait.promise } })
  state.versionConflict = true; const baseline = state.baselineSignature
  const pending = state.recoverVersion(); await state.recoverVersion(); assert.equal(reads, 1)
  wait.resolve({ code: 500001, message: '读取失败' }); await pending
  assert.equal(state.detail.version, 2); assert.equal(state.baselineSignature, baseline)
  assert.equal(state.form.termName, '我的修改'); assert.equal(state.versionConflict, true)
  assert.equal(state.recovering, false); assert.equal(state.recoveryError, '读取失败')
})

test('late recovery after context or local signature changes never replaces draft', async () => {
  for (const change of [state => { state.disposed = true }, state => { state.form.termName = '更新的输入' }]) {
    const wait = deferred(); const { state } = conflictPage({ get: () => wait.promise })
    state.versionConflict = true; const pending = state.recoverVersion(); change(state)
    wait.resolve({ code: 0, data: { termName: '迟到', version: 3, allowedActions: { editBasic: true } } }); await pending
    assert.equal(state.detail.version, 2); assert.notEqual(state.form.termName, '迟到')
  }
})

test('recovery refreshes allowed actions and blocks saving when latest workspace becomes readonly', async () => {
  let writes = 0
  const { state } = conflictPage({ get: async () => ({ code: 0, data: { termName: '已归档', version: 3, allowedActions: {} } }), update: async () => { writes++; return { code: 0 } } })
  state.versionConflict = true; await state.recoverVersion()
  assert.equal(state.canEditName, false); assert.equal(state.form.termName, '我的修改')
  await state.save(); assert.equal(writes, 0)
})

test('term api preserves version-conflict business code separately from numeric transport code', async () => {
  const script = readFileSync(new URL('../src/modules/academicAffairs/api/academic-affairs-term-detail.api.js', import.meta.url), 'utf8').replace(/^import .*$/gm, '').replace('export const academicAffairsTermDetailApi', 'globalThis.api')
  const sandbox = { request: async () => { throw { code: 409001, bizCode: 'APPROVAL_VERSION_CONFLICT', message: '冲突', details: { currentVersion: 3 } } } }
  vm.runInNewContext(script, sandbox)
  const result = await sandbox.api.update('3', {})
  assert.equal(result.bizCode, 'APPROVAL_VERSION_CONFLICT'); assert.equal(result.code, 409001)
})

test('pending and superseded previews cannot allow saving or reactivate a recovered draft', async () => {
  const wait = deferred(); let writes = 0
  const { state } = conflictPage({ preview: () => wait.promise, update: async () => { writes++; return { code: 0 } }, get: async () => ({ code: 0, data: { termName: '原名称', version: 3, allowedActions: { editBasic: true } } }) })
  const pending = state.previewChange(); await state.save(); assert.equal(writes, 0)
  state.invalidatePreview(); state.versionConflict = true; await state.recoverVersion()
  wait.resolve({ code: 0, data: { canSave: true } }); await pending
  assert.equal(state.previewCurrent, false)
})

test('latest locked timeline is preserved until explicit adoption and never blocks name recovery forever', async () => {
  const { state } = conflictPage({ get: async () => ({ code: 0, data: { termName: '服务器名称', version: 3, teachingWeeks: 20, allowedActions: { editNameOnly: true } } }) })
  state.form.teachingWeeks = 17; state.versionConflict = true; await state.recoverVersion()
  assert.equal(state.form.teachingWeeks, 17); assert.equal(state.restrictedFieldChanges, true)
  state.adoptLatestRestrictedFields()
  assert.equal(state.form.teachingWeeks, 20); assert.equal(state.form.termName, '我的修改')
  assert.equal(state.restrictedFieldChanges, false); assert.equal(state.previewCurrent, false)
})

test('unresolved conflict and recovery block lifecycle commands even without local changes', () => {
  const { state } = conflictPage()
  state.detail.allowedActions.freeze = true; state.hydrateForm(state.detail)
  for (const flag of ['versionConflict', 'recovering']) {
    state[flag] = true; assert.equal(state.actionAllowed('FREEZE'), false); state[flag] = false
  }
})

function weekPage(api = {}, extras = {}, dirtyGuard = { markSaved() {} }) {
  const detail = { termId: 'draft', status: 'DRAFT', version: 4, teachingWeeks: 20, examWeekStart: 15, allowedActions: { editBasic: true } }
  const state = page('AaTeachingWeekConfigView', { academicAffairsTermDetailApi: api, dirtyGuard,
    academicAffairsApi: { getTermWeeks: async () => ({ code: 0, data: [], message: 'ok' }) } }, {
    termsLoading: false, terms: [detail, { termId: 'other', status: 'DRAFT', teachingWeeks: 10 }], termId: 'draft', detail,
    $route: { query: { termId: 'draft', returnToken: 'saved-page-2' } }, ...extras
  })
  if (state.hydrateForm) state.hydrateForm(detail)
  else {
    state.form = { teachingWeeks: detail.teachingWeeks, examWeekStart: detail.examWeekStart }
    state.baselineForm = { ...state.form }
  }
  state.form.teachingWeeks = 17; state.form.examWeekStart = 16
  state.preview = { termId: 'draft', canSave: true }; state.previewSignature = state.signature
  return state
}

test('teaching week picker remains controlled until successful route change and preserves return token', async () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaTeachingWeekConfigView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  let picker, ignored = false, implicitLabel = false, namedGroup = false
  function visit(node, ignore = false, label = false, group = false) {
    if (node.type === 1) ignore ||= node.props.some(p => p.type === 6 && p.name === 'data-dirty-ignore' && p.value?.content === 'true')
    if (node.type === 1) {
      label ||= node.tag === 'label'
      group ||= node.props.some(p => p.type === 6 && p.name === 'role' && p.value?.content === 'group') && node.props.some(p => p.type === 6 && p.name === 'aria-labelledby')
    }
    if (node.type === 1 && node.tag === 'AppTermEntityPicker') { picker = node; ignored = ignore; implicitLabel = label; namedGroup = group }
    for (const child of node.children || []) visit(child, ignore, label, group)
  }
  visit(descriptor.template.ast)
  assert.ok(picker.props.some(p => p.type === 7 && p.name === 'bind' && p.arg?.content === 'model-value'))
  assert.ok(!picker.props.some(p => p.type === 7 && p.name === 'model'))
  assert.equal(ignored, true)
  assert.equal(implicitLabel, false, 'a picker label must not implicitly activate its clear button')
  assert.equal(namedGroup, true)
  const wait = deferred(); let destination
  const state = weekPage({}, { $router: { replace: to => { destination = to; return wait.promise } } })
  const signature = state.signature
  const pending = state.onTermChange('other')
  assert.equal(state.termId, 'draft'); assert.equal(state.form.teachingWeeks, 17); assert.equal(state.previewCurrent, true)
  assert.equal(destination.query.termId, 'other'); assert.equal(destination.query.returnToken, 'saved-page-2')
  wait.resolve({ type: 4 }); await pending
  assert.equal(state.signature, signature)
  state.loadWorkspace = async () => {}
  state.$route.query.termId = 'other'; state.$options.watch['$route.query.termId'].call(state, 'other')
  assert.equal(state.termId, 'other'); assert.equal(state.form.teachingWeeks, 10); assert.equal(state.previewCurrent, false)
})

test('teaching week dirty guard ignores picker search and retains dirty after cancellation or failed navigation', async () => {
  const previous = { window: globalThis.window, document: globalThis.document, Element: globalThis.Element }
  let before, after, input, unload, accepted = false, confirmations = 0, dispose
  const from = { name: 'aa-term-teaching-weeks', fullPath: '/admin/academic-affairs/terms/teaching-weeks?termId=draft' }
  const to = { ...from, fullPath: '/admin/academic-affairs/terms/teaching-weeks?termId=other' }
  globalThis.Element = class { constructor(ignore = false) { this.ignore = ignore } matches() { return true } closest() { return this.ignore ? {} : null } }
  globalThis.window = { addEventListener(name, fn) { if (name === 'beforeunload') unload = fn }, removeEventListener() {} }
  globalThis.document = { addEventListener(name, fn) { if (name === 'input') input = fn }, removeEventListener() {} }
  try {
    dispose = installDirtyFormGuard({ currentRoute: { value: from }, beforeEach(fn) { before = fn }, beforeResolve(fn) { this.resolveGuard = fn; return () => { if (this.resolveGuard === fn) this.resolveGuard = null } }, afterEach(fn) { after = fn } })
    const guard = window.__SAAS_DIRTY_FORM_GUARD__
    guard.registerConfirmation(() => { confirmations++; return accepted })
    assert.equal(guard.handlesRoute(from), true)
    input({ isTrusted: true, target: new Element(true) }); assert.equal(guard.isDirty(), false)
    assert.equal(await before(to, from), true); assert.equal(confirmations, 0)
    input({ isTrusted: true, target: new Element() }); assert.equal(await before(to, from), false)
    let prevented = false; unload({ preventDefault() { prevented = true } }); assert.equal(prevented, true)
    accepted = true; assert.equal(await before(to, from), true)
    after(to, from, new Error('later guard rejected')); assert.equal(guard.isDirty(), true)
    assert.equal(await before(to, from), true); after(to, from); assert.equal(guard.isDirty(), false)
  } finally {
    dispose?.()
    for (const [key, value] of Object.entries(previous)) { if (value === undefined) delete globalThis[key]; else globalThis[key] = value }
  }
})

test('teaching week numeric version conflict requires explicit latest read; other409 cannot enter recovery', async () => {
  for (const bizCode of ['DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT']) {
    let reads = 0
    const state = weekPage({ update: async () => ({ code: 409001, bizCode, message: '冲突' }), get: async () => { reads++; return { code: 0 } }, preview: async () => ({ code: 0, data: { termId: 'draft', canSave: true } }) })
    await state.submit()
    assert.equal(state.versionConflict, bizCode === 'APPROVAL_VERSION_CONFLICT')
    assert.equal(reads, 0); assert.equal(state.detail.version, 4)
    assert.equal(state.form.teachingWeeks, 17); assert.equal(state.previewCurrent, false)
    if (bizCode === 'APPROVAL_VERSION_CONFLICT') { await state.previewChange(); assert.equal(state.previewCurrent, false) }
  }
})

test('teaching week recovery uses latest workspace and merges both fields against original baseline', async () => {
  let saved = 0
  const state = weekPage({ get: async id => { assert.equal(id, 'draft'); return { code: 0, data: { termId: id, status: 'DRAFT', version: 5, teachingWeeks: 22, examWeekStart: 18, allowedActions: { editBasic: true } } } } }, {}, { markSaved() { saved++ } })
  state.form.examWeekStart = 15; state.versionConflict = true
  await state.recoverVersion()
  assert.equal(state.detail.version, 5); assert.equal(state.form.teachingWeeks, 17); assert.equal(state.form.examWeekStart, 18)
  assert.equal(state.baselineForm.teachingWeeks, 22); assert.equal(state.versionConflict, false); assert.equal(state.previewCurrent, false)
  assert.equal(state.recoveryComparison[0].original, 20); assert.equal(state.recoveryComparison[0].latest, 22); assert.equal(state.recoveryComparison[0].retained, 17)
  assert.equal(saved, 0)
})

test('failed or wrong-object teaching week recovery and duplicate clicks preserve draft and baseline', async () => {
  for (const response of [{ code: 500001, message: '读取失败' }, { code: 0, data: { termId: 'other', version: 5 } }]) {
    const wait = deferred(); let reads = 0
    const state = weekPage({ get: () => { reads++; return wait.promise } })
    state.versionConflict = true; const baseline = JSON.stringify(state.baselineForm)
    const pending = state.recoverVersion(); await state.recoverVersion(); assert.equal(reads, 1); assert.equal(state.editable, false)
    wait.resolve(response); await pending
    assert.equal(state.detail.version, 4); assert.equal(state.form.teachingWeeks, 17); assert.equal(JSON.stringify(state.baselineForm), baseline)
    assert.equal(state.versionConflict, true); assert.equal(state.recovering, false); assert.ok(state.recoveryError)
    assert.notEqual(state.recoveryError, 'ok')
  }
})

test('late teaching week recovery cannot apply after route, scope, input, disposal or workspace generation changes', async () => {
  for (const change of [s => { s.termId = 'other' }, s => { s.ctx.dataScope.scope = 'COLLEGE' }, s => { s.form.teachingWeeks = 19 }, s => { s.disposed = true }, s => { s.workspaceVersion++ }]) {
    const wait = deferred(); const state = weekPage({ get: () => wait.promise }); state.versionConflict = true
    const pending = state.recoverVersion(); change(state)
    wait.resolve({ code: 0, data: { termId: 'draft', status: 'DRAFT', version: 5, teachingWeeks: 22, allowedActions: { editBasic: true } } }); await pending
    assert.equal(state.detail.version, 4); assert.notEqual(state.form.teachingWeeks, 22)
  }
})

test('latest teaching week workspace status and allowed actions independently lock retained input', async () => {
  for (const latest of [{ status: 'PUBLISHED', allowedActions: { editBasic: true } }, { status: 'DRAFT', allowedActions: {} }]) {
    let writes = 0
    const state = weekPage({ get: async () => ({ code: 0, data: { termId: 'draft', version: 5, teachingWeeks: 20, examWeekStart: 15, ...latest } }), update: async () => { writes++; return { code: 0 } } })
    state.versionConflict = true; await state.recoverVersion()
    assert.equal(state.editable, false); assert.equal(state.form.teachingWeeks, 17)
    await state.submit(); assert.equal(writes, 0)
  }
})

test('superseded teaching week preview cannot reactivate after recovery and fresh preview uses latest version', async () => {
  const wait = deferred(); const writes = []
  const state = weekPage({ preview: () => wait.promise, get: async () => ({ code: 0, data: { termId: 'draft', status: 'DRAFT', version: 5, teachingWeeks: 20, examWeekStart: 15, allowedActions: { editBasic: true } } }), update: async (id, body) => { writes.push(body); return { code: 500001 } } })
  const pending = state.previewChange(); await state.submit(); assert.equal(writes.length, 0)
  state.invalidatePreview(); state.versionConflict = true; await state.recoverVersion()
  wait.resolve({ code: 0, data: { termId: 'draft', canSave: true } }); await pending
  assert.equal(state.previewCurrent, false); await state.submit(); assert.equal(writes.length, 0)
  state.preview = { canSave: true }; state.previewSignature = state.signature
  await state.submit(); assert.equal(writes[0].expectedVersion, 5)
})

test('only current successful teaching week save hydrates returned fields and clears dirty', async () => {
  let saved = 0
  const state = weekPage({ update: async () => ({ code: 0, data: { termId: 'draft', version: 5, status: 'DRAFT', teachingWeeks: 17, examWeekStart: 16, allowedActions: { editBasic: true } } }) }, {}, { markSaved() { saved++ } })
  state.refreshTermCatalog = async () => {}
  await state.submit()
  assert.equal(saved, 1); assert.equal(state.detail.version, 5); assert.equal(state.baselineForm.teachingWeeks, 17); assert.equal(state.previewCurrent, false)
  for (const late of [false, true]) {
    const wait = deferred(); const rejected = weekPage({ update: () => wait.promise }, {}, { markSaved() { saved++ } })
    const pending = rejected.submit(); if (late) rejected.workspaceVersion++
    wait.resolve(late ? { code: 0, data: { termId: 'draft', version: 5, teachingWeeks: 8 } } : { code: 500001, message: '保存失败' }); await pending
    assert.equal(rejected.form.teachingWeeks, 17); assert.equal(saved, 1)
  }
})

test('teaching week workspace retry preserves local draft and requires recovery when version advanced', async () => {
  for (const version of [4, 5]) {
    const state = weekPage({ get: async () => ({ code: 0, data: { termId: 'draft', status: 'DRAFT', version, teachingWeeks: 22, examWeekStart: 18, allowedActions: { editBasic: true } } }) })
    state.workspaceLoaded = true
    const baseline = JSON.stringify(state.baselineForm)
    const api = { getTermWeeks: async () => ({ code: 0, data: [] }) }
    const retry = page('AaTeachingWeekConfigView', { academicAffairsTermDetailApi: { get: async () => ({ code: 0, data: { termId: 'draft', status: 'DRAFT', version, teachingWeeks: 22, examWeekStart: 18, allowedActions: { editBasic: true } } }) }, academicAffairsApi: api }, {
      termsLoading: false, terms: state.terms, termId: state.termId, detail: state.detail, form: state.form, baselineForm: state.baselineForm, workspaceLoaded: true
    })
    await retry.loadWorkspace()
    assert.equal(retry.form.teachingWeeks, 17); assert.equal(JSON.stringify(retry.baselineForm), baseline)
    assert.equal(retry.detail.version, 4); assert.equal(retry.versionConflict, version === 5)
  }
})

test('an old teaching week preview does not clear or approve a newer preview request', async () => {
  const old = deferred(), latest = deferred(); let calls = 0
  const state = weekPage({ preview: () => (++calls === 1 ? old.promise : latest.promise) })
  const first = state.previewChange(); state.invalidatePreview()
  const second = state.previewChange()
  old.resolve({ code: 0, data: { termId: 'draft', canSave: true } }); await first
  assert.equal(state.previewing, true); assert.equal(state.previewCurrent, false)
  latest.resolve({ code: 0, data: { termId: 'draft', canSave: true } }); await second
  assert.equal(state.previewing, false); assert.equal(state.previewCurrent, true)
})

test('successful teaching week save refreshes dated calendar weeks without reviving the old draft', async () => {
  let weekReads = 0, workspaceReads = 0
  const original = { termId: 'draft', status: 'DRAFT', version: 4, startDate: '2026-09-01T00:00:00Z', endDate: '2027-01-31T00:00:00Z', teachingWeeks: 20, examWeekStart: 18, allowedActions: { editBasic: true } }
  const latest = { ...original, version: 5, teachingWeeks: 17, examWeekStart: 16 }
  const state = page('AaTeachingWeekConfigView', {
    loadAcademicTermCatalog: async () => [latest],
    academicAffairsTermDetailApi: { update: async () => ({ code: 0, data: latest }), get: async () => { workspaceReads++; return { code: 0, data: latest } } },
    academicAffairsApi: { getCurrentTerm: async () => ({ code: 0, data: null }), getTermWeeks: async () => { weekReads++; return { code: 0, data: [{ weekNo: 17, startDate: '2026-12-21', remark: '最新周次依据' }] } } }
  }, { termsLoading: false, terms: [original], termId: 'draft', detail: original, workspaceLoaded: true, weeks: [{ weekNo: 20, remark: '旧周次依据' }], $route: { query: { termId: 'draft' } } })
  state.hydrateForm(original); state.form.teachingWeeks = 17; state.form.examWeekStart = 16
  state.preview = { canSave: true }; state.previewSignature = state.signature
  await state.submit()
  assert.equal(weekReads, 1); assert.equal(workspaceReads, 1)
  assert.equal(state.weeks[0].weekNo, 17); assert.equal(state.weeks[0].remark, '最新周次依据')
  assert.equal(state.form.teachingWeeks, 17); assert.equal(state.baselineForm.teachingWeeks, 17)
  assert.equal(state.detail.version, 5); assert.equal(state.previewCurrent, false)
})

test('teaching week number stepper marks user changes dirty while hydration and recovery stay clean', async () => {
  let dirty = 0, saved = 0
  const state = weekPage({ get: async () => ({ code: 0, data: { termId: 'draft', status: 'DRAFT', version: 5, teachingWeeks: 22, examWeekStart: 18, allowedActions: { editBasic: true } } }) }, {}, { markDirty() { dirty++ }, markSaved() { saved++ } })
  assert.equal(dirty, 0)
  const source = readFileSync(new URL('../src/components/common/form/AppNumberInput.vue', import.meta.url), 'utf8')
  const sandbox = {}
  vm.runInNewContext(parse(source).descriptor.script.content.replace('export default', 'component ='), sandbox)
  const stepper = { ...sandbox.component.methods, numValue: state.form.teachingWeeks, min: 1, max: 30, step: 1, precision: null,
    $emit(name, value) { if (name === 'update:modelValue') state.updateWeekField('teachingWeeks', value) } }
  stepper.stepBy(1)
  assert.equal(state.form.teachingWeeks, 18); assert.equal(dirty, 1); assert.equal(state.previewCurrent, false)
  state.updateWeekField('teachingWeeks', 18); assert.equal(dirty, 1)
  state.versionConflict = true; await state.recoverVersion()
  assert.equal(state.form.teachingWeeks, 18); assert.equal(dirty, 1); assert.equal(saved, 0)
  state.saving = true; state.updateWeekField('teachingWeeks', 19); assert.equal(state.form.teachingWeeks, 18); assert.equal(dirty, 1)
})

test('teaching week recovery replaces dated calendar term and weeks atomically with latest authority', async () => {
  const latest = { termId: 'draft', version: 5, status: 'DRAFT', startDate: '2026-10-01T00:00:00Z', endDate: '2027-02-28T00:00:00Z', teachingWeeks: 22, examWeekStart: 18, allowedActions: { editBasic: true } }
  for (const failWeeks of [false, true]) {
    const state = page('AaTeachingWeekConfigView', { academicAffairsTermDetailApi: { get: async () => ({ code: 0, data: latest }) },
      academicAffairsApi: { getTermWeeks: async () => failWeeks ? { code: 500001, message: '最新周次读取失败' } : { code: 0, data: [{ weekNo: 22, startDate: '2027-02-22', remark: '最新校历依据' }] } }
    }, { termsLoading: false, termId: 'draft', terms: [{ termId: 'draft', status: 'DRAFT', startDate: '2026-09-01', teachingWeeks: 20 }],
      detail: { termId: 'draft', status: 'DRAFT', version: 4, startDate: '2026-09-01', teachingWeeks: 20, examWeekStart: 15, allowedActions: { editBasic: true } }, weeks: [{ weekNo: 20, remark: '旧校历依据' }], versionConflict: true })
    state.hydrateForm(state.detail); state.form.teachingWeeks = 17
    await state.recoverVersion()
    assert.equal(state.form.teachingWeeks, 17)
    if (failWeeks) {
      assert.equal(state.detail.version, 4); assert.equal(state.baselineForm.teachingWeeks, 20)
      assert.equal(state.weeks[0].weekNo, 20); assert.equal(state.versionConflict, true); assert.equal(state.recoveryError, '最新周次读取失败')
    } else {
      assert.equal(state.calendarTerm.startDate, '2026-10-01T00:00:00Z'); assert.equal(state.calendarTerm.teachingWeeks, 22)
      assert.equal(state.weeks[0].weekNo, 22); assert.equal(state.weeks[0].remark, '最新校历依据')
      assert.equal(state.detail.version, 5); assert.equal(state.previewCurrent, false)
    }
  }
})

// A6: compiled public state regression. Declared transport responses pass through
// the actual API callList/catch/toErr; no HTTP, permission change or consumer rejection.
import { createRequire as termErrorCreateRequire } from 'node:module'
import { setImmediate as termErrorSetImmediate } from 'node:timers'
import { normalizeUiError as termErrorNormalize } from '../src/utils/presentationSafety.js'

const termErrorRequire = termErrorCreateRequire(import.meta.url)
const termErrorVue = termErrorRequire('vue')
const { compileTemplate: termErrorCompileTemplate } = termErrorRequire('@vue/compiler-sfc')
const termErrorRead = relative => readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')
function termErrorCompileActual(relative, scope = {}) {
  const { descriptor, errors } = parse(termErrorRead(relative), { filename: relative })
  assert.deepEqual(errors, [])
  const body = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const component = new Function(...Object.keys(scope), `${body}\nreturn component`)(...Object.values(scope))
  const template = termErrorCompileTemplate({ source: descriptor.template.content, filename: relative, id: relative, compilerOptions: { mode: 'function' } })
  assert.deepEqual(template.errors, [])
  component.render = new Function('Vue', template.code)(termErrorVue)
  return component
}
const TermErrorActualGlobal = termErrorCompileActual('components/common/AppGlobalState.vue', { normalizeUiError: termErrorNormalize })
const TermErrorActualError = termErrorCompileActual('components/business/ErrorState.vue', { AppGlobalState: TermErrorActualGlobal, normalizeUiError: termErrorNormalize })
const TermErrorActualLoading = termErrorCompileActual('components/business/LoadingState.vue', { AppGlobalState: TermErrorActualGlobal })
const TermErrorActualEmpty = termErrorCompileActual('components/business/EmptyState.vue', { AppGlobalState: TermErrorActualGlobal })
const TermErrorActualButton = termErrorCompileActual('components/ui/AppButton.vue')
const termErrorNode = (type, value = '') => ({ type, tagName: type.toUpperCase(), value, props: {}, children: [], parent: null, listeners: {}, addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) } })
const termErrorRenderer = termErrorVue.createRenderer({
  createElement: type => termErrorNode(type), createText: value => termErrorNode('#text', value), createComment: value => termErrorNode('#comment', value),
  setText(n, value) { n.value = value }, setElementText(n, value) { n.value = value; n.children = [] },
  parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
  patchProp(n, key, _old, value) { n.props[key] = value },
  insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(n); else parent.children.splice(i, 0, n) },
  remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } }
})
const termErrorWalk = n => [n, ...n.children.flatMap(termErrorWalk)]
const termErrorText = n => n.type === '#comment' ? '' : n.value + n.children.map(termErrorText).join('')
const termErrorPanels = (root, value) => termErrorWalk(root).filter(n => String(n.props.class || '').split(/\s+/).includes(`ags-${value}`))
const termErrorButtons = (root, label) => termErrorWalk(root).filter(n => n.type === 'button' && termErrorText(n).trim() === label)
const termErrorTerminal = async () => { await new Promise(resolve => termErrorSetImmediate(resolve)); await termErrorVue.nextTick() }
function termErrorClick(root, label) {
  const buttons = termErrorButtons(root, label); assert.equal(buttons.length, 1, `One public ${label} button`)
  const button = buttons[0]; assert.equal(!!button.props.disabled, false, 'Never dispatch a disabled public control')
  for (const fn of Array.isArray(button.props.onClick) ? button.props.onClick : [button.props.onClick]) fn?.({ target: button, currentTarget: button, type: 'click' })
}
function termErrorDeclaredTransport({ httpStatus, code = 1, bizCode = '', message = '读取失败', traceId = '', details = null }) {
  // Shape follows the real client: normalize payload first, then attach HTTP metadata.
  // This declaration is not an observed backend/HTTP failure or an auth operation.
  const normalized = termErrorNormalize({ code, bizCode, message, traceId })
  return Object.assign(new Error(normalized.userMessage), { biz: true, httpStatus, code, bizCode, details, traceId, rawDeveloperDetail: normalized.rawDeveloperDetail })
}
const termErrorHealthyPage = termName => ({ items: [{ termId: 'DECLARED_TERM', yearCode: '2030-2031', termNo: 1, termName, status: 'DRAFT', isCurrent: false }], total: 1, page: 1, pageSize: 20 })
async function termErrorCompiledFixture(t, options = {}) {
  const requests = [], responses = [], warnings = [], errors = []
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const state = termErrorVue.reactive({ ctx: { ctxKey: 'DECLARED_TERM_SCOPE', permissionPatterns: ['academicAffairs.term.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 } })
  let termsCalls = 0, currentCalls = 0
  const prohibited = () => { throw new Error('该读取状态夹具禁止写入、下载、授权和导航') }
  const request = async (path, requestOptions = {}) => {
    requests.push({ path, params: requestOptions.params || {} })
    if (path === '/academic-affairs/terms/current') { currentCalls++; return { termId: 'DECLARED_TERM', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true } }
    assert.equal(path, '/academic-affairs/terms')
    termsCalls++
    return options.terms ? options.terms(termsCalls, requestOptions.params || {}) : termErrorHealthyPage('声明正常学期')
  }
  // Entire original adapter, with import/export wiring only. The catch and toErr are actual producers.
  const apiSource = termErrorRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const productionApi = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const api = { ...productionApi, getTerms(params) { return productionApi.getTerms(params).then(result => { responses.push(result); return result }) } }
  const visual = name => ({ name, inheritAttrs: false, setup(_props, { slots }) { return () => termErrorVue.h('section', {}, [slots.actions?.(), slots.default?.()]) } })
  const Table = { name: 'DeclaredUnrelatedTermTable', props: ['rows'], render() { return termErrorVue.h('table', {}, (this.rows || []).map(row => termErrorVue.h('tr', {}, row.termName))) } }
  const Component = termErrorCompileActual('modules/academicAffairs/views/AaTermListView.vue', {
    ModulePageShell: visual('DeclaredPageShell'), DataTable: Table, LoadingState: TermErrorActualLoading, ErrorState: TermErrorActualError, EmptyState: TermErrorActualEmpty,
    AdvancedFilter: visual('DeclaredUnrelatedStaticFilter'), AppButton: TermErrorActualButton, AppStatusTag: visual('DeclaredUnrelatedStatusTag'), AppConfirmDialog: visual('DeclaredUnopenedPublishDialog'),
    academicAffairsApi: api, toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission,
    academicIdentity: flow.academicIdentity, academicRouteState: flow.academicRouteState, createAcademicRequestGate: flow.createAcademicRequestGate, routeScalar: flow.routeScalar, currentUserFromToken: () => claims
  })
  const root = termErrorNode('root')
  const app = termErrorRenderer.createApp({ render: () => termErrorVue.h(Component, { ctx: state.ctx }) })
  app.config.globalProperties.$route = termErrorVue.reactive({ path: '/admin/academic-affairs/terms', fullPath: '/admin/academic-affairs/terms', query: {} })
  app.config.globalProperties.$router = { options: { history: { state: {} } }, push: prohibited, back: prohibited }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  let stopped = false
  t.after(async () => { if (!stopped) { app.unmount(); stopped = true }; await termErrorTerminal(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []) })
  app.mount(root); await termErrorTerminal()
  return { root, state, requests, responses, warnings, errors, termsCalls: () => termsCalls, currentCalls: () => currentCalls }
}

test('A6 real adapter HTTP500 overrides stale permission code in the actual public term-list error state', async t => {
  const transportError = termErrorDeclaredTransport({ httpStatus: 500, code: 403003, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_TERM_FAILURE_500' })
  const f = await termErrorCompiledFixture(t, { terms() { throw transportError } })
  assert.equal(f.termsCalls(), 1); assert.equal(f.currentCalls(), 1)
  assert.equal(f.responses[0].httpStatus, 500); assert.equal(f.responses[0].bizCode, 'NO_PERMISSION'); assert.equal(f.responses[0].traceId, 'DECLARED_TERM_FAILURE_500')
  assert.equal(termErrorPanels(f.root, 'error').length, 1, 'HTTP500 must remain an actual shared retryable error panel, not stale permission denial')
  assert.equal(termErrorPanels(f.root, 'forbidden').length, 0); assert.equal(termErrorButtons(f.root, '重试').length, 1)
  assert.match(termErrorText(f.root), /操作未完成，请稍后重试/)
})

test('A6 typed403 renders the real term-list forbidden state without ordinary retry', async t => {
  const f = await termErrorCompiledFixture(t, { terms() { throw termErrorDeclaredTransport({ httpStatus: 403, bizCode: 'NO_PERMISSION' }) } })
  assert.equal(f.responses[0].httpStatus, 403)
  assert.equal(termErrorPanels(f.root, 'forbidden').length, 1); assert.equal(termErrorPanels(f.root, 'error').length, 0)
  assert.equal(termErrorButtons(f.root, '重试').length, 0); assert.equal(termErrorButtons(f.root, '返回').length, 1)
  assert.doesNotMatch(termErrorText(f.root), /NO_PERMISSION|permissionPatterns|DECLARED_STAFF/)
})

test('A6 typed401 renders the real term-list login-expired state instead of retry', async t => {
  const f = await termErrorCompiledFixture(t, { terms() { throw termErrorDeclaredTransport({ httpStatus: 401, bizCode: 'UNAUTHORIZED' }) } })
  assert.equal(f.responses[0].httpStatus, 401)
  assert.equal(termErrorPanels(f.root, 'unauthorized').length, 1); assert.equal(termErrorPanels(f.root, 'error').length, 0)
  assert.equal(termErrorButtons(f.root, '重新登录').length, 1); assert.equal(termErrorButtons(f.root, '重试').length, 0)
  assert.match(termErrorText(f.root), /登录已失效/); assert.doesNotMatch(termErrorText(f.root), /UNAUTHORIZED|DECLARED_STAFF/)
})

test('A6 a safe technical500 error retries through the public button and recovers the current term list', async t => {
  const f = await termErrorCompiledFixture(t, { terms(index) {
    if (index === 1) throw termErrorDeclaredTransport({ httpStatus: 500, code: 500001, bizCode: 'SERVER_ERROR', message: 'SQLSTATE HY000 SELECT secret FROM hidden_table', traceId: 'DECLARED_TECHNICAL_FAILURE', details: { privateField: 'PRIVATE_DETAIL_MUST_NOT_RENDER' } })
    return termErrorHealthyPage('声明重试恢复学期')
  } })
  assert.equal(termErrorPanels(f.root, 'error').length, 1); assert.match(termErrorText(f.root), /DECLARED_TECHNICAL_FAILURE/)
  assert.doesNotMatch(termErrorText(f.root), /SQLSTATE|SELECT secret|hidden_table|PRIVATE_DETAIL_MUST_NOT_RENDER|SERVER_ERROR/)
  termErrorClick(f.root, '重试'); await termErrorTerminal()
  assert.equal(f.termsCalls(), 2); assert.equal(f.currentCalls(), 1)
  assert.equal(termErrorPanels(f.root, 'error').length, 0); assert.equal(termErrorPanels(f.root, 'loading').length, 0)
  assert.equal(termErrorPanels(f.root, 'empty').length, 0); assert.match(termErrorText(f.root), /声明重试恢复学期/)
  assert.equal(f.responses[1].code, 0); assert.equal(f.responses[1].data.total, 1)
})

test('A6 an older typed term-list failure cannot replace a newer context list result', async t => {
  let rejectOld
  const oldRequest = new Promise((_resolve, reject) => { rejectOld = reject })
  const f = await termErrorCompiledFixture(t, { terms(index) { return index === 1 ? oldRequest : termErrorHealthyPage('声明新范围学期') } })
  assert.equal(termErrorPanels(f.root, 'loading').length, 1); assert.equal(f.termsCalls(), 1)
  f.state.ctx = { ...f.state.ctx, ctxKey: 'DECLARED_NEW_SCOPE', dataScopeVersion: 2 }
  await termErrorTerminal(); assert.equal(f.termsCalls(), 2); assert.equal(f.currentCalls(), 2)
  assert.match(termErrorText(f.root), /声明新范围学期/)
  rejectOld(termErrorDeclaredTransport({ httpStatus: 500, code: 403003, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_OLD_FAILURE' }))
  await termErrorTerminal()
  assert.equal(f.responses.length, 2); assert.equal(f.responses.find(response => response.code !== 0).httpStatus, 500)
  assert.equal(termErrorPanels(f.root, 'error').length, 0); assert.equal(termErrorPanels(f.root, 'forbidden').length, 0); assert.equal(termErrorPanels(f.root, 'loading').length, 0)
  assert.match(termErrorText(f.root), /声明新范围学期/); assert.doesNotMatch(termErrorText(f.root), /DECLARED_OLD_FAILURE|暂无访问权限/)
  assert.equal(f.termsCalls(), 2)
})

// Status uses the same actual compiler/shared states as the retained TermList
// cases above, with its own natural three-read contract and no business action.
import { safeEnumLabel as statusErrorSafeEnumLabel } from '../src/utils/presentationSafety.js'
import * as statusErrorDialog from '../src/services/systemDialog.js'
async function statusErrorCompiledFixture(t, options) {
  const previous = Object.fromEntries(['window', 'document'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const body = termErrorNode('body'), requests = [], responses = [], archives = [], currents = [], errors = [], warnings = []
  const prohibited = () => { throw new Error('该学期状态只读夹具禁止冻结、解冻、保存、授权、业务写入或导航') }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body } })
  let app, stopped = false
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } await termErrorTerminal(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(statusErrorDialog.systemDialogState.visible, false) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
  })
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const ctx = termErrorVue.reactive({ ctxKey: 'DECLARED_TERM_STATUS_READ_SCOPE', permissionPatterns: ['academicAffairs.term.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 })
  assert.equal(matchPermission(ctx.permissionPatterns, 'academicAffairs.term.manage'), false)
  const currentDTO = { termId: '1', yearCode: '2025-2026', termNo: 2, termName: '声明当前学期1', startDate: '2026-02-01T00:00:00', endDate: '2026-06-30T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: true, status: 'PUBLISHED', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
  const transportError = termErrorDeclaredTransport(options)
  const counts = { terms: 0, archive: 0, current: 0 }
  const request = async (path, requestOptions = {}) => {
    assert.ok(!requestOptions.method || requestOptions.method === 'GET'); assert.equal(requestOptions.body, undefined)
    requests.push({ path, method: requestOptions.method || 'GET', params: requestOptions.params ?? null }); assert.ok(requests.length <= 6)
    if (path === '/academic-affairs/terms') {
      assert.deepEqual(requestOptions.params, { page: 1, pageSize: 100 }); assert.ok(++counts.terms <= 2)
      if (counts.terms === 1) throw transportError
      return { items: [], total: 0, page: 1, pageSize: 100 }
    }
    if (path === '/academic-affairs/terms/archive-overview') { assert.equal(requestOptions.params, undefined); assert.ok(++counts.archive <= 2); return { items: [] } }
    assert.equal(path, '/academic-affairs/terms/current'); assert.equal(requestOptions.params, undefined); assert.ok(++counts.current <= 2); return structuredClone(currentDTO)
  }
  const apiSource = termErrorRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const productionApi = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const api = { ...productionApi,
    getTerms(params) { assert.deepEqual(params, { page: 1, pageSize: 100 }); return productionApi.getTerms(params).then(result => { responses.push(structuredClone(result)); return result }) },
    getTermArchiveOverview() { return productionApi.getTermArchiveOverview().then(result => { archives.push(structuredClone(result)); return result }) },
    getCurrentTerm() { return productionApi.getCurrentTerm().then(result => { currents.push(structuredClone(result)); return result }) }
  }
  const visual = name => ({ name, inheritAttrs: false, setup(_props, { slots }) { return () => termErrorVue.h('section', {}, [slots.actions?.(), slots.default?.()]) } })
  const Drawer = termErrorCompileActual('components/ui/AppDrawer.vue')
  const Status = termErrorCompileActual('modules/academicAffairs/views/AaTermStatusView.vue', {
    ModulePageShell: visual('DeclaredStatusShell'), DataTable: visual('DeclaredUnrelatedEmptyStatusRows'), LoadingState: TermErrorActualLoading, ErrorState: TermErrorActualError, EmptyState: TermErrorActualEmpty,
    AppButton: TermErrorActualButton, AppDrawer: Drawer, AppSectionCard: visual('DeclaredStatusFactsAndListCards'), AppStatusTag: visual('DeclaredUnusedRowStatus'), AppConfirmDialog: visual('DeclaredUnopenedFreezeDialog'), AppFormItem: visual('DeclaredUnopenedUnfreezeForm'), AppTextarea: visual('DeclaredUnopenedReason'), AppInlineAlert: visual('DeclaredUnrelatedCurrentWarning'),
    academicAffairsApi: api, toast: { success: prohibited, error: prohibited, warning: prohibited }, safeEnumLabel: statusErrorSafeEnumLabel, matchPermission
  })
  const renderer = termErrorVue.createRenderer({ querySelector(selector) { assert.equal(selector, 'body'); return document.body }, createElement: type => termErrorNode(type), createText: value => termErrorNode('#text', value), createComment: value => termErrorNode('#comment', value), setText(n, value) { n.value = value }, setElementText(n, value) { n.value = value; n.children = [] }, parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null, patchProp(n, key, _old, value) { n.props[key] = value }, insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(n); else parent.children.splice(i, 0, n) }, remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } } })
  const root = termErrorNode('root'); app = renderer.createApp({ render: () => termErrorVue.h(Status, { ctx }) })
  let restored = 0
  app.provide('academicFlow', { identity: () => flow.academicIdentity(claims, ctx), restorePosition() { restored++ }, captureReturn: prohibited })
  app.config.globalProperties.$route = termErrorVue.reactive({ name: 'aa-term-status', path: '/admin/academic-affairs/terms/status', fullPath: '/admin/academic-affairs/terms/status', query: {} })
  app.config.globalProperties.$router = { push: prohibited, replace: prohibited, back: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  app.mount(root)
  for (let i = 0; i < 8; i++) { await termErrorTerminal(); if (requests.length === 3 && responses.length === 1 && archives.length === 1 && currents.length === 1 && !termErrorPanels(root, 'loading').length) break }
  assert.deepEqual(counts, { terms: 1, archive: 1, current: 1 }); assert.equal(requests.length, 3)
  assert.deepEqual(responses, [{ code: transportError.code, data: null, message: transportError.message, bizCode: transportError.bizCode, details: transportError.details, httpStatus: transportError.httpStatus, traceId: transportError.traceId }])
  assert.deepEqual(archives, [{ code: 0, data: [], message: 'ok' }]); assert.deepEqual(currents, [{ code: 0, data: currentDTO, message: 'ok' }]); assert.equal(restored, 1)
  assert.ok(termErrorText(root).includes('2025-2026 第 2 学期')); assert.ok(termErrorText(root).includes('教务学期管理'))
  for (const label of ['冻结', '解冻', '确认冻结', '确认解冻']) assert.equal(termErrorButtons(root, label).length, 0)
  assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(statusErrorDialog.systemDialogState.visible, false)
  const support = () => {
    const codes = termErrorPanels(root, 'code'); assert.equal(codes.length, 1); assert.equal(termErrorText(codes[0]), `实施人员使用错误码：${transportError.traceId}`)
    const descriptions = termErrorPanels(root, 'desc'); assert.equal(descriptions.length, 1)
    if (transportError.httpStatus === 404 && transportError.bizCode === 'RECORD_NOT_FOUND') assert.equal(termErrorText(descriptions[0]), '记录不存在或已被删除')
    else assert.ok(!termErrorText(descriptions[0]).includes(transportError.traceId), '技术编号应留在折叠的实施人员信息中')
  }
  const assertState = state => {
    assert.equal(termErrorPanels(root, state).length, 1)
    for (const other of ['error', 'forbidden', 'empty', 'loading'].filter(name => name !== state)) assert.equal(termErrorPanels(root, other).length, 0)
  }
  const retry = async () => {
    termErrorClick(root, '重试'); await termErrorTerminal()
    assert.deepEqual(counts, { terms: 2, archive: 2, current: 2 }); assert.equal(requests.length, 6)
    assert.deepEqual(responses[1], { code: 0, data: { list: [], total: 0, page: 1, pageSize: 100 }, message: 'ok' })
    assert.deepEqual(archives, [{ code: 0, data: [], message: 'ok' }, { code: 0, data: [], message: 'ok' }]); assert.deepEqual(currents, [{ code: 0, data: currentDTO, message: 'ok' }, { code: 0, data: currentDTO, message: 'ok' }])
    assertState('empty'); assert.equal(restored, 2); assert.ok(termErrorText(root).includes('2025-2026 第 2 学期')); assert.ok(termErrorText(root).includes('教务学期管理')); assert.deepEqual(errors, []); assert.deepEqual(warnings, [])
  }
  return { root, requests, responses, assertState, support, retry }
}

test('term status actual typed HTTP500 overrides stale denial and public retry restores its three-read empty ledger', async t => {
  const f = await statusErrorCompiledFixture(t, { httpStatus: 500, code: 403003, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_STATUS_FAILURE_500' })
  f.assertState('error'); f.support(); assert.equal(termErrorButtons(f.root, '重试').length, 1); assert.ok(termErrorText(f.root).includes('操作未完成，请稍后重试'))
  await f.retry()
})

test('term status actual typed HTTP403 renders forbidden without ordinary retry or a permission change', async t => {
  const f = await statusErrorCompiledFixture(t, { httpStatus: 403, code: 403003, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_STATUS_FORBIDDEN' })
  f.assertState('forbidden'); assert.equal(termErrorButtons(f.root, '重试').length, 0); assert.equal(termErrorButtons(f.root, '返回').length, 1)
  assert.ok(termErrorText(f.root).includes('原因：不在授权范围内。建议：切换身份或联系管理员开通权限')); assert.equal(f.requests.length, 3)
})

test('term status actual typed HTTP404 stays a safe failed read instead of a healthy empty ledger', async t => {
  const f = await statusErrorCompiledFixture(t, { httpStatus: 404, code: 404001, bizCode: 'RECORD_NOT_FOUND', traceId: 'DECLARED_STATUS_NOT_FOUND' })
  f.assertState('error'); f.support(); assert.equal(termErrorButtons(f.root, '重试').length, 1); assert.equal(f.requests.length, 3)
})

test('term status actual technical HTTP500 keeps full adapter details private and public retry preserves current facts', async t => {
  const details = { sql: 'SELECT value FROM t_declared_private', stack: 'Traceback /srv/declared.py' }
  const f = await statusErrorCompiledFixture(t, { httpStatus: 500, code: 500001, bizCode: 'INTERNAL_ERROR', message: 'SQLSTATE 42S02 SELECT value FROM t_declared_private /srv/declared.py', traceId: 'DECLARED_STATUS_TECH_500', details })
  f.assertState('error'); f.support(); assert.deepEqual(f.responses[0].details, details); assert.equal(termErrorButtons(f.root, '重试').length, 1)
  for (const raw of ['SQLSTATE', 'SELECT value', 't_declared_private', 'Traceback', '/srv/declared.py']) assert.equal(termErrorText(f.root).includes(raw), false)
  await f.retry()
})


// Archive's own canonical one-read adapter contract. Transport is declared;
// full page/ErrorState/AppGlobalState/AppButton/closed Drawer are actual SFCs.
async function archiveErrorFixture(t, options) {
  const previous = Object.fromEntries(['window', 'document'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const requests = [], responses = [], warnings = [], errors = []
  const prohibited = () => { throw new Error('该归档读取夹具禁止生成、预检、封存、发布、保存、下载、其他API或导航') }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body: termErrorNode('body') } })
  let app, reads = 0, restored = 0
  t.after(async () => {
    try { app?.unmount(); await termErrorTerminal(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(statusErrorDialog.systemDialogState.visible, false) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
  })
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const ctx = termErrorVue.reactive({ ctxKey: 'DECLARED_ARCHIVE_READ_SCOPE', permissionPatterns: ['academicAffairs.term.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 })
  assert.equal(matchPermission(ctx.permissionPatterns, 'academicAffairs.archive.manage'), false)
  const transportError = termErrorDeclaredTransport(options)
  const request = async (path, requestOptions = {}) => {
    assert.ok(!requestOptions.method || requestOptions.method === 'GET'); assert.equal(requestOptions.body, undefined)
    assert.equal(path, '/academic-affairs/terms/archive-overview'); assert.equal(requestOptions.params, undefined)
    requests.push({ path, method: requestOptions.method || 'GET', params: null }); assert.ok(++reads <= 2)
    if (reads === 1) throw transportError
    return { items: [] }
  }
  const apiSource = termErrorRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const productionApi = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn academicAffairsApi`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const api = { ...productionApi, getTermArchiveOverview() { return productionApi.getTermArchiveOverview().then(result => { responses.push(structuredClone(result)); return result }) } }
  const visual = name => ({ name, inheritAttrs: false, setup(_props, { slots }) { return () => termErrorVue.h('section', {}, [slots.actions?.(), slots.default?.()]) } })
  const Drawer = termErrorCompileActual('components/ui/AppDrawer.vue')
  const Archive = termErrorCompileActual('modules/academicAffairs/views/AaTermArchiveView.vue', {
    ModulePageShell: visual('DeclaredArchiveShell'), DataTable: visual('DeclaredUnrelatedEmptyArchiveRows'), LoadingState: TermErrorActualLoading, ErrorState: TermErrorActualError, EmptyState: TermErrorActualEmpty,
    AppButton: TermErrorActualButton, AppDrawer: Drawer, AppStatusTag: visual('DeclaredUnusedArchiveStatus'), AaCalendarArchivePanel: visual('DeclaredUnopenedArchiveEvidence'), academicAffairsApi: api, matchPermission
  })
  const renderer = termErrorVue.createRenderer({ querySelector(selector) { assert.equal(selector, 'body'); return document.body }, createElement: type => termErrorNode(type), createText: value => termErrorNode('#text', value), createComment: value => termErrorNode('#comment', value), setText(n, value) { n.value = value }, setElementText(n, value) { n.value = value; n.children = [] }, parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null, patchProp(n, key, _old, value) { n.props[key] = value }, insert(n, parent, anchor = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(n); else parent.children.splice(i, 0, n) }, remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } } })
  const root = termErrorNode('root'); app = renderer.createApp({ render: () => termErrorVue.h(Archive, { ctx }) })
  app.provide('academicFlow', { identity: () => flow.academicIdentity(claims, ctx), restorePosition() { restored++ }, back: prohibited })
  app.config.globalProperties.$route = termErrorVue.reactive({ path: '/admin/academic-affairs/terms/archive-status', fullPath: '/admin/academic-affairs/terms/archive-status', query: {} })
  app.config.globalProperties.$router = { push: prohibited, replace: prohibited, back: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  app.mount(root); await termErrorTerminal()
  assert.equal(reads, 1); assert.equal(requests.length, 1); assert.equal(restored, 1)
  assert.deepEqual(responses, [{ code: transportError.code, data: null, message: transportError.message, bizCode: transportError.bizCode, details: transportError.details, httpStatus: transportError.httpStatus, traceId: transportError.traceId }])
  assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(statusErrorDialog.systemDialogState.visible, false)
  const assertState = state => {
    assert.equal(termErrorPanels(root, state).length, 1)
    for (const other of ['error', 'forbidden', 'empty', 'loading'].filter(name => name !== state)) assert.equal(termErrorPanels(root, other).length, 0)
  }
  const support = () => {
    const codes = termErrorPanels(root, 'code'); assert.equal(codes.length, 1); assert.equal(termErrorText(codes[0]), `实施人员使用错误码：${transportError.traceId}`)
    const descriptions = termErrorPanels(root, 'desc'); assert.equal(descriptions.length, 1)
    if (transportError.httpStatus === 404 && transportError.bizCode === 'RECORD_NOT_FOUND') assert.equal(termErrorText(descriptions[0]), '记录不存在或已被删除')
    else assert.ok(!termErrorText(descriptions[0]).includes(transportError.traceId), '技术编号应留在折叠的实施人员信息中')
  }
  const retry = async () => {
    termErrorClick(root, '重试'); await termErrorTerminal()
    assert.equal(reads, 2); assert.equal(requests.length, 2); assert.equal(restored, 2)
    assert.deepEqual(responses[1], { code: 0, data: [], message: 'ok' }); assertState('empty')
    assert.deepEqual(errors, []); assert.deepEqual(warnings, [])
  }
  return { root, requests, responses, assertState, support, retry }
}
test('term archive actual typed HTTP500 overrides stale denial and public retry restores its one-read empty overview', async t => {
  const f = await archiveErrorFixture(t, { httpStatus: 500, code: 403003, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_ARCHIVE_FAILURE_500' })
  f.assertState('error'); f.support(); assert.equal(termErrorButtons(f.root, '重试').length, 1); assert.ok(termErrorText(f.root).includes('操作未完成，请稍后重试'))
  await f.retry()
})

test('term archive actual typed HTTP403 renders forbidden without ordinary retry or a permission change', async t => {
  const f = await archiveErrorFixture(t, { httpStatus: 403, code: 403003, bizCode: 'NO_PERMISSION', traceId: 'DECLARED_ARCHIVE_FORBIDDEN' })
  f.assertState('forbidden'); assert.equal(termErrorButtons(f.root, '重试').length, 0); assert.equal(termErrorButtons(f.root, '返回').length, 1)
  assert.ok(termErrorText(f.root).includes('原因：不在授权范围内。建议：切换身份或联系管理员开通权限')); assert.equal(f.requests.length, 1)
})

test('term archive actual typed HTTP404 stays a safe failed read instead of a healthy empty overview', async t => {
  const f = await archiveErrorFixture(t, { httpStatus: 404, code: 404001, bizCode: 'RECORD_NOT_FOUND', traceId: 'DECLARED_ARCHIVE_NOT_FOUND' })
  f.assertState('error'); f.support(); assert.equal(termErrorButtons(f.root, '重试').length, 1); assert.equal(f.requests.length, 1)
})

test('term archive actual technical HTTP500 keeps full adapter details private and public retry recovers the empty overview', async t => {
  const details = { sql: 'SELECT value FROM t_declared_private', stack: 'Traceback /srv/declared.py' }
  const f = await archiveErrorFixture(t, { httpStatus: 500, code: 500001, bizCode: 'INTERNAL_ERROR', message: 'SQLSTATE 42S02 SELECT value FROM t_declared_private /srv/declared.py', traceId: 'DECLARED_ARCHIVE_TECH_500', details })
  f.assertState('error'); f.support(); assert.deepEqual(f.responses[0].details, details); assert.equal(termErrorButtons(f.root, '重试').length, 1)
  for (const raw of ['SQLSTATE', 'SELECT value', 't_declared_private', 'Traceback', '/srv/declared.py']) assert.equal(termErrorText(f.root).includes(raw), false)
  await f.retry()
})
