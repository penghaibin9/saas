import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { installDirtyFormGuard } from '../src/router/dirtyFormGuard.js'

function component(path, dependencies = {}, extra = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/${path}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { window: dependencies.window, sessionStorage: dependencies.sessionStorage, dependencies: { matchPermission, currentUserFromToken: () => null, toast: { success() {}, error() {}, warning() {} }, ...dependencies } }
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
  const { state } = component('components/AaCalendarCopyPanel', {
    termCalendarConvenienceApi: { previewCalendarCopy: async () => ({ code: 0, data: { canConfirm: true, items: [{ status: 'READY' }, { status: 'READY' }] } }) },
    academicAffairsApi: { addCalendarEvent: async (target) => {
      targets.push(target)
      return targets.length === 1 ? { code: 0 } : { code: 409, message: '日期冲突' }
    } }
  }, { targetTermId: 'target', sourceTermId: 'source', academicFlow: { identity: () => 'local-stable-identity' } })
  // Explicit local VM regression exception: actual preview creates ownership; no HTTP/DB adapter is used.
  await state.loadPreview()
  await state.applyCopy()
  assert.deepEqual(targets, ['target', 'target'])
  assert.equal(state.canApply, false)
  assert.equal(state.applying, false)
  assert.match(state.error, /已复制 1 项/)
})

for (const changed of ['source', 'target', 'identity']) {
  test(`calendar copy VM watcher contract stops stale local continuation after ${changed} changes`, async () => {
    const targets = [], applied = []
    let identity = 'local-original-identity'
    const { state, definition } = component('components/AaCalendarCopyPanel', {
      termCalendarConvenienceApi: { previewCalendarCopy: async () => ({ code: 0, data: { canConfirm: true, items: [{ status: 'READY' }, { status: 'READY' }] } }) },
      academicAffairsApi: { addCalendarEvent: async target => {
        targets.push(target)
        if (changed === 'source') state.sourceTermId = 'other-source'
        if (changed === 'target') state.targetTermId = 'other-target'
        if (changed === 'identity') identity = 'local-new-identity'
        assert.equal(state.canApply, false, 'Changed ownership cannot reuse old preview before watcher invocation')
        // Existing VM helper is not reactive: explicitly invoke the actual source watcher contract.
        const watcher = definition.watch[changed === 'source' ? 'sourceTermId' : changed === 'target' ? 'targetTermId' : 'contextKey']
        ;(typeof watcher === 'function' ? watcher : watcher.handler).call(state)
        return { code: 0 }
      } }
    }, { targetTermId: 'target', sourceTermId: 'source', terms: [], academicFlow: { identity: () => identity }, $emit(name, value) { if (name === 'applied') applied.push(value) } })
    await state.loadPreview()
    assert.equal(state.canApply, true)
    // Bounded local VM exception only; compiled consumers and browser acceptance never invoke apply.
    await state.applyCopy()
    assert.deepEqual(targets, ['target'])
    assert.deepEqual(applied, [])
    assert.equal(state.preview, null)
    assert.equal(state.applying, false)
    assert.equal(state.canApply, false)
    assert.equal(state.error, '')
  })
}


function draftPage(api = {}, extra = {}) {
  const calls = []
  const { state, definition } = page({ window: { __SAAS_DIRTY_FORM_GUARD__: { markSaved: () => calls.push('saved'), markDirty: () => calls.push('dirty') } }, academicAffairsApi: api }, { $refs: {}, ...extra })
  state.resetDraft(); state.loadEvents = () => calls.push('read'); state.loadForTab = () => calls.push('load')
  return { state, definition, calls }
}
const calendarAck = (termId = 'a', eventId = 'e') => ({ code: 0, data: { termId, eventId, version: 1, eventType: 'TEACHING', startDate: '2026-10-01T00:00:00', endDate: '2026-10-01T00:00:00', swapToDate: null, remark: 'saved' } })

test('calendar tab and term intents preserve hidden inputs until successful route adoption', async () => {
  const { state, definition } = draftPage({}, { $route: { query: { termId: 'a', tab: 'events', returnToken: 'origin', page: '2' } } })
  state.draft.remark = 'hidden draft'; state.createVisible = false
  const routes = []; state.$router.replace = value => { routes.push(value); return Promise.resolve({ type: 'cancelled' }) }
  await state.switchTab('holiday')
  assert.equal(state.tab, 'events'); assert.equal(state.draft.remark, 'hidden draft'); assert.equal(state.draft.eventType, 'TEACHING')
  assert.equal(routes[0].query.tab, 'holiday'); assert.equal(routes[0].query.termId, 'a'); assert.equal(routes[0].query.returnToken, 'origin')
  await state.onTermChange('b')
  assert.equal(state.termId, 'a'); assert.equal(state.draft.remark, 'hidden draft')
  assert.equal(routes[1].query.termId, 'b'); assert.equal(routes[1].query.page, '2')
  state.$route.query = { termId: 'b', tab: 'holiday', returnToken: 'origin', page: '2' }
  definition.watch['$route.query.tab'].call(state, 'holiday')
  definition.watch['$route.query.termId'].call(state, 'b')
  assert.equal(state.termId, 'b'); assert.equal(state.tab, 'holiday'); assert.equal(state.draft.remark, ''); assert.equal(state.draft.eventType, 'HOLIDAY')
  assert.equal(state.createVisible, false); assert.equal(state.editForm, null)
})

test('calendar rejected route request retains draft and active editor', async () => {
  const { state } = draftPage({}, { $router: { replace: () => Promise.reject(new Error('route unavailable')) } })
  state.draft.remark = 'retain'; state.editForm = { eventId: 'edit', remark: 'retain edit' }; state.editVisible = true
  await state.switchTab('holiday'); await state.onTermChange('b')
  assert.equal(state.tab, 'events'); assert.equal(state.termId, 'a'); assert.equal(state.draft.remark, 'retain'); assert.equal(state.editForm.remark, 'retain edit'); assert.equal(state.editVisible, true)
})

test('calendar model-only event type and date changes explicitly mark dirty while hydration does not', () => {
  const { state, calls } = draftPage()
  assert.deepEqual(calls, [])
  state.updateEventField('create', 'eventType', 'EXAM'); state.updateEventField('create', 'startDate', '2026-10-01')
  assert.deepEqual(calls, ['dirty', 'dirty']); assert.equal(state.draft.eventType, 'EXAM'); assert.equal(state.draft.startDate, '2026-10-01')
  state.updateEventField('create', 'startDate', '2026-10-01'); assert.equal(calls.length, 2)
  state.adding = true; state.updateEventField('create', 'remark', 'late user'); assert.equal(state.draft.remark, '')
})

test('calendar successful create only clears its saved draft and retains hidden edit or copy work', async () => {
  for (const other of ['none', 'edit', 'copy']) {
    const { state, calls } = draftPage({ addCalendarEvent: async () => calendarAck() })
    state.draft.startDate = '2026-10-01'; state.draft.remark = 'saved'
    if (other === 'edit') { state.openEdit({ eventId: 'old', eventType: 'TEACHING', startDate: '2026-10-02', remark: 'original' }); state.updateEventField('edit', 'remark', 'hidden edit'); state.editVisible = false }
    if (other === 'copy') state.$refs.calendarCopyPanel = { preview: { items: [{ sourceEventId: 'source' }] }, reviewConfirmed: true }
    await state.addEvent()
    assert.equal(state.draft.remark, ''); assert.equal(state.createVisible, false)
    if (other === 'none') assert.ok(calls.includes('saved'))
    else { assert.equal(calls.includes('saved'), false); assert.ok(calls.includes('dirty')) }
    if (other === 'edit') assert.equal(state.editForm.remark, 'hidden edit')
  }
})

test('calendar successful edit retains hidden create draft and keeps shared dirty protection', async () => {
  const { state, calls } = draftPage({ updateCalendarEvent: async () => calendarAck() })
  state.draft.remark = 'hidden create'; state.openEdit({ eventId: 'e', eventType: 'TEACHING', startDate: '2026-10-01', remark: 'old' }); state.updateEventField('edit', 'remark', 'saved')
  await state.submitEdit(); assert.equal(state.draft.remark, 'hidden create'); assert.equal(state.editForm.remark, 'saved'); assert.equal(state.editVisible, false); assert.equal(calls.includes('saved'), false)
  state.resetDraft(); await state.submitEdit(); assert.ok(calls.includes('saved'))
})

test('calendar failed malformed and late create acknowledgements preserve inputs and dirty', async () => {
  for (const response of [{ code: 409001, message: 'reject' }, calendarAck('other'), { code: 0, message: 'ok', data: { termId: 'a', eventId: 'e' } }]) {
    const { state, calls } = draftPage({ addCalendarEvent: async () => response }); state.draft.startDate = '2026-10-01'; state.draft.remark = 'saved'; state.createVisible = true
    await state.addEvent(); assert.equal(state.draft.remark, 'saved'); assert.equal(state.createVisible, true); assert.equal(calls.includes('saved'), false); assert.match(state.formError, /reject|回执|核对/)
  }
  for (const change of [state => { state.termId = 'b' }, state => { state.ctx.permissionPatterns = ['academicAffairs.calendar.view'] }, state => { state.draft.remark = 'newer local' }]) {
    const reply = deferred(); const { state, calls } = draftPage({ addCalendarEvent: () => reply.promise }); state.draft.startDate = '2026-10-01'; state.draft.remark = 'saved'; state.createVisible = true
    const pending = state.addEvent(); change(state); reply.resolve(calendarAck()); await pending
    assert.equal(state.createVisible, true); assert.equal(calls.includes('saved'), false); assert.notEqual(state.draft.remark, '')
  }
})

test('calendar wrong-event or late edit acknowledgement cannot replace a different editor', async () => {
  const { state, calls } = draftPage({ updateCalendarEvent: async () => calendarAck('a', 'wrong') }); state.openEdit({ eventId: 'e', eventType: 'TEACHING', startDate: '2026-10-01', remark: 'local' })
  await state.submitEdit(); assert.equal(state.editVisible, true); assert.equal(state.editForm.remark, 'local'); assert.equal(calls.includes('saved'), false)
  const reply = deferred(); const late = draftPage({ updateCalendarEvent: () => reply.promise }); late.state.openEdit({ eventId: 'e', eventType: 'TEACHING', startDate: '2026-10-01', remark: 'local' })
  const pending = late.state.submitEdit(); late.state.editForm = { ...late.state.editForm, eventId: 'new', remark: 'new editor' }; reply.resolve(calendarAck()); await pending
  assert.equal(late.state.editForm.eventId, 'new'); assert.equal(late.state.editForm.remark, 'new editor'); assert.equal(late.calls.includes('saved'), false)
})


test('calendar uses the existing guard for hidden editor dirty and retains it after cancelled or aborted navigation', async () => {
  const previous = { window: globalThis.window, document: globalThis.document }
  const from = { name: 'aa-calendar', path: '/admin/academic-affairs/calendar', fullPath: '/admin/academic-affairs/calendar?termId=a&tab=events' }
  const to = { ...from, fullPath: '/admin/academic-affairs/calendar?termId=a&tab=holiday' }
  let before, after, accepted = false
  globalThis.window = { addEventListener() {}, removeEventListener() {} }
  globalThis.document = { addEventListener() {}, removeEventListener() {} }
  const router = { currentRoute: { value: from }, beforeEach(fn) { before = fn }, beforeResolve(fn) { this.resolveGuard = fn; return () => { if (this.resolveGuard === fn) this.resolveGuard = null } }, afterEach(fn) { after = fn } }
  let dispose
  try {
    dispose = installDirtyFormGuard(router)
    const guard = window.__SAAS_DIRTY_FORM_GUARD__
    assert.equal(guard.handlesRoute(from), true); assert.equal(guard.handlesRoute({ name: 'aa-time-slots' }), true); assert.equal(guard.handlesRoute({ name: 'aa-unrelated-readonly' }), false)
    guard.registerConfirmation(() => accepted)
    assert.equal(await before(to, from), true)
    guard.markDirty(); assert.equal(await before(to, from), false); assert.equal(guard.isDirty(), true)
    accepted = true; assert.equal(await before(to, from), true); after(to, from, new Error('aborted')); assert.equal(guard.isDirty(), true)
    assert.equal(await before(to, from), true); after(to, from); assert.equal(guard.isDirty(), false)
  } finally {
    dispose?.()
    for (const [key, value] of Object.entries(previous)) { if (value === undefined) delete globalThis[key]; else globalThis[key] = value }
  }
})


const reopenCalendarRow = (remark = 'original') => ({ eventId: 'e', termId: 'a', eventType: 'HOLIDAY', startDate: '2028-04-03T00:00:00Z', endDate: '2028-04-05T00:00:00Z', swapToDate: null, remark, version: 0 })

test('calendar same-owner same-row reopening retains unsaved remark, baseline and error', () => {
  const { state, calls } = draftPage()
  const row = reopenCalendarRow()
  state.openEdit(row)
  const form = state.editForm, baseline = state.editBaseline, owner = state.editOwnerKey
  state.updateEventField('edit', 'remark', 'unsaved reopen marker')
  state.editError = '上次保存失败，输入仍未保存'
  state.editVisible = false
  state.openEdit(row)
  assert.equal(state.editForm.remark, 'unsaved reopen marker')
  assert.equal(state.editForm, form)
  assert.equal(state.editBaseline, baseline)
  assert.equal(state.editOwnerKey, owner)
  assert.equal(state.editError, '上次保存失败，输入仍未保存')
  assert.equal(state.editVisible, true)
  assert.equal(calls.includes('saved'), false)
  assert.equal(calls.filter(call => call === 'dirty').length, 1)
})

test('calendar clean same-row reopening hydrates a newer formal row without phantom dirty', () => {
  const { state, calls } = draftPage()
  state.openEdit(reopenCalendarRow())
  state.editError = '旧提示'
  state.editVisible = false
  state.openEdit({ ...reopenCalendarRow('formal latest'), version: 1 })
  assert.equal(state.editForm.remark, 'formal latest')
  assert.equal(state.editBaseline, state.eventSignature(state.editForm))
  assert.equal(state.editOwnerKey, JSON.stringify([state.contextKey, String(state.termId)]))
  assert.equal(state.editError, '')
  assert.deepEqual(calls, [])
})

test('calendar saved editor reopens fresh formal data while hidden create remains protected', async () => {
  const { state, calls } = draftPage({ updateCalendarEvent: async () => calendarAck() })
  state.openEdit({ eventId: 'e', eventType: 'TEACHING', startDate: '2026-10-01', remark: 'original' })
  state.updateEventField('edit', 'remark', 'saved')
  state.updateEventField('create', 'remark', 'hidden create marker')
  await state.submitEdit()
  assert.equal(state.editBaseline, state.eventSignature(state.editForm))
  assert.equal(state.editOwnerKey, JSON.stringify([state.contextKey, String(state.termId)]))
  assert.equal(state.editVisible, false)
  state.openEdit({ ...calendarAck().data, version: 2, remark: 'fresh after saved' })
  assert.equal(state.editForm.remark, 'fresh after saved')
  assert.equal(state.editBaseline, state.eventSignature(state.editForm))
  assert.equal(state.draft.remark, 'hidden create marker')
  assert.equal(calls.includes('saved'), false)
  assert.ok(calls.includes('dirty'))
})

test('calendar reopening the same event ID in a different context hydrates the new owner', () => {
  const { state } = draftPage()
  state.openEdit(reopenCalendarRow())
  state.updateEventField('edit', 'remark', 'old context marker')
  state.editError = '旧上下文提示'
  const oldOwner = state.editOwnerKey
  state.ctx = { ...state.ctx, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '新上下文' } }
  state.openEdit(reopenCalendarRow('new context formal'))
  assert.equal(state.editForm.remark, 'new context formal')
  assert.equal(state.editBaseline, state.eventSignature(state.editForm))
  assert.equal(state.editError, '')
  assert.notEqual(state.editOwnerKey, oldOwner)
  assert.equal(state.editOwnerKey, JSON.stringify([state.contextKey, String(state.termId)]))
})

test('calendar reopening after a term change cannot retain the previous term editor owner', () => {
  const { state } = draftPage()
  state.openEdit(reopenCalendarRow())
  state.updateEventField('edit', 'remark', 'old term marker')
  const oldOwner = state.editOwnerKey
  state.termId = 'b'
  state.openEdit({ ...reopenCalendarRow('new term formal'), termId: 'b' })
  assert.equal(state.editForm.remark, 'new term formal')
  assert.equal(state.editBaseline, state.eventSignature(state.editForm))
  assert.notEqual(state.editOwnerKey, oldOwner)
  assert.equal(state.editOwnerKey, JSON.stringify([state.contextKey, 'b']))
  state.applyRouteSelection('a', 'holiday')
  assert.equal(state.editForm, null)
  assert.equal(state.editBaseline, null)
  assert.equal(state.editOwnerKey, '')
})

// Pure VM consumer contracts: local canonical adapters only, no HTTP or browser claim.
async function completedCopyFixture({ hidden = '', rows = 1, refuseSecond = false } = {}) {
  const operations = [], emitted = [], refreshes = []
  const parent = draftPage({ getCalendar: async id => { operations.push(`read:${id}`); return { code: 0, data: [] } } })
  parent.state.loadEvents = parent.definition.methods.loadEvents
  if (hidden === 'create') parent.state.draft.remark = 'keep hidden create'
  if (hidden === 'edit') {
    parent.state.openEdit({ eventId: 'hidden', eventType: 'TEACHING', startDate: '2030-02-04', remark: 'baseline' })
    parent.state.editForm.remark = 'keep hidden edit'; parent.state.editVisible = false
  }
  const previewItems = Array.from({ length: rows }, (_, i) => ({ sourceEventId: `source-${i}`, eventType: 'HOLIDAY', status: 'REVIEW', startDate: '2030-04-04', endDate: '2030-04-06', remark: `copied-${i}` }))
  let writes = 0
  const { state: child } = component('components/AaCalendarCopyPanel', {
    termCalendarConvenienceApi: { previewCalendarCopy: async () => ({ code: 0, data: { items: previewItems, canConfirm: true, readyCount: 0, reviewCount: rows, blockedCount: 0, targetExistingCount: 0 } }) },
    academicAffairsApi: { addCalendarEvent: async (termId, body) => {
      operations.push(`write:${++writes}`)
      return refuseSecond && writes === 2 ? { code: 409001, message: 'canonical conflict' } : { code: 0, data: { eventId: `local-${writes}`, termId, version: 0, ...body, swapToDate: null } }
    } },
  }, { terms: [{ termId: 'source', yearCode: '2027-2028', termNo: 2 }], sourceTermId: 'source', targetTermId: 'a', disabled: false })
  parent.state.$refs.calendarCopyPanel = child
  const template = readFileSync(new URL('../src/modules/academicAffairs/views/AaCalendarView.vue', import.meta.url), 'utf8')
  const consumer = template.match(/@applied="([^"]+)"/)[1]
  assert.equal(typeof parent.state[consumer], 'function', 'Invoke the actual template consumer, including the immutable old loadEvents binding')
  child.$emit = (name, result) => {
    if (name !== 'applied') return
    emitted.push({ applied: result.applied, partial: result.partial, preview: child.preview, reviewConfirmed: child.reviewConfirmed, error: child.error })
    refreshes.push(Promise.resolve(parent.state[consumer](result)))
  }
  await child.loadPreview(); child.reviewConfirmed = true
  assert.equal(child.canApply, true)
  await child.applyCopy(); await Promise.all(refreshes)
  return { parent, child, emitted, operations, writes }
}

test('completed calendar copy emits final child state and actual parent consumer clears only completed dirty', async () => {
  const f = await completedCopyFixture()
  assert.equal(f.emitted.length, 1)
  assert.equal(f.emitted[0].preview, null, 'Completed copy must not be observed by its consumer as a pending preview')
  assert.equal(f.emitted[0].reviewConfirmed, false)
  assert.equal(f.emitted[0].applied, 1); assert.equal(f.emitted[0].partial, false)
  assert.equal(f.writes, 1); assert.deepEqual(f.operations, ['write:1', 'read:a'])
  assert.deepEqual(f.parent.calls, ['saved'])
  assert.equal(f.child.error, '')
})

test('completed copy preserves hidden create and edit drafts instead of clearing their protection', async () => {
  for (const hidden of ['create', 'edit']) {
    const f = await completedCopyFixture({ hidden })
    assert.equal(f.emitted[0].preview, null); assert.equal(f.emitted[0].reviewConfirmed, false)
    assert.equal(f.parent.calls.includes('saved'), false); assert.ok(f.parent.calls.includes('dirty'))
    if (hidden === 'create') assert.equal(f.parent.state.draft.remark, 'keep hidden create')
    else assert.equal(f.parent.state.editForm.remark, 'keep hidden edit')
    assert.equal(f.writes, 1); assert.deepEqual(f.operations, ['write:1', 'read:a'])
  }
})

test('partial copy preserves canonical conflict count and error while its parent retains another draft', async () => {
  const f = await completedCopyFixture({ hidden: 'create', rows: 2, refuseSecond: true })
  assert.equal(f.writes, 2); assert.deepEqual(f.operations, ['write:1', 'write:2', 'read:a'])
  assert.equal(f.emitted.length, 1); assert.equal(f.emitted[0].applied, 1); assert.equal(f.emitted[0].partial, true)
  assert.equal(f.emitted[0].preview, null); assert.equal(f.emitted[0].reviewConfirmed, false)
  assert.match(f.emitted[0].error, /已复制 1 项；第 2 项被系统拒绝：canonical conflict/)
  assert.equal(f.child.error, f.emitted[0].error); assert.equal(f.child.applying, false)
  assert.equal(f.parent.state.draft.remark, 'keep hidden create')
  assert.equal(f.parent.calls.includes('saved'), false); assert.ok(f.parent.calls.includes('dirty'))
})

test('copy notification without an actual positive write refreshes but does not claim a saved form', async () => {
  for (const payload of [undefined, {}, { applied: 0 }, { applied: -1 }, { applied: '1' }, { applied: 0.5 }]) {
    const reads = [], { state, calls, definition } = draftPage({ getCalendar: async id => { reads.push(id); return { code: 0, data: [] } } })
    state.loadEvents = definition.methods.loadEvents
    await state.onCopyApplied(payload)
    assert.deepEqual(reads, ['a']); assert.deepEqual(calls, [])
  }
})

test('copy saved reconciliation happens before refresh and cannot clear a later pending input', async () => {
  const pending = deferred(), { state, calls, definition } = draftPage({ getCalendar: () => pending.promise })
  state.loadEvents = definition.methods.loadEvents
  state.$refs.calendarCopyPanel = { preview: null, reviewConfirmed: false, loading: false, applying: false }
  const reading = state.onCopyApplied({ applied: 1, partial: false })
  assert.deepEqual(calls, ['saved'])
  state.updateEventField('create', 'remark', 'later local input')
  assert.deepEqual(calls, ['saved', 'dirty'])
  pending.resolve({ code: 0, data: [] }); await reading
  assert.equal(state.draft.remark, 'later local input'); assert.deepEqual(calls, ['saved', 'dirty'])
})


test('ordinary calendar editor keeps the first event remark, baseline and error until a different-event decision', () => {
  // Declared local method fixture, not a real account/permission or API result.
  const first = { eventId: 'declared-first', termId: '4', eventType: 'HOLIDAY', startDate: '2028-04-03', endDate: '2028-04-05', swapToDate: null, remark: 'first saved remark', version: 1 }
  const second = { eventId: 'declared-second', termId: '4', eventType: 'HOLIDAY', startDate: '2028-05-03', endDate: '2028-05-05', swapToDate: null, remark: 'second saved remark', version: 0 }
  const { state } = draftPage({}, {
    ctx: { currentRole: { roleCode: 'ACADEMIC_ADMIN' }, dataScope: { scope: 'TENANT_ALL' }, permissionPatterns: ['academicAffairs.calendar.view', 'academicAffairs.calendar.manage'] },
    terms: [{ termId: '4', status: 'DRAFT' }], termId: '4', events: [first, second]
  })
  assert.equal(state.canEditEvents, true)
  state.openEdit(first)
  state.updateEventField('edit', 'remark', 'A6 different-event pending remark')
  state.editError = 'The original field validation message belongs to this draft'
  state.editVisible = false
  const pending = { form: JSON.stringify(state.editForm), baseline: state.editBaseline, error: state.editError }
  state.openEdit(second)
  assert.deepEqual({ form: JSON.stringify(state.editForm), baseline: state.editBaseline, error: state.editError }, pending,
    'selecting a different calendar event cannot discard the first remark before an explicit decision')
})


function calendarSwitchFixture(api = {}, extra = {}) {
  const first = { eventId: '2', termId: '4', eventType: 'HOLIDAY', startDate: '2028-04-03', endDate: '2028-04-05', swapToDate: null, remark: 'first formal remark', version: 1 }
  const second = { eventId: '5', termId: '4', eventType: 'HOLIDAY', startDate: '2028-05-03', endDate: '2028-05-05', swapToDate: null, remark: 'second formal remark', version: 0 }
  const fixture = draftPage(api, {
    ctx: { currentRole: { roleCode: 'ACADEMIC_ADMIN' }, dataScope: { scope: 'TENANT_ALL' }, permissionPatterns: ['academicAffairs.calendar.view', 'academicAffairs.calendar.manage'] },
    academicFlow: { identity: () => 'declared-local-identity' },
    terms: [{ termId: '4', status: 'DRAFT' }, { termId: '5', status: 'DRAFT' }], termId: '4', events: [first, second], ...extra
  })
  fixture.state.openEdit(first)
  fixture.state.updateEventField('edit', 'remark', 'different-event pending marker')
  fixture.state.editError = 'original failed-save message'
  fixture.state.editVisible = false
  fixture.calls.length = 0
  return { ...fixture, first, second }
}

test('calendar different-event cancel reopens the original remark with its baseline, owner and error intact', () => {
  const { state, calls, first, second } = calendarSwitchFixture()
  const form = state.editForm, snapshot = JSON.stringify(form), baseline = state.editBaseline, owner = state.editOwnerKey
  state.openEdit(second)
  assert.equal(state.eventSwitchVisible, true); assert.equal(state.editForm, form)
  assert.equal(JSON.stringify(state.editForm), snapshot); assert.equal(state.editBaseline, baseline); assert.equal(state.editError, 'original failed-save message')
  state.cancelEventSwitch()
  assert.equal(state.eventSwitchVisible, false); assert.equal(state.pendingEventSwitch, null); assert.equal(state.editVisible, true)
  assert.equal(state.editForm, form); assert.equal(state.editForm.eventId, first.eventId)
  assert.equal(state.editForm.remark, 'different-event pending marker'); assert.equal(state.editBaseline, baseline)
  assert.equal(state.editOwnerKey, owner); assert.equal(state.editError, 'original failed-save message')
  assert.equal(calls.includes('saved'), false)
})

test('explicit calendar discard adopts only the current target while every hidden create or copy intent stays dirty', () => {
  for (const other of ['none', 'create', 'copy preview', 'copy review', 'copy loading', 'copy applying']) {
    const { state, calls, second } = calendarSwitchFixture()
    if (other === 'create') state.updateEventField('create', 'remark', 'hidden create remains')
    else if (other.startsWith('copy')) state.$refs.calendarCopyPanel = {
      preview: other === 'copy preview' ? { items: [] } : null,
      reviewConfirmed: other === 'copy review', loading: other === 'copy loading', applying: other === 'copy applying'
    }
    state.openEdit(second); assert.equal(state.eventSwitchVisible, true)
    state.confirmEventSwitch()
    assert.equal(state.eventSwitchVisible, false); assert.equal(state.pendingEventSwitch, null); assert.equal(state.editVisible, true)
    assert.equal(state.editForm.eventId, second.eventId); assert.equal(state.editForm.remark, second.remark)
    assert.equal(state.editBaseline, state.eventSignature(state.editForm)); assert.equal(state.editError, '')
    assert.equal(state.editOwnerKey, JSON.stringify([state.contextKey, String(state.termId)]))
    if (other === 'none') assert.deepEqual(calls, ['saved'])
    else { assert.equal(calls.includes('saved'), false, other); assert.ok(calls.includes('dirty'), other) }
  }
})

test('calendar pending same-row and clean or acknowledged saved other-row editing stays compatible', async () => {
  const same = calendarSwitchFixture(), baseline = same.state.editBaseline
  same.state.openEdit(same.first)
  assert.equal(same.state.eventSwitchVisible, false); assert.equal(same.state.editVisible, true)
  assert.equal(same.state.editForm.remark, 'different-event pending marker'); assert.equal(same.state.editBaseline, baseline)
  const clean = calendarSwitchFixture()
  clean.state.editForm.remark = clean.first.remark
  clean.state.openEdit(clean.second)
  assert.equal(clean.state.eventSwitchVisible, false); assert.equal(clean.state.editForm.remark, clean.second.remark)
  const saved = calendarSwitchFixture({ updateCalendarEvent: async (termId, eventId, body) => ({ code: 0, data: { ...body, eventId, termId, version: 2 } }) })
  await saved.state.submitEdit()
  assert.equal(saved.state.editBaseline, saved.state.eventSignature(saved.state.editForm))
  saved.state.openEdit(saved.second)
  assert.equal(saved.state.eventSwitchVisible, false); assert.equal(saved.state.editForm.eventId, saved.second.eventId)
})

test('calendar confirm rejects stale identity, context, term, source draft, baseline, target signature or separate version', () => {
  const mutations = [
    state => { state.academicFlow = { identity: () => 'another local identity' } },
    state => { state.ctx.dataScope = { scope: 'COLLEGE', collegeId: 'declared-other' } },
    state => { state.termId = '5' },
    state => { state.editForm.remark = 'newer local remark' },
    state => { state.editBaseline = 'different baseline' },
    state => { state.editOwnerKey = 'another source owner' },
    state => { state.editIdentityKey = 'different stored editor identity' },
    state => { state.events = [state.events[0]] },
    state => { state.events[1] = { ...state.events[1], remark: 'new formal target' } },
    state => { state.events[1] = { ...state.events[1], termId: '5' } },
    state => { state.events[1] = { ...state.events[1], version: 1 } }
  ]
  for (const change of mutations) {
    const { state, calls, second } = calendarSwitchFixture()
    state.openEdit(second); assert.equal(state.eventSwitchVisible, true)
    change(state)
    const snapshot = JSON.stringify(state.editForm), baseline = state.editBaseline, error = state.editError
    state.confirmEventSwitch()
    assert.equal(JSON.stringify(state.editForm), snapshot); assert.equal(state.editBaseline, baseline); assert.equal(state.editError, error)
    assert.equal(state.eventSwitchVisible, false); assert.equal(state.pendingEventSwitch, null); assert.equal(calls.includes('saved'), false)
  }
})

test('calendar busy, lost manage permission, locked status, disposed or malformed current target never discards a draft', () => {
  const denials = [
    state => { state.copying = true }, state => { state.saving = true },
    state => { state.ctx.permissionPatterns = ['academicAffairs.calendar.view'] },
    state => { state.terms[0].status = 'PUBLISHED' }, state => { state.termsLoading = true },
    state => { state.catalogError = 'unavailable catalog' }, state => { state.disposed = true }
  ]
  for (const deny of denials) {
    const { state, calls, second } = calendarSwitchFixture()
    state.openEdit(second); assert.equal(state.eventSwitchVisible, true)
    deny(state)
    const snapshot = JSON.stringify(state.editForm), baseline = state.editBaseline
    state.confirmEventSwitch()
    assert.equal(JSON.stringify(state.editForm), snapshot); assert.equal(state.editBaseline, baseline); assert.equal(calls.includes('saved'), false)
    state.openEdit(second); assert.equal(state.eventSwitchVisible, false)
  }
  for (const bad of [undefined, -1, '0']) {
    const { state, calls, second } = calendarSwitchFixture()
    state.events[1].version = bad
    const snapshot = JSON.stringify(state.editForm)
    state.openEdit(second); assert.equal(state.eventSwitchVisible, false); assert.equal(JSON.stringify(state.editForm), snapshot)
    assert.equal(calls.includes('saved'), false)
  }
})

test('calendar route adoption, owner watcher, loss of editable state and unmount invalidate the actual local switch intent', () => {
  // The existing VM fixture does not simulate reactivity. Invoke the actual
  // hooks/watch handlers explicitly; this is not ordinary identity UI proof.
  for (const transition of ['route', 'owner', 'locked', 'unmount']) {
    const { state, calls, definition, second } = calendarSwitchFixture()
    state.openEdit(second); assert.equal(state.eventSwitchVisible, true)
    if (transition === 'route') state.applyRouteSelection('5', 'events')
    else if (transition === 'owner') {
      state.academicFlow = { identity: () => 'changed owner' }
      definition.watch.eventSwitchContextKey.handler.call(state)
    } else if (transition === 'locked') {
      state.terms[0].status = 'PUBLISHED'
      definition.watch.canEditEvents.handler.call(state, false)
    } else definition.beforeUnmount.call(state)
    assert.equal(state.eventSwitchVisible, false); assert.equal(state.pendingEventSwitch, null)
    const snapshot = JSON.stringify(state.editForm)
    state.confirmEventSwitch(); assert.equal(JSON.stringify(state.editForm), snapshot); assert.equal(calls.includes('saved'), false)
  }
})

test('a failed calendar save keeps its actual error and invalid draft through another-event cancellation', async () => {
  const { state, calls, second } = calendarSwitchFixture({ updateCalendarEvent: async () => ({ code: 422001, message: '日期需在学期起止范围内' }) })
  state.updateEventField('edit', 'startDate', '2028-01-31')
  const snapshot = JSON.stringify(state.editForm), baseline = state.editBaseline
  await state.submitEdit()
  assert.equal(state.editError, '日期需在学期起止范围内'); assert.equal(JSON.stringify(state.editForm), snapshot)
  assert.equal(state.editBaseline, baseline); assert.equal(calls.includes('saved'), false)
  state.editVisible = false; state.openEdit(second); assert.equal(state.eventSwitchVisible, true)
  state.cancelEventSwitch(); assert.equal(state.editVisible, true); assert.equal(JSON.stringify(state.editForm), snapshot)
  assert.equal(state.editError, '日期需在学期起止范围内'); assert.equal(state.editBaseline, baseline)
  assert.equal(calls.includes('saved'), false)
})

// Actual Calendar/Month/shared-state contract. Transport errors are declared
// client-shaped inputs through the unchanged API adapter, not live HTTP faults.
import { createRequire as calTypedCreateRequire } from 'node:module'
import { setImmediate as calTypedSetImmediate } from 'node:timers'
import { normalizeUiError as calTypedNormalize } from '../src/utils/presentationSafety.js'
import { academicIdentity as calTypedIdentity } from '../src/modules/academicAffairs/academicFlowContext.js'
import { academicStatusLabel as calTypedStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'
import { SCHEDULE_BATCH_STATUS as calTypedBatchStatus } from '../src/modules/academicAffairs/constants/teaching.js'
import * as calTypedDialog from '../src/services/systemDialog.js'
const calTypedRequire = calTypedCreateRequire(import.meta.url)
const calTypedVue = calTypedRequire('vue')
const { parse: calTypedParse, compileTemplate: calTypedCompileTemplate } = calTypedRequire('@vue/compiler-sfc')
const calTypedRead = relative => readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')
function calTypedCompile(relative, scope = {}) {
  const { descriptor, errors } = calTypedParse(calTypedRead(relative), { filename: relative }); assert.deepEqual(errors, [])
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'const component =')
  const actual = new Function(...Object.keys(scope), `${script}\nreturn component`)(...Object.values(scope))
  const result = calTypedCompileTemplate({ source: descriptor.template.content, filename: relative, id: relative, compilerOptions: { mode: 'function' } }); assert.deepEqual(result.errors, [])
  actual.render = new Function('Vue', result.code)(calTypedVue)
  return actual
}
const calTypedNode = (type, value = '') => ({ type, tagName: type.toUpperCase(), value, props: {}, children: [], parent: null, listeners: {}, addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn) }, removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn) } })
const calTypedWalk = node => [node, ...node.children.flatMap(calTypedWalk)]
const calTypedText = node => node.type === '#comment' ? '' : node.value + node.children.map(calTypedText).join('')
const calTypedTick = async () => { await new Promise(resolve => calTypedSetImmediate(resolve)); await calTypedVue.nextTick() }
const calTypedClasses = (nodes, name) => nodes.filter(node => String(node.props.class || '').split(/\s+/).includes(name))
const calTypedVisual = name => ({ name, inheritAttrs: false, setup(_props, { slots }) { return () => calTypedVue.h('section', {}, [slots.actions?.(), slots.default?.()]) } })
async function calTypedFixture(t, { status, code, bizCode, message, traceId, details = null, rawTransportError = null }) {
  const previous = Object.fromEntries(['window', 'document', 'sessionStorage'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const body = calTypedNode('body'), requests = [], catalogResponses = [], currentResponses = [], responses = [], errors = [], warnings = []
  const prohibited = () => { throw new Error('该只读校历状态夹具禁止业务写入、发布、复制、归档、预览或其他API') }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body } })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: { getItem: () => null, setItem: prohibited, removeItem: prohibited } })
  let app, stopped = false
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } await calTypedTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(calTypedDialog.systemDialogState.visible, false) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
  })
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const ctx = calTypedVue.reactive({ ctxKey: 'DECLARED_CALENDAR_READ_SCOPE', permissionPatterns: ['academicAffairs.calendar.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 })
  assert.equal(matchPermission(ctx.permissionPatterns, 'academicAffairs.calendar.manage'), false)
  // Established independent DRAFT101 grammar; no live PUBLISHED row is changed.
  const termId = '101'
  const catalogDraft = { termId, yearCode: '2027-2028', termNo: 1, termName: '声明独立校历草稿学期101', startDate: '2027-09-01T00:00:00', endDate: '2028-01-31T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: false, status: 'DRAFT' }
  const catalogCurrent = { termId: '1', yearCode: '2025-2026', termNo: 2, termName: '声明当前学期1', startDate: '2026-02-01T00:00:00', endDate: '2026-06-30T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: true, status: 'PUBLISHED' }
  const catalog = [catalogCurrent, catalogDraft], currentDTO = { termId: '1', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
  const payload = { code, bizCode, message, traceId, details }, normalized = calTypedNormalize(payload)
  if (rawTransportError) {
    assert.equal(rawTransportError instanceof TypeError, true); assert.equal(rawTransportError.message, 'Failed to fetch')
    for (const key of ['httpStatus', 'status', 'code', 'biz', 'bizCode', 'traceId']) assert.equal(Object.hasOwn(rawTransportError, key), false)
  }
  const transportError = rawTransportError ?? Object.assign(new Error(normalized.userMessage), { biz: true, httpStatus: status, code, bizCode, details, traceId, rawDeveloperDetail: normalized.rawDeveloperDetail })
  const counts = { catalog: 0, current: 0, calendar: 0 }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    requests.push({ path, method: options.method || 'GET', params: options.params ?? null }); assert.ok(requests.length <= 4)
    if (path === '/academic-affairs/terms') {
      assert.equal(++counts.catalog, 1); assert.deepEqual(options.params, { resolveValue: undefined, keyword: '', page: 1, pageSize: 100 })
      return { items: structuredClone(catalog), total: 2, page: 1, pageSize: 100 }
    }
    if (path === '/academic-affairs/terms/current') { assert.equal(++counts.current, 1); assert.equal(options.params, undefined); return structuredClone(currentDTO) }
    assert.equal(path, `/academic-affairs/terms/${termId}/calendar`); assert.deepEqual(options.params, {})
    assert.ok(++counts.calendar <= 2)
    if (counts.calendar === 1) throw transportError
    return { items: [] }
  }
  const apiSource = calTypedRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const modules = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn { academicAffairsApi, academicAffairsOrgApi, academicAffairsLabApi, academicAffairsEquipmentApi, academicAffairsExamApi, academicAffairsSelectionApi, academicAffairsMakeupApi, academicAffairsArchiveApi }`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const productionApi = modules.academicAffairsApi
  const api = { ...productionApi,
    getCurrentTerm() { return productionApi.getCurrentTerm().then(result => { currentResponses.push(structuredClone(result)); return result }) },
    getCalendar(id, type) { assert.equal(String(id), termId); assert.equal(type, undefined); return productionApi.getCalendar(id, type).then(result => { responses.push(structuredClone(result)); return result }) }
  }
  const pickerSource = calTypedRead('modules/academicAffairs/pickerAdapters.js').replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '').replace(/^export (async function|function|const) /gm, '$1 ')
  const pickerBindings = { ...modules, academicAffairsApi: api, academicStatusLabel: calTypedStatusLabel, SCHEDULE_BATCH_STATUS: calTypedBatchStatus }
  const actualCatalog = new Function(...Object.keys(pickerBindings), `${pickerSource}\nreturn loadAcademicTermCatalog`)(...Object.values(pickerBindings))
  const loadCatalog = (...args) => actualCatalog(...args).then(rows => { catalogResponses.push(structuredClone(rows)); return rows })
  const Global = calTypedCompile('components/common/AppGlobalState.vue', { normalizeUiError: calTypedNormalize })
  const ErrorState = calTypedCompile('components/business/ErrorState.vue', { AppGlobalState: Global, normalizeUiError: calTypedNormalize })
  const Loading = calTypedCompile('components/business/LoadingState.vue', { AppGlobalState: Global }), Empty = calTypedCompile('components/business/EmptyState.vue', { AppGlobalState: Global })
  const Button = calTypedCompile('components/ui/AppButton.vue'), Drawer = calTypedCompile('components/ui/AppDrawer.vue')
  const Month = calTypedCompile('modules/academicAffairs/components/AaCalendarMonth.vue', { ErrorState, LoadingState: Loading, AppButton: Button })
  const Calendar = calTypedCompile('modules/academicAffairs/views/AaCalendarView.vue', {
    ModulePageShell: calTypedVisual('DeclaredCalendarShell'), DataTable: calTypedVisual('DeclaredUnrelatedEmptyCalendarRows'), StatusTag: calTypedVisual('DeclaredUnusedStatus'), LoadingState: Loading, ErrorState, EmptyState: Empty,
    AppButton: Button, AppDrawer: Drawer, AppSectionCard: calTypedVisual('DeclaredCalendarListCard'), AppSelect: calTypedVisual('DeclaredUnopenedEventType'), AppTextInput: calTypedVisual('DeclaredUnopenedRemark'), AppFormItem: calTypedVisual('DeclaredUnopenedForm'), AppDatePicker: calTypedVisual('DeclaredUnopenedEventDate'), AppTermEntityPicker: calTypedVisual('DeclaredUnopenedTermPicker'), AppConfirmDialog: calTypedVisual('DeclaredUnopenedObjectDialog'), AppInlineAlert: calTypedVisual('DeclaredUnrelatedAuthorityHint'),
    AaCalendarCopyPanel: calTypedVisual('DeclaredUnopenedCopyPanel'), AaCalendarMonth: Month, AaCalendarArchivePanel: calTypedVisual('DeclaredUnopenedArchivePanel'), academicAffairsApi: api, academicAffairsTermDetailApi: { get: prohibited }, loadAcademicTermCatalog: loadCatalog,
    toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission, currentUserFromToken: () => claims, systemConfirm: calTypedDialog.systemConfirm
  })
  const renderer = calTypedVue.createRenderer({ querySelector(selector) { assert.equal(selector, 'body'); return document.body }, createElement: type => calTypedNode(type), createText: value => calTypedNode('#text', value), createComment: value => calTypedNode('#comment', value), setText(node, value) { node.value = value }, setElementText(node, value) { node.value = value; node.children = [] }, parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null, patchProp(node, key, _old, value) { node.props[key] = value }, insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(node); else parent.children.splice(i, 0, node) }, remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } } })
  const root = calTypedNode('root'); app = renderer.createApp({ render: () => calTypedVue.h(Calendar, { ctx }) })
  app.provide('academicFlow', { identity: () => calTypedIdentity(claims, ctx), restorePosition() {} })
  app.config.globalProperties.$route = calTypedVue.reactive({ path: '/admin/academic-affairs/calendar', fullPath: '/admin/academic-affairs/calendar?termId=101&tab=events', query: { termId, tab: 'events' } })
  app.config.globalProperties.$router = { push: prohibited, replace: prohibited, back: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  app.mount(root)
  for (let i = 0; i < 8; i++) { await calTypedTick(); if (counts.calendar === 1 && responses.length === 1 && !calTypedClasses(calTypedWalk(root), 'ags-loading').length) break }
  assert.deepEqual(counts, { catalog: 1, current: 1, calendar: 1 }); assert.equal(requests.length, 3)
  assert.deepEqual(catalogResponses, [catalog]); assert.deepEqual(currentResponses, [{ code: 0, data: currentDTO, message: 'ok' }])
  if (rawTransportError) assert.deepEqual(responses, [{ code: 503001, data: null, message: 'Failed to fetch' }])
  else assert.deepEqual(responses, [{ code, data: null, message: normalized.userMessage, bizCode, details, httpStatus: status, traceId }])
  const months = calTypedClasses(calTypedWalk(root), 'acm-calendar'); assert.equal(months.length, 1)
  const month = months[0]
  const nodes = outlet => outlet === 'month' ? calTypedWalk(month) : calTypedWalk(root).filter(node => !new Set(calTypedWalk(month)).has(node))
  const classes = (outlet, name) => calTypedClasses(nodes(outlet), name)
  const buttons = (outlet, label) => nodes(outlet).filter(node => node.type === 'button' && calTypedText(node) === label)
  const assertBoth = state => {
    for (const outlet of ['month', 'list']) {
      assert.equal(classes(outlet, `ags-${state}`).length, 1)
      for (const other of ['error', 'forbidden', 'loading', 'empty'].filter(value => value !== state)) assert.equal(classes(outlet, `ags-${other}`).length, 0)
    }
  }
  const support = () => {
    for (const outlet of ['month', 'list']) {
      const codes = classes(outlet, 'ags-code'); assert.equal(codes.length, 1); assert.equal(calTypedText(codes[0]), `实施人员使用错误码：${traceId}`)
      const descriptions = classes(outlet, 'ags-desc'); assert.equal(descriptions.length, 1)
      if (status === 404 && bizCode === 'RECORD_NOT_FOUND') assert.equal(calTypedText(descriptions[0]), '记录不存在或已被删除')
      else assert.ok(!calTypedText(descriptions[0]).includes(traceId), '技术编号保留在实施人员折叠区')
    }
  }
  const retry = async outlet => {
    const candidates = buttons(outlet, '重试'); assert.equal(candidates.length, 1); assert.equal(!!candidates[0].props.disabled, false)
    const handlers = candidates[0].props.onClick; assert.ok(handlers); const event = { type: 'click', target: candidates[0], currentTarget: candidates[0] }
    for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event)
    await calTypedTick(); assert.deepEqual(counts, { catalog: 1, current: 1, calendar: 2 }); assert.equal(requests.length, 4)
    assert.deepEqual(responses[1], { code: 0, data: [], message: 'ok' }); assert.deepEqual(catalogResponses, [catalog]); assert.deepEqual(currentResponses, [{ code: 0, data: currentDTO, message: 'ok' }])
    assert.equal(calTypedClasses(calTypedWalk(root), 'ags-error').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-forbidden').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-loading').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-empty').length, 1)
    assert.equal(classes('month', 'acm-days').length, 1); assert.deepEqual(errors, []); assert.deepEqual(warnings, [])
  }
  assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(calTypedDialog.systemDialogState.visible, false)
  return { root, requests, responses, classes, buttons, assertBoth, support, retry }
}

test('calendar typed HTTP500 overrides stale permission metadata in both actual error outlets and Month public retry recovers', async t => {
  const f = await calTypedFixture(t, { status: 500, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_CALENDAR_FAILURE_500' })
  f.assertBoth('error'); f.support()
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('操作未完成，请稍后重试')) }
  await f.retry('month')
})

test('calendar typed HTTP403 renders both actual forbidden outlets without ordinary retry or permission mutation', async t => {
  const f = await calTypedFixture(t, { status: 403, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_CALENDAR_FORBIDDEN' })
  f.assertBoth('forbidden')
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 0); assert.equal(f.buttons(outlet, '返回').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('原因：不在授权范围内。建议：切换身份或联系管理员开通权限')) }
  assert.equal(f.requests.length, 3)
})

test('calendar typed HTTP404 preserves two safe record-not-found errors instead of healthy empty calendar data', async t => {
  const f = await calTypedFixture(t, { status: 404, code: 404001, bizCode: 'RECORD_NOT_FOUND', message: '读取失败', traceId: 'DECLARED_CALENDAR_NOT_FOUND' })
  f.assertBoth('error'); f.support()
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('记录不存在或已被删除')); assert.equal(f.classes(outlet, 'acm-days').length, 0) }
  assert.equal(f.requests.length, 3)
})

test('calendar technical HTTP500 keeps details private in both actual outlets and list public retry recovers the Month grid', async t => {
  const details = { sql: 'SELECT value FROM t_declared_private', stack: 'Traceback /srv/declared.py' }
  const f = await calTypedFixture(t, { status: 500, code: 500001, bizCode: 'INTERNAL_ERROR', message: 'SQLSTATE 42S02 SELECT value FROM t_declared_private /srv/declared.py', traceId: 'DECLARED_CALENDAR_TECH_500', details })
  f.assertBoth('error'); f.support(); assert.deepEqual(f.responses[0].details, details)
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('操作未完成，请稍后重试')) }
  for (const raw of ['SQLSTATE', 'SELECT value', 't_declared_private', 'Traceback', '/srv/declared.py']) assert.equal(calTypedText(f.root).includes(raw), false)
  await f.retry('list')
})


test('calendar raw fetch TypeError without HTTP metadata remains retryable in both real outlets and public retry restores the empty read', async t => {
  // A raw non-biz transport error goes through the actual API fallback. It has
  // no server response/status or trace; adapter code503001 is not HTTP503.
  const failure = new TypeError('Failed to fetch')
  const f = await calTypedFixture(t, { code: 503001, message: 'Failed to fetch', rawTransportError: failure })
  assert.deepEqual(f.responses[0], { code: 503001, data: null, message: 'Failed to fetch' })
  for (const key of ['httpStatus', 'status', 'bizCode', 'details', 'traceId']) assert.equal(Object.hasOwn(f.responses[0], key), false)
  f.assertBoth('error')
  for (const outlet of ['month', 'list']) {
    assert.equal(f.classes(outlet, 'ags-offline').length, 0); assert.equal(f.classes(outlet, 'ags-code').length, 0); assert.equal(f.buttons(outlet, '重试').length, 1)
    assert.equal(calTypedText(f.classes(outlet, 'ags-desc')[0]), '系统暂时无法完成该操作，请稍后重试')
  }
  assert.equal(calTypedText(f.root).includes('Failed to fetch'), false); assert.equal(f.requests.length, 3)
  await f.retry('month')
})


// TermWeeks has its own canonical catalog/current/weeks contract and actual Month.
// Independent declared DRAFT101, not a live status or permission mutation.
async function weeksErrorFixture(t, { status, code, bizCode, message, traceId, details = null }) {
  const previous = Object.fromEntries(['window', 'document', 'sessionStorage'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const body = calTypedNode('body'), requests = [], catalogResponses = [], currentResponses = [], responses = [], errors = [], warnings = []
  const prohibited = () => { throw new Error('该只读校历状态夹具禁止业务写入、发布、复制、归档、预览或其他API') }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body } })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: { getItem: () => null, setItem: prohibited, removeItem: prohibited } })
  let app, stopped = false
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } await calTypedTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(calTypedDialog.systemDialogState.visible, false) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
  })
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const ctx = calTypedVue.reactive({ ctxKey: 'DECLARED_TERM_WEEKS_READ_SCOPE', permissionPatterns: ['academicAffairs.term.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 })
  assert.equal(matchPermission(ctx.permissionPatterns, 'academicAffairs.term.manage'), false)
  // Established independent DRAFT101 grammar; no live PUBLISHED row is changed.
  const termId = '101'
  const catalogDraft = { termId, yearCode: '2027-2028', termNo: 1, termName: '声明独立校历草稿学期101', startDate: '2027-09-01T00:00:00', endDate: '2028-01-31T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: false, status: 'DRAFT' }
  const catalogCurrent = { termId: '1', yearCode: '2025-2026', termNo: 2, termName: '声明当前学期1', startDate: '2026-02-01T00:00:00', endDate: '2026-06-30T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: true, status: 'PUBLISHED' }
  const weeksDTO = [{"weekNo":1,"startDate":"2027-09-01","endDate":"2027-09-07","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":2,"startDate":"2027-09-08","endDate":"2027-09-14","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":3,"startDate":"2027-09-15","endDate":"2027-09-21","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":4,"startDate":"2027-09-22","endDate":"2027-09-28","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":5,"startDate":"2027-09-29","endDate":"2027-10-05","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":6,"startDate":"2027-10-06","endDate":"2027-10-12","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":7,"startDate":"2027-10-13","endDate":"2027-10-19","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":8,"startDate":"2027-10-20","endDate":"2027-10-26","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":9,"startDate":"2027-10-27","endDate":"2027-11-02","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":10,"startDate":"2027-11-03","endDate":"2027-11-09","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":11,"startDate":"2027-11-10","endDate":"2027-11-16","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":12,"startDate":"2027-11-17","endDate":"2027-11-23","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":13,"startDate":"2027-11-24","endDate":"2027-11-30","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":14,"startDate":"2027-12-01","endDate":"2027-12-07","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":15,"startDate":"2027-12-08","endDate":"2027-12-14","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":16,"startDate":"2027-12-15","endDate":"2027-12-21","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":17,"startDate":"2027-12-22","endDate":"2027-12-28","weekType":"TEACHING","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":18,"startDate":"2027-12-29","endDate":"2028-01-04","weekType":"EXAM","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":19,"startDate":"2028-01-05","endDate":"2028-01-11","weekType":"EXAM","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false},{"weekNo":20,"startDate":"2028-01-12","endDate":"2028-01-18","weekType":"EXAM","remark":"","teachingDayCount":5,"exceptionSummary":"无例外安排","isCurrent":false}]
  const catalog = [catalogCurrent, catalogDraft], currentDTO = { termId: '1', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
  const payload = { code, bizCode, message, traceId, details }, normalized = calTypedNormalize(payload)
  const transportError = Object.assign(new Error(normalized.userMessage), { biz: true, httpStatus: status, code, bizCode, details, traceId, rawDeveloperDetail: normalized.rawDeveloperDetail })
  const counts = { catalog: 0, current: 0, weeks: 0 }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    requests.push({ path, method: options.method || 'GET', params: options.params ?? null }); assert.ok(requests.length <= 4)
    if (path === '/academic-affairs/terms') {
      assert.equal(++counts.catalog, 1); assert.deepEqual(options.params, { resolveValue: undefined, keyword: '', page: 1, pageSize: 100 })
      return { items: structuredClone(catalog), total: 2, page: 1, pageSize: 100 }
    }
    if (path === '/academic-affairs/terms/current') { assert.equal(++counts.current, 1); assert.equal(options.params, undefined); return structuredClone(currentDTO) }
    assert.equal(path, `/academic-affairs/terms/${termId}/weeks`); assert.equal(options.params, undefined)
    assert.ok(++counts.weeks <= 2)
    if (counts.weeks === 1) throw transportError
    return { items: structuredClone(weeksDTO) }
  }
  const apiSource = calTypedRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const modules = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn { academicAffairsApi, academicAffairsOrgApi, academicAffairsLabApi, academicAffairsEquipmentApi, academicAffairsExamApi, academicAffairsSelectionApi, academicAffairsMakeupApi, academicAffairsArchiveApi }`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const productionApi = modules.academicAffairsApi
  const api = { ...productionApi,
    getCurrentTerm() { return productionApi.getCurrentTerm().then(result => { currentResponses.push(structuredClone(result)); return result }) },
    getTermWeeks(id) { assert.equal(String(id), termId); return productionApi.getTermWeeks(id).then(result => { responses.push(structuredClone(result)); return result }) }
  }
  const pickerSource = calTypedRead('modules/academicAffairs/pickerAdapters.js').replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '').replace(/^export (async function|function|const) /gm, '$1 ')
  const pickerBindings = { ...modules, academicAffairsApi: api, academicStatusLabel: calTypedStatusLabel, SCHEDULE_BATCH_STATUS: calTypedBatchStatus }
  const actualCatalog = new Function(...Object.keys(pickerBindings), `${pickerSource}\nreturn loadAcademicTermCatalog`)(...Object.values(pickerBindings))
  const loadCatalog = (...args) => actualCatalog(...args).then(rows => { catalogResponses.push(structuredClone(rows)); return rows })
  const Global = calTypedCompile('components/common/AppGlobalState.vue', { normalizeUiError: calTypedNormalize })
  const ErrorState = calTypedCompile('components/business/ErrorState.vue', { AppGlobalState: Global, normalizeUiError: calTypedNormalize })
  const Loading = calTypedCompile('components/business/LoadingState.vue', { AppGlobalState: Global }), Empty = calTypedCompile('components/business/EmptyState.vue', { AppGlobalState: Global })
  const Button = calTypedCompile('components/ui/AppButton.vue'), Drawer = calTypedCompile('components/ui/AppDrawer.vue')
  const Month = calTypedCompile('modules/academicAffairs/components/AaCalendarMonth.vue', { ErrorState, LoadingState: Loading, AppButton: Button })
  const Weeks = calTypedCompile('modules/academicAffairs/views/AaTermWeeksView.vue', {
    ModulePageShell: calTypedVisual('DeclaredTermWeeksShell'), DataTable: calTypedVisual('DeclaredUnrelatedEmptyCalendarRows'), StatusTag: calTypedVisual('DeclaredUnusedStatus'), AppStatusTag: calTypedVisual('DeclaredUnusedWeekType'), LoadingState: Loading, ErrorState, EmptyState: Empty,
    AppButton: Button, AppDrawer: Drawer, AppSectionCard: calTypedVisual('DeclaredTermWeeksListCard'), AppSelect: calTypedVisual('DeclaredUnopenedEventType'), AppTextInput: calTypedVisual('DeclaredUnopenedRemark'), AppFormItem: calTypedVisual('DeclaredUnopenedForm'), AppDatePicker: calTypedVisual('DeclaredUnopenedEventDate'), AppTermEntityPicker: calTypedVisual('DeclaredUnopenedTermPicker'), AppConfirmDialog: calTypedVisual('DeclaredUnopenedObjectDialog'), AppInlineAlert: calTypedVisual('DeclaredUnrelatedAuthorityHint'),
    AaCalendarCopyPanel: calTypedVisual('DeclaredUnopenedCopyPanel'), AaCalendarMonth: Month, AaCalendarArchivePanel: calTypedVisual('DeclaredUnopenedArchivePanel'), academicAffairsApi: api, academicAffairsTermDetailApi: { get: prohibited }, loadAcademicTermCatalog: loadCatalog,
    toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission, currentUserFromToken: () => claims, systemConfirm: calTypedDialog.systemConfirm
  })
  const renderer = calTypedVue.createRenderer({ querySelector(selector) { assert.equal(selector, 'body'); return document.body }, createElement: type => calTypedNode(type), createText: value => calTypedNode('#text', value), createComment: value => calTypedNode('#comment', value), setText(node, value) { node.value = value }, setElementText(node, value) { node.value = value; node.children = [] }, parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null, patchProp(node, key, _old, value) { node.props[key] = value }, insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(node); else parent.children.splice(i, 0, node) }, remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } } })
  const root = calTypedNode('root'); app = renderer.createApp({ render: () => calTypedVue.h(Weeks, { ctx }) })
  app.provide('academicFlow', { identity: () => calTypedIdentity(claims, ctx), restorePosition() {} })
  app.config.globalProperties.$route = calTypedVue.reactive({ path: '/admin/academic-affairs/terms/weeks', fullPath: '/admin/academic-affairs/terms/weeks?termId=101', query: { termId } })
  app.config.globalProperties.$router = { push: prohibited, replace: prohibited, back: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  app.mount(root)
  for (let i = 0; i < 8; i++) { await calTypedTick(); if (counts.weeks === 1 && responses.length === 1 && !calTypedClasses(calTypedWalk(root), 'ags-loading').length) break }
  assert.deepEqual(counts, { catalog: 1, current: 1, weeks: 1 }); assert.equal(requests.length, 3)
  assert.deepEqual(catalogResponses, [catalog]); assert.deepEqual(currentResponses, [{ code: 0, data: currentDTO, message: 'ok' }])
  assert.deepEqual(responses, [{ code, data: null, message: normalized.userMessage, bizCode, details, httpStatus: status, traceId }])
  const months = calTypedClasses(calTypedWalk(root), 'acm-calendar'); assert.equal(months.length, 1)
  const month = months[0]
  const nodes = outlet => outlet === 'month' ? calTypedWalk(month) : calTypedWalk(root).filter(node => !new Set(calTypedWalk(month)).has(node))
  const classes = (outlet, name) => calTypedClasses(nodes(outlet), name)
  const buttons = (outlet, label) => nodes(outlet).filter(node => node.type === 'button' && calTypedText(node) === label)
  const assertBoth = state => {
    for (const outlet of ['month', 'list']) {
      assert.equal(classes(outlet, `ags-${state}`).length, 1)
      for (const other of ['error', 'forbidden', 'loading', 'empty'].filter(value => value !== state)) assert.equal(classes(outlet, `ags-${other}`).length, 0)
    }
  }
  const support = () => {
    for (const outlet of ['month', 'list']) {
      const codes = classes(outlet, 'ags-code'); assert.equal(codes.length, 1); assert.equal(calTypedText(codes[0]), `实施人员使用错误码：${traceId}`)
      const descriptions = classes(outlet, 'ags-desc'); assert.equal(descriptions.length, 1)
      if (status === 404 && bizCode === 'RECORD_NOT_FOUND') assert.equal(calTypedText(descriptions[0]), '记录不存在或已被删除')
      else assert.ok(!calTypedText(descriptions[0]).includes(traceId), '技术编号保留在实施人员折叠区')
    }
  }
  const retry = async outlet => {
    const candidates = buttons(outlet, '重试'); assert.equal(candidates.length, 1); assert.equal(!!candidates[0].props.disabled, false)
    const handlers = candidates[0].props.onClick; assert.ok(handlers); const event = { type: 'click', target: candidates[0], currentTarget: candidates[0] }
    for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event)
    await calTypedTick(); assert.deepEqual(counts, { catalog: 1, current: 1, weeks: 2 }); assert.equal(requests.length, 4)
    assert.deepEqual(responses[1], { code: 0, data: weeksDTO, message: 'ok' }); assert.equal(responses[1].data.length, 20); assert.deepEqual(catalogResponses, [catalog]); assert.deepEqual(currentResponses, [{ code: 0, data: currentDTO, message: 'ok' }])
    assert.equal(calTypedClasses(calTypedWalk(root), 'ags-error').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-forbidden').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-loading').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-empty').length, 0)
    assert.equal(classes('month', 'acm-days').length, 1); assert.ok(calTypedText(month).includes('第 1 周')); assert.deepEqual(errors, []); assert.deepEqual(warnings, [])
  }
  assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(calTypedDialog.systemDialogState.visible, false)
  return { root, requests, responses, classes, buttons, assertBoth, support, retry }
}

test('term weeks typed HTTP500 overrides stale permission metadata in both actual error outlets and Month public retry recovers', async t => {
  const f = await weeksErrorFixture(t, { status: 500, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_TERM_WEEKS_FAILURE_500' })
  f.assertBoth('error'); f.support()
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('操作未完成，请稍后重试')) }
  await f.retry('month')
})

test('term weeks typed HTTP403 renders both actual forbidden outlets without ordinary retry or permission mutation', async t => {
  const f = await weeksErrorFixture(t, { status: 403, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_TERM_WEEKS_FORBIDDEN' })
  f.assertBoth('forbidden')
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 0); assert.equal(f.buttons(outlet, '返回').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('原因：不在授权范围内。建议：切换身份或联系管理员开通权限')) }
  assert.equal(f.requests.length, 3)
})

test('term weeks typed HTTP404 preserves two safe record-not-found errors instead of healthy empty weeks data', async t => {
  const f = await weeksErrorFixture(t, { status: 404, code: 404001, bizCode: 'RECORD_NOT_FOUND', message: '读取失败', traceId: 'DECLARED_TERM_WEEKS_NOT_FOUND' })
  f.assertBoth('error'); f.support()
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('记录不存在或已被删除')); assert.equal(f.classes(outlet, 'acm-days').length, 0) }
  assert.equal(f.requests.length, 3)
})

test('term weeks technical HTTP500 keeps details private in both actual outlets and list public retry recovers the Month grid', async t => {
  const details = { sql: 'SELECT value FROM t_declared_private', stack: 'Traceback /srv/declared.py' }
  const f = await weeksErrorFixture(t, { status: 500, code: 500001, bizCode: 'INTERNAL_ERROR', message: 'SQLSTATE 42S02 SELECT value FROM t_declared_private /srv/declared.py', traceId: 'DECLARED_TERM_WEEKS_TECH_500', details })
  f.assertBoth('error'); f.support(); assert.deepEqual(f.responses[0].details, details)
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('操作未完成，请稍后重试')) }
  for (const raw of ['SQLSTATE', 'SELECT value', 't_declared_private', 'Traceback', '/srv/declared.py']) assert.equal(calTypedText(f.root).includes(raw), false)
  await f.retry('list')
})


// Calendar weekCalendar is a distinct endpoint from events and TermWeeks.
// Full actual Calendar/Month/API/picker; only declared read-only DRAFT101 inputs.
async function weekCalendarTypedFixture(t, { status, code, bizCode, message, traceId, details = null }) {
  const previous = Object.fromEntries(['window', 'document', 'sessionStorage'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const body = calTypedNode('body'), requests = [], catalogResponses = [], currentResponses = [], responses = [], errors = [], warnings = []
  const prohibited = () => { throw new Error('该只读校历状态夹具禁止业务写入、发布、复制、归档、预览或其他API') }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: {} })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { body } })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: { getItem: () => null, setItem: prohibited, removeItem: prohibited } })
  let app, stopped = false
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } await calTypedTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(calTypedDialog.systemDialogState.visible, false) }
    finally { for (const [key, descriptor] of Object.entries(previous)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
  })
  const claims = { tenantId: 'DECLARED_TENANT', userId: 'DECLARED_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_ROLE' }
  const ctx = calTypedVue.reactive({ ctxKey: 'DECLARED_WEEK_CALENDAR_READ_SCOPE', permissionPatterns: ['academicAffairs.calendar.view'], currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务管理员' }, dataScope: { scope: 'SCHOOL', scopeName: '声明学校范围' }, permissionVersion: 1, dataScopeVersion: 1 })
  assert.equal(matchPermission(ctx.permissionPatterns, 'academicAffairs.calendar.manage'), false)
  // Established independent DRAFT101 grammar; no live PUBLISHED row is changed.
  const termId = '101'
  const catalogDraft = { termId, yearCode: '2027-2028', termNo: 1, termName: '声明独立校历草稿学期101', startDate: '2027-09-01T00:00:00', endDate: '2028-01-31T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: false, status: 'DRAFT' }
  const catalogCurrent = { termId: '1', yearCode: '2025-2026', termNo: 2, termName: '声明当前学期1', startDate: '2026-02-01T00:00:00', endDate: '2026-06-30T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: true, status: 'PUBLISHED' }
  // Actual week-calendar object grammar; this is not the /weeks list DTO.
  const calendarWeeksDTO = [{"weekNo":1,"startDate":"2027-09-01","endDate":"2027-09-07","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":2,"startDate":"2027-09-08","endDate":"2027-09-14","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":3,"startDate":"2027-09-15","endDate":"2027-09-21","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":4,"startDate":"2027-09-22","endDate":"2027-09-28","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":5,"startDate":"2027-09-29","endDate":"2027-10-05","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":6,"startDate":"2027-10-06","endDate":"2027-10-12","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":7,"startDate":"2027-10-13","endDate":"2027-10-19","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":8,"startDate":"2027-10-20","endDate":"2027-10-26","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":9,"startDate":"2027-10-27","endDate":"2027-11-02","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":10,"startDate":"2027-11-03","endDate":"2027-11-09","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":11,"startDate":"2027-11-10","endDate":"2027-11-16","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":12,"startDate":"2027-11-17","endDate":"2027-11-23","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":13,"startDate":"2027-11-24","endDate":"2027-11-30","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":14,"startDate":"2027-12-01","endDate":"2027-12-07","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":15,"startDate":"2027-12-08","endDate":"2027-12-14","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":16,"startDate":"2027-12-15","endDate":"2027-12-21","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":17,"startDate":"2027-12-22","endDate":"2027-12-28","weekType":"TEACHING","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":18,"startDate":"2027-12-29","endDate":"2028-01-04","weekType":"EXAM","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":19,"startDate":"2028-01-05","endDate":"2028-01-11","weekType":"EXAM","remark":"","holidays":[],"swaps":[],"internships":[]},{"weekNo":20,"startDate":"2028-01-12","endDate":"2028-01-18","weekType":"EXAM","remark":"","holidays":[],"swaps":[],"internships":[]}]
  const weekCalendarDTO = { termId, termName: catalogDraft.termName, teachingWeeks: 20, examWeekStart: 18, weeks: calendarWeeksDTO }
  const catalog = [catalogCurrent, catalogDraft], currentDTO = { termId: '1', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
  const payload = { code, bizCode, message, traceId, details }, normalized = calTypedNormalize(payload)
  const transportError = Object.assign(new Error(normalized.userMessage), { biz: true, httpStatus: status, code, bizCode, details, traceId, rawDeveloperDetail: normalized.rawDeveloperDetail })
  const counts = { catalog: 0, current: 0, weekCalendar: 0 }
  const request = async (path, options = {}) => {
    assert.ok(!options.method || options.method === 'GET'); assert.equal(options.body, undefined)
    requests.push({ path, method: options.method || 'GET', params: options.params ?? null }); assert.ok(requests.length <= 4)
    if (path === '/academic-affairs/terms') {
      assert.equal(++counts.catalog, 1); assert.deepEqual(options.params, { resolveValue: undefined, keyword: '', page: 1, pageSize: 100 })
      return { items: structuredClone(catalog), total: 2, page: 1, pageSize: 100 }
    }
    if (path === '/academic-affairs/terms/current') { assert.equal(++counts.current, 1); assert.equal(options.params, undefined); return structuredClone(currentDTO) }
    assert.equal(path, `/academic-affairs/terms/${termId}/week-calendar`); assert.equal(options.params, undefined)
    assert.ok(++counts.weekCalendar <= 2)
    if (counts.weekCalendar === 1) throw transportError
    return structuredClone(weekCalendarDTO)
  }
  const apiSource = calTypedRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const modules = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn { academicAffairsApi, academicAffairsOrgApi, academicAffairsLabApi, academicAffairsEquipmentApi, academicAffairsExamApi, academicAffairsSelectionApi, academicAffairsMakeupApi, academicAffairsArchiveApi }`)(request, prohibited, prohibited, prohibited, () => claims, prohibited)
  const productionApi = modules.academicAffairsApi
  const api = { ...productionApi,
    getCurrentTerm() { return productionApi.getCurrentTerm().then(result => { currentResponses.push(structuredClone(result)); return result }) },
    getWeekCalendar(id) { assert.equal(String(id), termId); return productionApi.getWeekCalendar(id).then(result => { responses.push(structuredClone(result)); return result }) }
  }
  const pickerSource = calTypedRead('modules/academicAffairs/pickerAdapters.js').replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '').replace(/^export (async function|function|const) /gm, '$1 ')
  const pickerBindings = { ...modules, academicAffairsApi: api, academicStatusLabel: calTypedStatusLabel, SCHEDULE_BATCH_STATUS: calTypedBatchStatus }
  const actualCatalog = new Function(...Object.keys(pickerBindings), `${pickerSource}\nreturn loadAcademicTermCatalog`)(...Object.values(pickerBindings))
  const loadCatalog = (...args) => actualCatalog(...args).then(rows => { catalogResponses.push(structuredClone(rows)); return rows })
  const Global = calTypedCompile('components/common/AppGlobalState.vue', { normalizeUiError: calTypedNormalize })
  const ErrorState = calTypedCompile('components/business/ErrorState.vue', { AppGlobalState: Global, normalizeUiError: calTypedNormalize })
  const Loading = calTypedCompile('components/business/LoadingState.vue', { AppGlobalState: Global }), Empty = calTypedCompile('components/business/EmptyState.vue', { AppGlobalState: Global })
  const Button = calTypedCompile('components/ui/AppButton.vue'), Drawer = calTypedCompile('components/ui/AppDrawer.vue')
  const Month = calTypedCompile('modules/academicAffairs/components/AaCalendarMonth.vue', { ErrorState, LoadingState: Loading, AppButton: Button })
  const Calendar = calTypedCompile('modules/academicAffairs/views/AaCalendarView.vue', {
    ModulePageShell: calTypedVisual('DeclaredCalendarShell'), DataTable: calTypedVisual('DeclaredUnrelatedEmptyCalendarRows'), StatusTag: calTypedVisual('DeclaredUnusedStatus'), LoadingState: Loading, ErrorState, EmptyState: Empty,
    AppButton: Button, AppDrawer: Drawer, AppSectionCard: calTypedVisual('DeclaredCalendarListCard'), AppSelect: calTypedVisual('DeclaredUnopenedEventType'), AppTextInput: calTypedVisual('DeclaredUnopenedRemark'), AppFormItem: calTypedVisual('DeclaredUnopenedForm'), AppDatePicker: calTypedVisual('DeclaredUnopenedEventDate'), AppTermEntityPicker: calTypedVisual('DeclaredUnopenedTermPicker'), AppConfirmDialog: calTypedVisual('DeclaredUnopenedObjectDialog'), AppInlineAlert: calTypedVisual('DeclaredUnrelatedAuthorityHint'),
    AaCalendarCopyPanel: calTypedVisual('DeclaredUnopenedCopyPanel'), AaCalendarMonth: Month, AaCalendarArchivePanel: calTypedVisual('DeclaredUnopenedArchivePanel'), academicAffairsApi: api, academicAffairsTermDetailApi: { get: prohibited }, loadAcademicTermCatalog: loadCatalog,
    toast: { success: prohibited, error: prohibited, warning: prohibited }, matchPermission, currentUserFromToken: () => claims, systemConfirm: calTypedDialog.systemConfirm
  })
  const renderer = calTypedVue.createRenderer({ querySelector(selector) { assert.equal(selector, 'body'); return document.body }, createElement: type => calTypedNode(type), createText: value => calTypedNode('#text', value), createComment: value => calTypedNode('#comment', value), setText(node, value) { node.value = value }, setElementText(node, value) { node.value = value; node.children = [] }, parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null, patchProp(node, key, _old, value) { node.props[key] = value }, insert(node, parent, anchor = null) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(node); else parent.children.splice(i, 0, node) }, remove(node) { if (node.parent) { node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null } } })
  const root = calTypedNode('root'); app = renderer.createApp({ render: () => calTypedVue.h(Calendar, { ctx }) })
  app.provide('academicFlow', { identity: () => calTypedIdentity(claims, ctx), restorePosition() {} })
  app.config.globalProperties.$route = calTypedVue.reactive({ path: '/admin/academic-affairs/calendar', fullPath: '/admin/academic-affairs/calendar?termId=101&tab=weekCalendar', query: { termId, tab: 'weekCalendar' } })
  app.config.globalProperties.$router = { push: prohibited, replace: prohibited, back: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = warning => warnings.push(String(warning)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  app.mount(root)
  for (let i = 0; i < 8; i++) { await calTypedTick(); if (counts.weekCalendar === 1 && responses.length === 1 && !calTypedClasses(calTypedWalk(root), 'ags-loading').length) break }
  assert.deepEqual(counts, { catalog: 1, current: 1, weekCalendar: 1 }); assert.equal(requests.length, 3)
  assert.deepEqual(catalogResponses, [catalog]); assert.deepEqual(currentResponses, [{ code: 0, data: currentDTO, message: 'ok' }])
  assert.deepEqual(responses, [{ code, data: null, message: normalized.userMessage, bizCode, details, httpStatus: status, traceId }])
  const months = calTypedClasses(calTypedWalk(root), 'acm-calendar'); assert.equal(months.length, 1)
  const month = months[0]
  const nodes = outlet => outlet === 'month' ? calTypedWalk(month) : calTypedWalk(root).filter(node => !new Set(calTypedWalk(month)).has(node))
  const classes = (outlet, name) => calTypedClasses(nodes(outlet), name)
  assert.deepEqual([Month.props.error.type].flat().map(Type => Type.name), ['String', 'Object'])
  for (const outlet of ['month', 'list']) assert.equal(classes(outlet, 'ags-panel').length, 1)
  assert.equal(calTypedWalk(root).filter(node => node.type === 'button' && calTypedText(node) === '教学周日历' && node.props['aria-current'] === 'page').length, 1)
  const buttons = (outlet, label) => nodes(outlet).filter(node => node.type === 'button' && calTypedText(node) === label)
  const assertBoth = state => {
    for (const outlet of ['month', 'list']) {
      assert.equal(classes(outlet, `ags-${state}`).length, 1)
      for (const other of ['error', 'forbidden', 'loading', 'empty'].filter(value => value !== state)) assert.equal(classes(outlet, `ags-${other}`).length, 0)
    }
  }
  const support = () => {
    for (const outlet of ['month', 'list']) {
      const codes = classes(outlet, 'ags-code'); assert.equal(codes.length, 1); assert.equal(calTypedText(codes[0]), `实施人员使用错误码：${traceId}`)
      const descriptions = classes(outlet, 'ags-desc'); assert.equal(descriptions.length, 1)
      if (status === 404 && bizCode === 'RECORD_NOT_FOUND') assert.equal(calTypedText(descriptions[0]), '记录不存在或已被删除')
      else assert.equal(calTypedText(descriptions[0]), '操作未完成，请稍后重试')
    }
  }
  const retry = async outlet => {
    const candidates = buttons(outlet, '重试'); assert.equal(candidates.length, 1); assert.equal(!!candidates[0].props.disabled, false)
    const handlers = candidates[0].props.onClick; assert.ok(handlers); const event = { type: 'click', target: candidates[0], currentTarget: candidates[0] }
    for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(event)
    await calTypedTick(); assert.deepEqual(counts, { catalog: 1, current: 1, weekCalendar: 2 }); assert.equal(requests.length, 4)
    assert.deepEqual(responses[1], { code: 0, data: weekCalendarDTO, message: 'ok' }); assert.equal(responses[1].data.weeks.length, 20); assert.deepEqual(catalogResponses, [catalog]); assert.deepEqual(currentResponses, [{ code: 0, data: currentDTO, message: 'ok' }])
    assert.equal(calTypedClasses(calTypedWalk(root), 'ags-error').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-forbidden').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-loading').length, 0); assert.equal(calTypedClasses(calTypedWalk(root), 'ags-empty').length, 0)
    assert.equal(classes('month', 'acm-days').length, 1); assert.ok(calTypedText(month).includes('第 1 周'))
    const lists = calTypedClasses(calTypedWalk(root), 'aa-week-list'); assert.equal(lists.length, 1)
    const rows = lists[0].children.filter(node => node.type === 'li'); assert.equal(rows.length, 20)
    assert.ok(calTypedText(rows[0]).includes('第 1 周')); assert.ok(calTypedText(rows[19]).includes('第 20 周'))
    assert.deepEqual(errors, []); assert.deepEqual(warnings, [])
  }
  assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(calTypedDialog.systemDialogState.visible, false)
  return { root, requests, responses, classes, buttons, assertBoth, support, retry }
}

test('week calendar typed HTTP500 overrides stale permission metadata in both actual error outlets and Month public retry recovers', async t => {
  const f = await weekCalendarTypedFixture(t, { status: 500, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_WEEK_CALENDAR_FAILURE_500' })
  f.assertBoth('error'); f.support()
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('操作未完成，请稍后重试')) }
  await f.retry('month')
})

test('week calendar typed HTTP403 renders both actual forbidden outlets without ordinary retry or permission mutation', async t => {
  const f = await weekCalendarTypedFixture(t, { status: 403, code: 403003, bizCode: 'NO_PERMISSION', message: '读取失败', traceId: 'DECLARED_WEEK_CALENDAR_FORBIDDEN' })
  f.assertBoth('forbidden')
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 0); assert.equal(f.buttons(outlet, '返回').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('原因：不在授权范围内。建议：切换身份或联系管理员开通权限')) }
  assert.equal(f.requests.length, 3)
})

test('week calendar typed HTTP404 preserves two safe record-not-found errors instead of healthy empty week-calendar data', async t => {
  const f = await weekCalendarTypedFixture(t, { status: 404, code: 404001, bizCode: 'RECORD_NOT_FOUND', message: '读取失败', traceId: 'DECLARED_WEEK_CALENDAR_NOT_FOUND' })
  f.assertBoth('error'); f.support()
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('记录不存在或已被删除')); assert.equal(f.classes(outlet, 'acm-days').length, 0) }
  assert.equal(f.requests.length, 3)
})

test('week calendar technical HTTP500 keeps details private in both actual outlets and list public retry recovers the Month grid', async t => {
  const details = { sql: 'SELECT value FROM t_declared_private', stack: 'Traceback /srv/declared.py' }
  const f = await weekCalendarTypedFixture(t, { status: 500, code: 500001, bizCode: 'INTERNAL_ERROR', message: 'SQLSTATE 42S02 SELECT value FROM t_declared_private /srv/declared.py', traceId: 'DECLARED_WEEK_CALENDAR_TECH_500', details })
  f.assertBoth('error'); f.support(); assert.deepEqual(f.responses[0].details, details)
  for (const outlet of ['month', 'list']) { assert.equal(f.buttons(outlet, '重试').length, 1); assert.ok(calTypedText(f.classes(outlet, 'ags-desc')[0]).includes('操作未完成，请稍后重试')) }
  for (const raw of ['SQLSTATE', 'SELECT value', 't_declared_private', 'Traceback', '/srv/declared.py']) assert.equal(calTypedText(f.root).includes(raw), false)
  await f.retry('list')
})

// Original S0/A6 copy write outcomes: complete client/API/parent/child contract.
// Declared fetch fixtures are not real HTTP, backend-commit, auth or native proofs.
async function copyOutcomeFixture(t, { mode = 'healthy', failAt = 2, holdFailure = false } = {}) {
  const Vue = calTypedVue, { h, reactive, createRenderer } = Vue
  const previous = Object.fromEntries(['window', 'document', 'sessionStorage'].map(k => [k, Object.getOwnPropertyDescriptor(globalThis, k)]))
  const memory = new Map(), storage = { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, String(v)), removeItem: k => memory.delete(k) }
  const eventHost = { addEventListener() {}, removeEventListener() {} }
  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: { ...eventHost } })
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: { ...eventHost, body: calTypedNode('body') } })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, writable: true, value: storage })
  let app, stopped = false, vm, releaseFailure
  const errors = [], warnings = [], dtos = [], requests = [], toasts = [], mounts = [], unmounts = []
  t.after(async () => {
    try { if (app && !stopped) { app.unmount(); stopped = true } releaseFailure?.(); await calTypedTick(); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); assert.equal(calTypedDialog.systemDialogState.visible, false) }
    finally { for (const [k, d] of Object.entries(previous)) { if (d) Object.defineProperty(globalThis, k, d); else delete globalThis[k] } }
  })
  const prohibited = () => { throw new Error('Outside this declared calendar copy outcome contract') }
  const claims = { tenantId: 'DECLARED_COPY_TENANT', userId: 'DECLARED_COPY_STAFF', currentRoleCode: 'ACADEMIC_ADMIN', activeContextId: 'DECLARED_COPY_CONTEXT' }
  const makeCtx = key => ({ ctxKey: key, currentRole: { roleCode: 'ACADEMIC_ADMIN', roleName: '声明教务' }, dataScope: { scope: 'SCHOOL', scopeName: key }, permissionPatterns: ['academicAffairs.calendar.view', 'academicAffairs.calendar.manage', 'academicAffairs.term.view'] })
  const state = reactive({ ctx: makeCtx('A') })
  const source = { termId: '1', yearCode: '2025-2026', termNo: 2, termName: '声明来源', startDate: '2026-02-01T00:00:00', endDate: '2026-06-30T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: true, status: 'PUBLISHED' }
  const target = { termId: '101', yearCode: '2027-2028', termNo: 1, termName: '声明独立草稿', startDate: '2027-09-01T00:00:00', endDate: '2028-01-31T23:59:59', teachingWeeks: 20, examWeekStart: 18, isCurrent: false, status: 'DRAFT' }
  const catalog = [source, target], current = { termId: '1', currentAuthority: 'AA_TERM_COMPAT', canDirectSwitch: true }
  const rows = [1, 2].map(n => ({ sourceEventId: String(10 + n), eventType: 'TEACHING', startDate: `2027-09-0${n * 2 - 1}`, endDate: `2027-09-0${n * 2}`, swapToDate: null, remark: `声明项目${n}`, status: 'READY', needsReview: false, reasons: [] }))
  const acks = rows.map((row, i) => ({ eventId: String(501 + i), termId: '101', eventType: row.eventType, startDate: row.startDate + 'T00:00:00', endDate: row.endDate + 'T00:00:00', swapToDate: null, remark: row.remark, version: 0 }))
  const declaredAuthorityFacts = [], counts = { catalog: 0, current: 0, calendar: 0, preview: 0, writes: 0 }
  const preview = () => ({ sourceTerm: { termId: '1', termName: source.termName, startDate: '2026-02-01', teachingWeeks: 20, examWeekStart: 18 }, targetTerm: { termId: '101', termName: target.termName, startDate: '2027-09-01', endDate: '2028-01-31', teachingWeeks: 20, examWeekStart: 18 }, mappingRule: 'TEACHING_WEEK_RELATIVE_WITH_EXAM_WEEK_ALIGNMENT', items: rows, readyCount: 2, reviewCount: 0, blockedCount: declaredAuthorityFacts.length, targetExistingCount: declaredAuthorityFacts.length, canConfirm: declaredAuthorityFacts.length === 0, nextStep: declaredAuthorityFacts.length ? '目标学期已有校历事件，请先确认现有内容；为避免重复，本次复制不允许直接确认。' : '预览无阻断，可确认复制；正式写入仍逐条经过校历 canonical 校验。' })
  const response = data => ({ status: 200, json: async () => ({ code: 0, data, message: 'ok' }) })
  const fetch = async (url, options) => {
    const u = new URL(url, 'https://declared.invalid'), method = options.method || 'GET', body = options.body ? JSON.parse(options.body) : null
    requests.push({ path: u.pathname, method, body }); assert.ok(requests.length <= 10); assert.equal(options.credentials, 'include'); assert.ok(options.signal instanceof AbortSignal)
    if (u.pathname === '/api/v1/academic-affairs/terms') { assert.equal(method, 'GET'); assert.deepEqual(Object.fromEntries(u.searchParams), { page: '1', pageSize: '100' }); assert.ok(++counts.catalog <= 2); return response({ items: catalog, total: 2, page: 1, pageSize: 100 }) }
    if (u.pathname === '/api/v1/academic-affairs/terms/current') { assert.equal(method, 'GET'); assert.ok(++counts.current <= 2); return response(current) }
    if (u.pathname === '/api/v1/academic-affairs/terms/101/calendar/copy-preview') { assert.equal(method, 'POST'); assert.deepEqual(body, { sourceTermId: '1' }); assert.ok(++counts.preview <= 2); return response(preview()) }
    assert.equal(u.pathname, '/api/v1/academic-affairs/terms/101/calendar'); assert.equal(u.search, '')
    if (method === 'GET') { assert.ok(++counts.calendar <= 3); return response({ items: JSON.parse(JSON.stringify(declaredAuthorityFacts)) }) }
    assert.equal(method, 'POST'); const ordinal = ++counts.writes; assert.ok(ordinal <= 2, 'No automatic third canonical write')
    assert.deepEqual(body, { eventType: rows[ordinal - 1].eventType, startDate: rows[ordinal - 1].startDate, endDate: rows[ordinal - 1].endDate, remark: rows[ordinal - 1].remark })
    if (mode !== 'healthy' && ordinal === failAt) {
      if (holdFailure) await new Promise(resolve => { releaseFailure = resolve })
      if (mode === 'rejected') return { status: 409, json: async () => ({ code: 409001, bizCode: 'DATA_CONFLICT', message: '目标日期已有安排', traceId: 'DECLARED_COPY_CONFLICT', data: null }) }
      // Explicit fixture fact: this unacknowledged row appears in later authority GET.
      // This models outcome uncertainty, and does not prove a real server committed.
      declaredAuthorityFacts.push(acks[ordinal - 1])
      if (mode === 'timeout') throw new DOMException('Declared response unavailable', 'AbortError')
      throw new TypeError('Declared response unavailable')
    }
    declaredAuthorityFacts.push(acks[ordinal - 1]); return response(acks[ordinal - 1])
  }
  const toast = { info: message => toasts.push({ kind: 'info', message }), success: message => toasts.push({ kind: 'success', message }), error: prohibited, warning: prohibited }
  const clientSource = calTypedRead('services/http/client.js').replace(/^import .*$/gm, '').replace(/\bimport\.meta\b/g, '__buildMeta').replace(/^export /gm, '')
  const client = new Function('API_BASE_URL', 'API_PREFIX', 'allowMockFallback', 'realApiEnabled', 'toast', 'normalizeUiError', 'fetch', 'sessionStorage', 'localStorage', 'BroadcastChannel', '__buildMeta', `${clientSource}\nreturn { request, setToken }`)('', '/api/v1', () => false, () => true, toast, calTypedNormalize, fetch, storage, storage, undefined, { env: { DEV: false } })
  client.setToken('DECLARED_NONEMPTY_TOKEN_NOT_LOGIN_PROOF')
  const apiSource = calTypedRead('modules/academicAffairs/api/academic-affairs.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default academicAffairsApi\s*$/m, '')
  const modules = new Function('request', 'requestBlob', 'requestUpload', 'shouldTryReal', 'currentUserFromToken', 'setPermissionPatterns', `${apiSource}\nreturn { academicAffairsApi, academicAffairsOrgApi, academicAffairsLabApi, academicAffairsEquipmentApi, academicAffairsExamApi, academicAffairsSelectionApi, academicAffairsMakeupApi, academicAffairsArchiveApi }`)(client.request, prohibited, prohibited, () => true, () => claims, prohibited)
  const originalApi = modules.academicAffairsApi, api = { ...originalApi, addCalendarEvent(...args) { return originalApi.addCalendarEvent(...args).then(dto => { dtos.push(structuredClone(dto)); return dto }) } }
  const convenience = calTypedRead('modules/academicAffairs/api/term-calendar-convenience.api.js').replace(/^import .*$/gm, '').replace(/^export const /gm, 'const ').replace(/^export default termCalendarConvenienceApi\s*$/m, '')
  const termCalendarConvenienceApi = new Function('request', `${convenience}\nreturn termCalendarConvenienceApi`)(client.request)
  const picker = calTypedRead('modules/academicAffairs/pickerAdapters.js').replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*;?\s*$/gm, '').replace(/^export (async function|function|const) /gm, '$1 ')
  const bindings = { ...modules, academicAffairsApi: api, academicStatusLabel: calTypedStatusLabel, SCHEDULE_BATCH_STATUS: calTypedBatchStatus }
  const loadAcademicTermCatalog = new Function(...Object.keys(bindings), `${picker}\nreturn loadAcademicTermCatalog`)(...Object.values(bindings))
  const AppButton = calTypedCompile('components/ui/AppButton.vue'), AppSelect = calTypedCompile('components/common/form/AppSelect.vue'), AppInlineAlert = calTypedCompile('components/common/AppInlineAlert.vue')
  const hidden = name => ({ name, inheritAttrs: false, render: () => h('section') })
  const visual = { ModulePageShell: calTypedVisual('DeclaredCopyLayout'), AppSectionCard: calTypedVisual('DeclaredCopySection'), AppFormItem: calTypedVisual('DeclaredUnopenedForm') }
  for (const name of ['StatusTag', 'LoadingState', 'ErrorState', 'EmptyState', 'AppDrawer', 'AppTextInput', 'AppDatePicker', 'AppTermEntityPicker', 'AppConfirmDialog', 'AaCalendarMonth', 'AaCalendarArchivePanel']) visual[name] = hidden(`DeclaredUnused${name}`)
  visual.DataTable = { props: ['rows'], inheritAttrs: false, render() { return h('output', {}, JSON.stringify(this.rows)) } }
  const Panel = calTypedCompile('modules/academicAffairs/components/AaCalendarCopyPanel.vue', { ...visual, AppButton, AppSelect, AppInlineAlert, academicAffairsApi: api, termCalendarConvenienceApi, toast })
  const Calendar = calTypedCompile('modules/academicAffairs/views/AaCalendarView.vue', { ...visual, AppButton, AppSelect, AppInlineAlert, AaCalendarCopyPanel: Panel, academicAffairsApi: api, academicAffairsTermDetailApi: { get: prohibited }, loadAcademicTermCatalog, toast, matchPermission, currentUserFromToken: () => claims, systemConfirm: calTypedDialog.systemConfirm })
  const renderer = createRenderer({ createElement: tag => calTypedNode(tag), createText: v => calTypedNode('#text', v), createComment: v => calTypedNode('#comment', v), setText(n, v) { n.value = v }, setElementText(n, v) { n.value = v; n.children = [] }, parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null, patchProp(n, k, _old, v) { n.props[k] = v }, insert(n, p, a = null) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = p; const i = a ? p.children.indexOf(a) : -1; if (i < 0) p.children.push(n); else p.children.splice(i, 0, n) }, remove(n) { if (n.parent) { n.parent.children.splice(n.parent.children.indexOf(n), 1); n.parent = null } } })
  const route = reactive({ path: '/admin/academic-affairs/calendar', fullPath: '/admin/academic-affairs/calendar?termId=101&tab=events', query: { termId: '101', tab: 'events' } }), root = calTypedNode('root')
  app = renderer.createApp({ render: () => state.ctx ? h(Calendar, { ctx: state.ctx, onVnodeMounted: vnode => { vm = vnode.component.proxy; mounts.push(vnode.component.uid) }, onVnodeUnmounted: vnode => unmounts.push(vnode.component.uid) }) : null })
  app.provide('academicFlow', { identity: () => calTypedIdentity(claims, state.ctx || {}), restorePosition() {} })
  app.config.globalProperties.$route = route; app.config.globalProperties.$router = { push: prohibited, replace: prohibited, options: { history: { state: {} } } }
  app.config.warnHandler = message => warnings.push(String(message)); app.config.errorHandler = error => errors.push({ name: error.name, message: error.message })
  const until = async (predicate, label) => { for (let i = 0; i < 60; i++) { await calTypedTick(); if (predicate()) return } assert.fail(label) }
  const click = label => { const found = calTypedWalk(root).filter(n => n.type === 'button' && calTypedText(n).trim() === label); assert.equal(found.length, 1, label); const n = found[0]; assert.equal(!!n.props.disabled, false, label); for (const fn of Array.isArray(n.props.onClick) ? n.props.onClick : [n.props.onClick]) { assert.equal(typeof fn, 'function'); fn({ type: 'click', target: n, currentTarget: n }) } }
  const loaded = () => vm?.$refs.calendarCopyPanel && !vm.termsLoading && !vm.eventsLoading
  app.mount(root); await until(loaded, 'Initial complete parent readback')
  assert.equal(vm.canEditEvents, true); assert.deepEqual(vm.terms, catalog); assert.deepEqual(vm.currentContext, current); assert.deepEqual(vm.events, [])
  const start = async () => { click('预览复制结果'); await until(() => vm.$refs.calendarCopyPanel.preview && !vm.$refs.calendarCopyPanel.loading, 'Preview complete'); assert.equal(vm.$refs.calendarCopyPanel.canApply, true); click('确认复制 2 项') }
  const settled = async () => { await until(() => dtos.length === counts.writes && !vm.copying && !vm.eventsLoading, 'Apply and parent authority readback'); assert.equal(vm.$refs.calendarCopyPanel.preview, null); assert.equal(vm.$refs.calendarCopyPanel.canApply, false); assert.equal(vm.$refs.calendarCopyPanel.applying, false); assert.equal(counts.calendar, 2); assert.deepEqual(vm.events, declaredAuthorityFacts); assert.deepEqual(errors, []); assert.deepEqual(warnings, []); return vm.$refs.calendarCopyPanel.error }
  const freshPreview = async () => { const writes = counts.writes; click('预览复制结果'); await until(() => vm.$refs.calendarCopyPanel.preview && !vm.$refs.calendarCopyPanel.loading, 'Fresh authority preview'); assert.equal(vm.$refs.calendarCopyPanel.preview.targetExistingCount, declaredAuthorityFacts.length); assert.equal(vm.$refs.calendarCopyPanel.preview.canConfirm, false); assert.equal(vm.$refs.calendarCopyPanel.canApply, false); const buttons = calTypedWalk(root).filter(n => n.type === 'button' && calTypedText(n).trim() === '确认复制 2 项'); assert.equal(buttons.length, 1); assert.equal(buttons[0].props.disabled, true); assert.equal(counts.writes, writes) }
  return { root, state, counts, requests, dtos, declaredAuthorityFacts, acks, toasts, mounts, unmounts, until, start, settled, freshPreview, vm: () => vm, release: () => releaseFailure?.(), async replaceScope() { state.ctx = null; await calTypedTick(); state.ctx = makeCtx('B'); await until(() => loaded() && mounts.length === 2, 'Fresh B authority readback') } }
}

test('calendar copy complete canonical batch clears preview and parent reads both acknowledged facts', async t => {
  const f = await copyOutcomeFixture(t)
  await f.start(); assert.equal(await f.settled(), '')
  assert.deepEqual(f.counts, { catalog: 1, current: 1, calendar: 2, preview: 1, writes: 2 }); assert.equal(f.requests.length, 7)
  assert.deepEqual(f.dtos.map(dto => dto.code), [0, 0]); assert.deepEqual(f.vm().events, f.acks); assert.equal(f.toasts.filter(v => v.kind === 'success').length, 1)
})

test('calendar copy definitive second business409 stops after one ACK and fresh preview blocks duplicate apply', async t => {
  const f = await copyOutcomeFixture(t, { mode: 'rejected' })
  await f.start(); const message = await f.settled()
  assert.match(message, /已复制 1 项/); assert.match(message, /第 2 项被系统拒绝/); assert.equal(message.includes('结果尚未确认'), false)
  assert.equal(f.dtos[1].httpStatus, 409); assert.equal(f.dtos[1].bizCode, 'DATA_CONFLICT'); assert.deepEqual(f.vm().events, [f.acks[0]]); assert.equal(f.toasts.filter(v => v.kind === 'success').length, 0)
  await f.freshPreview(); assert.equal(f.counts.writes, 2); assert.equal(f.requests.length, 8)
})

test('calendar copy first raw fetch loss reports zero received ACKs and reads authority before a nonrepeatable preview', async t => {
  const f = await copyOutcomeFixture(t, { mode: 'unknown', failAt: 1 })
  await f.start(); const message = await f.settled()
  assert.match(message, /已复制 0 项/); assert.match(message, /仅计已收到成功回执/); assert.match(message, /第 1 项结果尚未确认/)
  for (const forbidden of ['被系统拒绝', 'mock', 'TypeError', '真实接口不可用']) assert.equal(message.includes(forbidden), false)
  assert.equal(f.dtos[0].code, 503002); assert.equal(f.dtos[0].httpStatus, undefined); assert.deepEqual(f.vm().events, [f.acks[0]])
  assert.equal(f.counts.writes, 1); assert.equal(f.requests.length, 6); await f.freshPreview(); assert.equal(f.counts.writes, 1); assert.equal(f.requests.length, 7)
})

test('calendar copy second actual REQUEST_TIMEOUT preserves first ACK and unknown row without automatic resend', async t => {
  const f = await copyOutcomeFixture(t, { mode: 'timeout' })
  await f.start(); const message = await f.settled()
  assert.match(message, /已复制 1 项/); assert.match(message, /仅计已收到成功回执/); assert.match(message, /第 2 项结果尚未确认/); assert.match(message, /核对校历与操作记录/); assert.match(message, /不要自动重发/)
  assert.equal(message.includes('被系统拒绝'), false); assert.equal(message.includes('mock'), false); assert.equal(f.dtos[1].code, 503002); assert.equal(f.dtos[1].bizCode, 'REQUEST_TIMEOUT'); assert.equal(f.dtos[1].httpStatus, undefined)
  assert.deepEqual(f.vm().events, f.acks); assert.equal(f.counts.writes, 2); assert.equal(f.requests.length, 7); await f.freshPreview(); assert.equal(f.counts.writes, 2); assert.equal(f.requests.length, 8)
})

test('calendar copy old pending transport result after actual owner unmount does not publish into new scope or continue writes', async t => {
  const f = await copyOutcomeFixture(t, { mode: 'unknown', holdFailure: true })
  await f.start(); await f.until(() => f.counts.writes === 2 && f.dtos.length === 1, 'Second declared fetch held after first ACK')
  const oldPanel = f.vm().$refs.calendarCopyPanel
  await f.replaceScope(); assert.equal(f.unmounts.length, 1); assert.equal(f.mounts.length, 2); assert.notEqual(f.mounts[0], f.mounts[1]); assert.equal(oldPanel.disposed, true)
  assert.equal(f.vm().$refs.calendarCopyPanel.error, ''); assert.equal(f.vm().$refs.calendarCopyPanel.preview, null); assert.deepEqual(f.vm().events, [f.acks[0]])
  f.release(); await f.until(() => f.dtos.length === 2, 'Old transport settles'); await calTypedTick()
  assert.deepEqual(f.counts, { catalog: 2, current: 2, calendar: 2, preview: 1, writes: 2 }); assert.equal(f.requests.length, 9)
  assert.equal(f.vm().$refs.calendarCopyPanel.error, ''); assert.equal(f.vm().$refs.calendarCopyPanel.preview, null); assert.deepEqual(f.vm().events, [f.acks[0]]); assert.equal(f.toasts.filter(v => v.kind === 'success').length, 0)
})
