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
  const sandbox = { sessionStorage: dependencies.sessionStorage, dependencies: { matchPermission, currentUserFromToken: () => null, toast: { success() {}, error() {}, warning() {} }, ...dependencies } }
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

test('month calendar aligns leap days to Monday and does not invent teaching events', () => {
  const { state } = component('components/AaCalendarMonth', {}, { month: '2024-02', events: [] })
  assert.equal(state.days.length, 35)
  assert.equal(state.days[3].date, '2024-02-01')
  assert.equal(state.days.filter(day => day.date).length, 29)
  assert.equal(state.days.filter(day => day.events?.length).length, 0)
})

test('month calendar displays only teaching weeks returned by the formal week service', () => {
  const { state } = component('components/AaCalendarMonth', {}, { month: '2026-09', events: [], weeks: [
    { weekNo: 1, startDate: '2026-09-01', endDate: '2026-09-07' },
    { weekNo: 2, startDate: '2026-09-08', endDate: '2026-09-14' },
  ] })
  assert.equal(state.monthWeeks.length, 2)
  assert.equal(state.days.find(day => day.date === '2026-09-08').week.weekNo, 2)
  assert.equal(state.days.find(day => day.date === '2026-09-15').week, undefined)
})

test('one cross-month swap is shown on both actual dates with distinct meanings', () => {
  const { state } = component('components/AaCalendarMonth', {}, { month: '2099-09', events: [
    { eventId: 'swap', eventType: 'SWAP', startDate: '2099-09-30', swapToDate: '2099-10-02' },
  ] })
  assert.equal(state.monthEvents.length, 1)
  assert.equal(state.days.find(day => day.date === '2099-09-30').events[0].label, '调休（至 2099-10-02）')
  state.moveMonth(1)
  assert.equal(state.month, '2099-10')
  assert.equal(state.days.find(day => day.date === '2099-10-02').events[0].label, '补课（原 2099-09-30）')
  assert.equal(state.days.filter(day => day.events?.length).length, 1)
})

test('a date range spanning a year is counted once and limited to its actual dates', () => {
  const { state } = component('components/AaCalendarMonth', {}, { month: '2026-12', events: [
    { eventId: 'holiday', eventType: 'HOLIDAY', startDate: '2026-12-31T00:00:00', endDate: '2027-01-02T00:00:00' },
  ] })
  state.moveMonth(1)
  assert.equal(state.month, '2027-01')
  assert.equal(state.monthEvents.length, 1)
  assert.equal(state.days.filter(day => day.events?.length).length, 2)
  assert.equal(state.days.find(day => day.date === '2027-01-03').events.length, 0)
})

test('an unavailable explicit calendar term cannot fall back to another editable term', async () => {
  const { state } = page({ loadAcademicTermCatalog: async () => [{ termId: 'other', status: 'DRAFT' }],
    academicAffairsApi: { getCurrentTerm: async () => ({ code: 0, data: { termId: 'other' } }) } },
    { termId: '', $route: { query: { termId: 'missing' } } })
  await state.refreshTermCatalog()
  assert.equal(state.termId, ''); assert.equal(state.canEditEvents, false)
  assert.match(state.catalogError, /入口指定的学期不可用/)
})

test('no current calendar authority means explicit selection, not the first catalog row', async () => {
  const { state } = page({ loadAcademicTermCatalog: async () => [{ termId: 'other', status: 'DRAFT' }],
    academicAffairsApi: { getCurrentTerm: async () => ({ code: 0, data: {} }) } }, { termId: '' })
  await state.refreshTermCatalog(); assert.equal(state.termId, ''); assert.equal(state.canEditEvents, false)
})

test('calendar publish waits for authoritative context and requires permission, school scope and compatible current term', async () => {
  let calls = 0
  const { state } = page({ academicAffairsApi: { publishCalendar: async () => { calls++; return { code: 0 } } } })
  assert.equal(state.canPublish, false)
  await state.doPublish()
  assert.equal(calls, 0)
  state.currentLoading = false
  state.currentContext = { canDirectSwitch: true, currentAuthority: 'AA_TERM_COMPAT' }
  assert.equal(state.canPublish, false, 'authority alone is not a publication review')
  state.publishEvidence = { term: state.terms[0], events: [], slots: [{ status: 'ENABLED' }] }
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

function publication(api = {}, extra = {}, dependencies = {}) {
  return page({ academicAffairsTermDetailApi: { get: api.getTermDetail || (async id => ({ code: 0, data: { termId: id, status: 'DRAFT', version: 3 } })) }, academicAffairsApi: {
    getCalendar: async () => ({ code: 0, data: [] }),
    getTimeSlots: async () => ({ code: 0, data: [{ slotId: 'slot', status: 'ENABLED' }] }),
    getCurrentTerm: async () => ({ code: 0, data: { canDirectSwitch: true, currentAuthority: 'AA_TERM_COMPAT' } }),
    ...api
  }, ...dependencies }, { tab: 'publish', ...extra })
}

test('calendar publication evidence blocks missing enabled slots, unpaired swaps and unavailable sources', async () => {
  const { state } = publication({ getTimeSlots: async () => ({ code: 0, data: [] }),
    getCalendar: async () => ({ code: 0, data: [{ eventId: 'unpaired', eventType: 'SWAP' }] }) })
  await state.loadPublishEvidence()
  assert.equal(state.canPublish, false)
  assert.match(state.publishBlockers.join(' '), /已启用 0 个节次.*未配对 1 项，事件 unpaired/)
  const denied = publication({ getTimeSlots: async () => ({ code: 403, message: '权限不足' }) }).state
  await denied.loadPublishEvidence()
  assert.equal(denied.canPublish, false); assert.equal(denied.publishEvidence, null)
  assert.match(denied.publishReadError, /作息节次：权限不足/)
})

test('late calendar publication evidence cannot replace a new term or a new scope', async () => {
  const reply = deferred()
  const { state } = publication({ getTermDetail: id => id === 'a' ? reply.promise : Promise.resolve({ code: 0, data: { termId: id, status: 'DRAFT' } }) })
  const old = state.loadPublishEvidence()
  state.termId = 'b'
  await state.loadPublishEvidence()
  reply.resolve({ code: 0, data: { termId: 'a', status: 'DRAFT' } }); await old
  assert.equal(state.publishEvidence.term.termId, 'b')
  const scopeReply = deferred()
  const scoped = publication({ getCurrentTerm: () => scopeReply.promise }).state
  const pending = scoped.loadPublishEvidence()
  scoped.ctx.dataScope.scope = 'COLLEGE'
  scoped.invalidatePublishReview()
  scopeReply.resolve({ code: 0, data: { canDirectSwitch: true } }); await pending
  assert.equal(scoped.publishEvidence, null); assert.equal(scoped.canPublish, false)
})

test('calendar publish confirmation fixes its term and dispatches only once', async () => {
  const reply = deferred(), writes = []
  const { state } = publication({ publishCalendar: id => { writes.push(id); return reply.promise } })
  await state.loadPublishEvidence(); state.askPublish()
  assert.equal(state.pendingPublish.termId, 'a')
  const pending = state.doPublish()
  await state.doPublish()
  reply.resolve({ code: 0, data: { termId: 'a', status: 'PUBLISHED' } }); await pending
  assert.deepEqual(writes, ['a'])
  assert.equal(state.activePublishReceipt.kind, 'COMMITTED')
  assert.equal(state.canPublish, false, 'a stale DRAFT read must not reopen a committed command')
  const switched = publication({ publishCalendar: id => { writes.push(id); return reply.promise } }).state
  await switched.loadPublishEvidence(); switched.askPublish()
  switched.termId = 'b'; switched.invalidatePublishReview()
  await switched.loadPublishEvidence(); await switched.doPublish()
  assert.deepEqual(writes, ['a'], 'an old confirmation must not publish the replacement term')
})

test('calendar publish uncertainty survives remount and stays isolated by tenant and account', async () => {
  const stored = new Map()
  const dependencies = {
    currentUserFromToken: () => ({ tenantId: 'school-a', userId: 'operator-a' }),
    sessionStorage: { getItem: key => stored.get(key), setItem: (key, value) => stored.set(key, value) }
  }
  const reply = deferred()
  const first = publication({ publishCalendar: () => reply.promise }, {}, dependencies).state
  await first.loadPublishEvidence(); first.askPublish()
  const pending = first.doPublish()
  const restored = publication({}, {}, dependencies).state
  await restored.loadPublishEvidence()
  assert.equal(restored.activePublishReceipt.kind, 'UNKNOWN'); assert.equal(restored.canPublish, false)
  const other = publication({}, {}, { ...dependencies, currentUserFromToken: () => ({ tenantId: 'school-b', userId: 'operator-a' }) }).state
  await other.loadPublishEvidence()
  assert.equal(other.activePublishReceipt, null); assert.equal(other.canPublish, true)
  reply.resolve({ code: 503001 }); await pending
})

test('an uncertain publish cannot be replayed after a refresh or be converted to success by a status read', async () => {
  let writes = 0, status = 'DRAFT'
  const { state } = publication({
    publishCalendar: async () => { writes++; return { code: 503001, message: '请求超时' } },
    getTermDetail: async id => ({ code: 0, data: { termId: id, status } })
  })
  await state.loadPublishEvidence(); state.askPublish(); await state.doPublish()
  assert.equal(state.activePublishReceipt.kind, 'UNKNOWN'); assert.equal(state.canPublish, false)
  await state.loadPublishEvidence(); state.askPublish(); await state.doPublish()
  assert.equal(writes, 1)
  status = 'PUBLISHED'; await state.loadPublishEvidence()
  assert.equal(state.activePublishReceipt.kind, 'UNKNOWN')
  assert.match(state.activePublishReceipt.message, /不能据此认定/)
})

test('a formal business rejection remains visible with the exact term, and a mismatched success DTO is unknown', async () => {
  const rejected = publication({ publishCalendar: async () => ({ code: 409, bizCode: 'DATA_CONFLICT', message: '学期已冻结' }) }).state
  await rejected.loadPublishEvidence(); rejected.askPublish(); await rejected.doPublish()
  assert.equal(rejected.activePublishReceipt.kind, 'REJECTED')
  assert.match(rejected.activePublishReceipt.message, /学期 a.*学期已冻结/)
  const forbidden = publication({ publishCalendar: async () => ({ code: 403001, bizCode: 'NO_PERMISSION', message: '无校历发布权限' }) }).state
  await forbidden.loadPublishEvidence(); forbidden.askPublish(); await forbidden.doPublish()
  assert.equal(forbidden.activePublishReceipt.kind, 'REJECTED')
  assert.match(forbidden.activePublishReceipt.message, /无校历发布权限/)
  const wrong = publication({ publishCalendar: async () => ({ code: 0, data: { termId: 'b', status: 'PUBLISHED' } }) }).state
  await wrong.loadPublishEvidence(); wrong.askPublish(); await wrong.doPublish()
  assert.equal(wrong.activePublishReceipt.kind, 'UNKNOWN')
})

test('late current-authority reads cannot overwrite a newer calendar publication review', async () => {
  const reply = deferred()
  let calls = 0
  const { state } = publication({ getCurrentTerm: () => ++calls === 1 ? reply.promise : Promise.resolve({ code: 0, data: { termId: 'a', currentAuthority: 'CALENDAR_GOVERNANCE' } }) })
  const old = state.loadCurrentContext()
  await state.loadPublishEvidence()
  reply.resolve({ code: 0, data: { termId: 'old', canDirectSwitch: true } }); await old
  assert.equal(state.currentContext.termId, 'a')
  assert.equal(state.canPublish, true)
})

function archive(dependencies = {}, extra = {}) {
  return component('components/AaCalendarArchivePanel', {
    academicAffairsTermDetailApi: { get: async id => ({ code: 0, data: { termId: id, version: 3 } }) },
    academicAffairsApi: { getTermArchiveOverview: async () => ({ code: 0, data: [{ termId: 'a', archiveBatchId: null }] }) },
    ...dependencies
  }, { term: { termId: 'a', status: 'DRAFT' }, ...extra })
}

test('archive view keeps UNKNOWN and missing evidence distinct from PASS and uses the selected term', async () => {
  const reads = []
  const { state } = archive({ academicAffairsArchiveApi: { precheck: async id => {
    reads.push(id); return { code: 0, data: { termId: id, domains: [{ domain: 'GRADE', result: 'UNKNOWN', recordCount: 0 }] } }
  } } })
  await state.load(); await state.loadEvidence()
  assert.deepEqual(reads, ['a'])
  assert.equal(state.domains[0].result, 'UNKNOWN')
  assert.equal(state.resultLabel(undefined), '待核 · 未知')
  assert.equal(state.resultType('UNKNOWN'), 'warning')
  assert.equal(state.batch, null); assert.equal(state.sealed, false)
})

test('an archived term with missing batch cannot substitute a live precheck for sealed facts', async () => {
  let reads = 0
  const { state } = archive({ academicAffairsArchiveApi: { precheck: async () => { reads++ } } }, { term: { termId: 'a', status: 'ARCHIVED' } })
  await state.load(); await state.loadEvidence()
  assert.equal(reads, 0); assert.match(state.evidenceError, /不能用实时预检替代历史封存证据/)
})

test('sealed evidence checks both batch and term identities and does not query another batch manifest', async () => {
  let manifestReads = 0
  const { state } = archive({
    academicAffairsApi: { getTermArchiveOverview: async () => ({ code: 0, data: [{ termId: 'a', archiveBatchId: 'batch-a', archiveBatchStatus: 'ARCHIVED' }] }) },
    academicAffairsArchiveApi: { getBatch: async () => ({ code: 0, data: { termId: 'b', batchId: 'batch-a', status: 'ARCHIVED' } }) },
    academicArchiveCorrectionApi: { verifyManifest: async () => { manifestReads++ } }
  }, { term: { termId: 'a', status: 'ARCHIVED' } })
  await state.load(); await state.loadEvidence()
  assert.match(state.evidenceError, /封存批次身份或状态已变化/)
  assert.equal(manifestReads, 0); assert.equal(state.batch, null)
})

test('a late archive precheck cannot expose a previous term in the new term panel', async () => {
  const reply = deferred()
  const { state } = archive({ academicAffairsArchiveApi: { precheck: () => reply.promise } })
  await state.load(); const pending = state.loadEvidence()
  state.term = { termId: 'b', status: 'DRAFT' }; await state.load()
  reply.resolve({ code: 0, data: { termId: 'a', domains: [{ domain: 'GRADE', result: 'PASS' }] } }); await pending
  assert.equal(state.domains.length, 0)
  assert.equal(state.evidenceRequested, false)
})

test('term-only roles do not request archive evidence and archive readers do not request manage-only manifest verification', async () => {
  let checks = 0, manifests = 0
  const dependencies = {
    academicAffairsApi: { getTermArchiveOverview: async () => ({ code: 0, data: [{ termId: 'a', archiveBatchId: 'batch-a', archiveBatchStatus: 'ARCHIVED' }] }) },
    academicAffairsArchiveApi: { getBatch: async () => { checks++; return { code: 0, data: { termId: 'a', batchId: 'batch-a', status: 'ARCHIVED', items: [{ domain: 'GRADE', result: 'UNKNOWN' }] } } } },
    academicArchiveCorrectionApi: { verifyManifest: async () => { manifests++ } }
  }
  const { state } = archive(dependencies, { term: { termId: 'a', status: 'ARCHIVED' } })
  await state.load(); state.ctx.permissionPatterns = ['academicAffairs.term.view']; await state.loadEvidence()
  assert.equal(checks, 0)
  state.ctx.permissionPatterns.push('academicAffairs.archive.view'); await state.loadEvidence()
  assert.equal(checks, 1); assert.equal(manifests, 0)
  assert.match(state.manifestError, /无封存版本链核验权限/)
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
