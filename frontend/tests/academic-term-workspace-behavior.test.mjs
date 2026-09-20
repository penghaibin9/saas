import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission, findActiveInPlan } from '../src/config/navPlan.js'
import { createMemoryHistory, createRouter } from 'vue-router'
import { academicAffairsRoutes } from '../src/modules/academicAffairs/academic-affairs.routes.js'
import * as flow from '../src/modules/academicAffairs/academicFlowContext.js'

function page(name, dependencies = {}, extra = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { ...flow, currentUserFromToken: () => ({ tenantId: 'school', userId: 'staff', currentRoleCode: 'SCHOOL_ADMIN' }), matchPermission, toast: { success() {}, error() {}, warning() {} }, ...dependencies } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = Object.assign(component.data(), component.methods, {
    ctx: { permissionPatterns: ['academicAffairs.term.*'], dataScope: { scope: 'SCHOOL' } },
    $route: { params: { termId: 'term-a' }, query: {} }, $router: { push() {} }
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
  let target
  const state = page('AaTermFormView', { academicAffairsApi: { createTerm: async () => ({ code: 0, data: { termId: 'new-term' } }) } }, { $router: { push: route => { target = route } } })
  Object.assign(state.form, { yearCode: '2026-2027', teachingWeeks: 17.5 })
  assert.equal(state.validate(), false)
  Object.assign(state.form, { teachingWeeks: 17, examWeekStart: 18 })
  assert.equal(state.validate(), false)
  state.form.examWeekStart = 17
  await state.submit()
  assert.equal(target.name, 'aa-term-detail')
  assert.equal(target.params.termId, 'new-term')
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
      get: async id => ({ code: 0, data: { termId: id, version: 3 } }),
      update: async (id, payload) => { assert.equal(id, 'draft'); body = payload; return { code: 0 } }
    }, academicAffairsApi: {
    getTermWeeks: async () => ({ code: 0, data: [] }),
    getCurrentTerm: async () => ({ code: 0, data: { termId: 'current' } })
  } }, { termsLoading: false, terms: rows, termId: 'draft', detail: { version: 3 }, form: { teachingWeeks: 20, examWeekStart: null } })
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
    { termsLoading: false, terms: [{ termId: 'draft', status: 'DRAFT' }], termId: 'draft', detail: { version: 2 }, form: { teachingWeeks: 20 } })
  state.preview = { canSave: true }; state.previewSignature = state.signature
  state.form.teachingWeeks = 10
  await state.submit(); assert.equal(writes, 0)
})

test('teaching week impact from an old object cannot approve the new object', async () => {
  const reply = deferred()
  const state = page('AaTeachingWeekConfigView', { academicAffairsTermDetailApi: { preview: () => reply.promise } },
    { termsLoading: false, terms: [{ termId: 'draft', status: 'DRAFT' }], termId: 'draft', detail: { version: 2 }, form: { teachingWeeks: 20 } })
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
