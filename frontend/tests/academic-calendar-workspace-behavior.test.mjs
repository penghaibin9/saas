import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'

function component(path, dependencies = {}, extra = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/${path}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { matchPermission, toast: { success() {}, error() {}, warning() {} }, ...dependencies } }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  const state = Object.assign(definition.data(), definition.methods, {
    ctx: { permissionPatterns: ['academicAffairs.*'], dataScope: { scope: 'SCHOOL' }, currentRole: { roleCode: 'SCHOOL_ADMIN' } },
    $route: { query: {} }, $router: { replace() {} }, $emit() {},
  }, extra)
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state), configurable: true })
  return { state, definition }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const page = (dependencies = {}, extra = {}) => component('views/AaCalendarView', dependencies, {
  terms: [{ termId: 'a', status: 'DRAFT' }, { termId: 'b', status: 'DRAFT' }], termId: 'a', termsLoading: false, ...extra,
})

test('calendar publish waits for authoritative context and requires permission, school scope and compatible current term', async () => {
  let calls = 0
  const { state } = page({ academicAffairsApi: { publishCalendar: async () => { calls++; return { code: 0 } } } })
  assert.equal(state.canPublish, false)
  await state.doPublish()
  assert.equal(calls, 0)
  state.currentLoading = false
  state.currentContext = { canDirectSwitch: true, currentAuthority: 'AA_TERM_COMPAT' }
  assert.equal(state.canPublish, true)
  state.ctx.permissionPatterns = ['academicAffairs.calendar.view']
  assert.equal(state.canPublish, false)
  assert.equal(state.canEditEvents, false)
  state.ctx.permissionPatterns = ['academicAffairs.*']
  state.ctx.dataScope.scope = 'COLLEGE'
  assert.equal(state.canPublish, false)
  state.ctx.dataScope.scope = 'SCHOOL'
  state.currentContext = { currentAuthority: 'CALENDAR_GOVERNANCE', termId: 'b', canDirectSwitch: false }
  assert.equal(state.canPublish, false)
  state.currentContext.termId = 'a'
  assert.equal(state.canPublish, true)
})

test('calendar classification navigation follows the query and old term results cannot replace the selected calendar', async () => {
  const replies = [deferred(), deferred()]
  let call = 0
  const { state, definition } = page({ academicAffairsApi: { getCalendar: () => replies[call++].promise } })
  const old = state.loadEvents()
  state.termId = 'b'
  const current = state.loadEvents()
  replies[1].resolve({ code: 0, data: [{ eventId: 'b-event' }] })
  await current
  replies[0].resolve({ code: 0, data: [{ eventId: 'a-event' }] })
  await old
  assert.equal(state.events[0].eventId, 'b-event')
  state.loadForTab = () => {}
  definition.watch['$route.query.tab'].call(state, 'holiday')
  assert.equal(state.tab, 'holiday')
  assert.equal(state.draft.eventType, 'HOLIDAY')
})

test('calendar catalog failures have a dedicated retry state and publication stays disabled', async () => {
  const { state } = page({ loadAcademicTermCatalog: async () => { throw new Error('目录暂不可用') } })
  await state.refreshTermCatalog()
  assert.equal(state.catalogError, '目录暂不可用')
  assert.equal(state.termsLoading, false)
  assert.equal(state.canPublish, false)
})

test('calendar navigation keeps the selected term in the URL and waits until a write completes', () => {
  let route, accepted
  const { state, definition } = page({}, { $route: { query: { tab: 'holiday' } }, $router: { replace(value) { route = value } } })
  state.loadForTab = () => {}
  definition.watch['$route.query.tab'].call(state, 'holiday')
  assert.equal(route.query.termId, 'a')
  assert.equal(route.query.tab, 'holiday')
  state.saving = true
  definition.beforeRouteUpdate.call(state, {}, {}, value => { accepted = value })
  assert.equal(accepted, false)
})

test('editing calendar events normalizes returned dates and explicitly clears old swap data and remarks', async () => {
  let sent
  const { state } = page({ academicAffairsApi: { updateCalendarEvent: async (...args) => { sent = args; return { code: 0 } } } })
  state.loadEvents = () => {}
  state.openEdit({ eventId: 'event', eventType: 'SWAP', startDate: '2026-10-02T00:00:00', swapToDate: '2026-10-10T00:00:00', remark: '旧备注' })
  assert.equal(state.editForm.startDate, '2026-10-02')
  state.events = [{ eventType: 'SWAP', startDate: '2026-10-02T00:00:00Z', swapToDate: '2026-10-10T00:00:00Z' }]
  assert.equal(state.filteredEvents[0].dateLabel, '2026-10-02 → 2026-10-10')
  state.editForm.eventType = 'HOLIDAY'
  state.editForm.remark = ''
  await state.submitEdit()
  assert.equal(sent[2].swapToDate, null)
  assert.equal(sent[2].remark, '')
  state.terms[0].status = 'PUBLISHED'
  sent = null
  await state.submitEdit()
  assert.equal(sent, null)
})

test('copy preview is invalidated when its source or target changes, including a response still in flight', async () => {
  const response = deferred()
  const { state, definition } = component('components/AaCalendarCopyPanel', { termCalendarConvenienceApi: { previewCalendarCopy: () => response.promise } }, { targetTermId: 'target', sourceTermId: 'source', terms: [] })
  const pending = state.loadPreview()
  state.sourceTermId = 'other'
  definition.watch.sourceTermId.call(state)
  response.resolve({ code: 0, data: { canConfirm: true } })
  await pending
  assert.equal(state.preview, null)
  assert.equal(state.canApply, false)
})

test('calendar copy keeps its original target throughout writes and requires fresh preview after partial success', async () => {
  const targets = []
  const { state } = component('components/AaCalendarCopyPanel', { academicAffairsApi: { addCalendarEvent: async (target) => {
    targets.push(target)
    state.targetTermId = 'other'
    return targets.length === 1 ? { code: 0 } : { code: 409, message: '日期冲突' }
  } } }, { targetTermId: 'target', preview: { canConfirm: true, items: [{ status: 'READY' }, { status: 'READY' }] } })
  await state.applyCopy()
  assert.deepEqual(targets, ['target', 'target'])
  assert.equal(state.canApply, false)
  assert.equal(state.applying, false)
  assert.match(state.error, /已复制 1 项/)
})
