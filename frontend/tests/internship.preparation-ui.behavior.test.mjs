import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { withInternshipBatch, internshipBatchListReturn } from '../src/modules/internship/navigation.js'

// Execute the real Options API script; replace network/UI dependencies only.
// These component regressions do not claim real API or browser E2E coverage.
function component(file, api, overrides = {}) {
  const path = new URL('../src/modules/internship/views/' + file, import.meta.url)
  const script = parse(fs.readFileSync(path, 'utf8')).descriptor.script.content
    .replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '')
    .replace(/components:\s*\{[^}]*\},/, 'components: {},')
    .replace('export default', 'return')
  const feedback = []
  const guard = { saved: 0, markSaved() { this.saved++ } }
  const options = new Function('internshipApi', 'toast', 'formatDate', 'formatDateTime',
    'withInternshipBatch', 'matchPermission', 'window', 'internStudentApi', 'canCode', 'useInternshipBatchStore', 'internshipBatchListReturn', script)(
    api, { error: (message) => feedback.push(message), success: (message) => feedback.push(message) },
    (value) => value || '', (value) => value || '', withInternshipBatch, () => false,
    { __SAAS_DIRTY_FORM_GUARD__: guard }, api, (ctx, code) => (ctx?.permissions || []).includes(code), () => overrides.batchStore, internshipBatchListReturn)
  const instance = { ...options.data(), $nextTick: async () => {}, ...overrides }
  for (const [key, method] of Object.entries(options.methods)) instance[key] = method.bind(instance)
  for (const [key, getter] of Object.entries(options.computed || {})) {
    Object.defineProperty(instance, key, { get: () => getter.call(instance), configurable: true })
  }
  return { instance, options, guard, feedback }
}
const ok = (data) => ({ code: 0, data })

test('student arrangement returns to the same volunteer record and batch without accepting external destinations', () => {
  const pushes = [], target = '/admin/internship/volunteer-review/8?batchId=1&campaignId=2&page=3'
  const { instance: view } = component('InternshipStudentDetailView.vue', {}, { $route: { params: { id: '31' }, query: { batchId: '1', returnTo: target } }, $router: { push: r => pushes.push(r) } })
  view.detail = { id: '31', batchId: '1' }
  view.goBack(); assert.equal(pushes[0], target)
  for (const invalid of [target.replace('batchId=1', 'batchId=2'), 'https://external.invalid/admin/internship/volunteer-review/8?batchId=1']) {
    view.$route.query.returnTo = invalid
    view.goBack(); assert.deepEqual(pushes.at(-1), { path: '/admin/internship/students', query: { batchId: '1' } })
  }
})

test('onboard checks keep blockers visible and recover from network failure without opening confirmation', async () => {
  let fail = true
  const { instance: view } = component('InternshipStudentDetailView.vue', { getOnboardChecklist: async () => { if (fail) throw new Error('网络不可用'); return ok({ canOnboard: false, statusReady: true, blockers: ['协议尚未生效'] }) } }, { ctx: { permissions: ['internship.student.manage'] }, $route: { query: { batchId: '1' } } })
  view.detail = { id: '31', status: 'READY', batchStatus: 'RUNNING' }
  await view.askStatus('ONBOARD')
  assert.equal(view.onboardError, '网络不可用'); assert.equal(view.onboardLoading, false); assert.equal(view.confirm.visible, false)
  fail = false; await view.askStatus('ONBOARD')
  assert.deepEqual(view.onboardChecklist.blockers, ['协议尚未生效']); assert.equal(view.onboardError, ''); assert.equal(view.confirm.visible, false)
})

test('an agreement blocker links to the student agreements with the exact return context', () => {
  const fullPath = '/admin/internship/students/9007199254740999?batchId=7&section=placement'
  const { instance: view } = component('InternshipStudentDetailView.vue', {}, { ctx: { permissions: ['internship.agreement.view'] }, $route: { fullPath, query: { batchId: '7' } } })
  view.detail = { id: '9007199254740999', name: '虚构学生', studentNo: 'TEST-002', batchId: '7' }
  view.onboardChecklist = { evaluation: { blockers: [{ code: 'agreement', status: 'MISSING' }] } }
  assert.deepEqual(view.agreementFollowUp, { path: '/admin/internship/agreements', query: { batchId: '7', panel: 'confirm', status: '', keyword: '虚构学生', returnTo: fullPath } })
  view.ctx.permissions = []; assert.equal(view.agreementFollowUp, null)
})

test('student placement links retain the exact batch and dossier return location', () => {
  const routes = [], fullPath = '/admin/internship/students/9007199254740999?batchId=7&section=placement'
  const { instance: view } = component('InternshipStudentDetailView.vue', {}, {
    $route: { fullPath, query: { batchId: '7' } }, $router: { push: to => routes.push(to) }
  })
  view.detail = { batchId: '7', enterpriseId: '9007199254740998', positionId: '9007199254740997' }
  view.openEnterprise(); view.openPosition()
  assert.deepEqual(routes, [
    { path: '/admin/internship/enterprises/9007199254740998', query: { batchId: '7', returnTo: fullPath } },
    { path: '/admin/internship/positions/9007199254740997', query: { batchId: '7', returnTo: fullPath } }
  ])
})

test('onboard agreement follow-up does not infer a blocker from text or stale results', () => {
  const { instance: view } = component('InternshipStudentDetailView.vue', {}, { ctx: { permissions: ['internship.agreement.view'] } })
  view.detail = { name: '虚构学生', studentNo: 'TEST-002', batchId: '7' }
  view.onboardChecklist = { blockers: ['三方协议未生效'] }; assert.equal(view.agreementFollowUp, null)
  view.onboardChecklist.evaluation = { blockers: [{ code: 'agreement' }] }
  view.onboardError = '读取失败'; assert.equal(view.agreementFollowUp, null)
  view.onboardError = ''; view.onboardLoading = true; assert.equal(view.agreementFollowUp, null)
})

test('onboard checks suppress duplicates and never confirm a different student after a late result', async () => {
  let resolve, calls = 0
  const pending = new Promise(r => { resolve = r })
  const { instance: view } = component('InternshipStudentDetailView.vue', { getOnboardChecklist: () => { calls++; return pending } }, { ctx: { permissions: ['internship.student.manage'] }, $route: { query: { batchId: '1' } } })
  view.detail = { id: '31', status: 'READY', batchStatus: 'RUNNING' }
  const first = view.askStatus('ONBOARD'); await view.askStatus('ONBOARD'); assert.equal(calls, 1)
  view.detail = { id: '32', status: 'READY', batchStatus: 'RUNNING' }
  resolve(ok({ canOnboard: true, statusReady: true, blockers: [] })); await first
  assert.equal(view.confirm.visible, false); assert.equal(view.onboardChecklist, null)
})

test('only the current state action can open the existing status confirmation after successful checks', async () => {
  const { instance: view } = component('InternshipStudentDetailView.vue', { getOnboardChecklist: async () => ok({ canOnboard: true, statusReady: true, blockers: [] }) }, { ctx: { permissions: ['internship.student.manage'] }, $route: { query: { batchId: '1' } } })
  view.detail = { id: '31', status: 'READY', batchStatus: 'RUNNING' }
  await view.askStatus('ASSESS'); assert.equal(view.confirm.visible, false)
  await view.askStatus('ONBOARD'); assert.equal(view.confirm.visible, true); assert.equal(view.confirm.extra, 'ONBOARD')
})
const deferred = () => {
  let resolve
  const promise = new Promise((r) => { resolve = r })
  return { promise, resolve }
}
const participantApi = (overrides = {}) => ({
  getBatchParticipantRule: async () => ok({ rule: { classIds: ['10'] }, frozen: true }),
  getBatchParticipantSummary: async () => ok({ activeCount: 1 }),
  getBatchParticipants: async () => ok({ list: [{ id: 'new' }], total: 1 }),
  ...overrides
})

test('batch detail refresh updates the active selector after participant activation', async () => {
  const store = { availableBatches: [{ id: '23', status: 'DRAFT' }], selectedBatchId: '23', applyBatch(batch) { this.batchStatus = batch.status } }
  const { instance: view } = component('BatchDetailView.vue', {
    getBatchDetail: async () => ok({ id: '23', status: 'RUNNING', batchName: '验收批次' })
  }, { $route: { params: { id: '23' }, query: {} }, batchStore: store })
  await view.load()
  assert.equal(view.detail.status, 'RUNNING')
  assert.equal(store.availableBatches[0].status, 'RUNNING')
  assert.equal(store.batchStatus, 'RUNNING')
})

test('student deep links reject a record belonging to a different batch', async () => {
  const { instance: view } = component('InternshipStudentDetailView.vue', {
    getStudentDetail: async () => ok({ id: '31', batchId: '22' })
  }, { $route: { params: { id: '31' }, query: { batchId: '23' } } })
  await view.load()
  assert.equal(view.detail, null)
  assert.match(view.error, /不属于当前批次/)
})

test('batch context failure is retryable and does not become an authorization denial', async () => {
  let failed = true
  const { instance: view } = component('BatchFormView.vue', {
    getContext: async () => failed ? { code: 500001, message: '上下文暂不可用' } : ok({ permissionActions: { createBatch: { allowed: true } } })
  }, { $route: { params: {}, path: '/admin/internship/batches/new' } })
  await view.loadContext()
  assert.equal(view.contextLoading, false)
  assert.equal(view.contextError, '上下文暂不可用')
  assert.equal(view.ctx, null)
  failed = false
  await view.loadContext()
  assert.equal(view.contextError, '')
  assert.equal(view.readonly, false)
})

test('student detail retains the selected record when an earlier deep-link load finishes late', async () => {
  const old = deferred()
  const { instance: view } = component('InternshipStudentDetailView.vue', {
    getStudentDetail: (id) => id === 'old' ? old.promise : Promise.resolve(ok({ id: 'new' }))
  }, { $route: { params: { id: 'old' }, query: {} } })
  const first = view.load()
  view.$route.params.id = 'new'
  await view.load()
  old.resolve(ok({ id: 'old' }))
  await first
  assert.equal(view.detail.id, 'new')
})

test('qualification conflict preserves the selected result, note, and original record version', async () => {
  const { instance: view, guard } = component('InternshipStudentDetailView.vue', {
    setEligibility: async () => ({ code: 409001, message: '记录已被修改' })
  }, { ctx: { permissions: ['internship.student.eligibility.review'] } })
  view.detail = { id: '31', version: 2, status: 'PREPARING', batchStatus: 'RUNNING' }
  view.reviewForm = { status: 'UNQUALIFIED', reason: '请核对补充材料' }
  view.askEligibility()
  await view.onConfirm()
  assert.equal(view.reviewConflict, true)
  assert.equal(view.reviewForm.reason, '请核对补充材料')
  assert.equal(view.detail.version, 2)
  assert.equal(guard.saved, 0)
  view.askEligibility()
  assert.equal(view.confirm.visible, false)
})

test('readonly records cannot open a qualification write and return links keep list filters', () => {
  const routes = []
  const { instance: view } = component('InternshipStudentDetailView.vue', {}, {
    ctx: { permissions: ['internship.student.eligibility.review'] },
    $route: { query: { returnTo: '/admin/internship/students?keyword=student&page=3&batchId=22' } },
    $router: { push: (location) => routes.push(location) }
  })
  view.detail = { status: 'PREPARING', batchStatus: 'CLOSED' }
  view.reviewForm.status = 'QUALIFIED'
  view.askEligibility()
  assert.equal(view.confirm.visible, false)
  view.goBack()
  assert.equal(routes[0], '/admin/internship/students?keyword=student&page=3&batchId=22')
})

test('participant summary or list failure stays an error instead of reporting an empty roster', async () => {
  for (const method of ['getBatchParticipantSummary', 'getBatchParticipants']) {
    const { instance: view } = component('components/BatchParticipantScope.vue', participantApi({
      [method]: async () => ({ code: 503001, message: '服务暂时不可用' })
    }), { batchId: '1' })
    await view.load()
    assert.equal(view.loading, false)
    assert.equal(view.error, '服务暂时不可用')
    assert.equal(view.ruleReady, false)
    assert.equal(view.previewDirty, true)
  }
})

test('late roster response cannot replace the newly selected batch', async () => {
  const old = deferred()
  const { instance: view } = component('components/BatchParticipantScope.vue', participantApi({
    getBatchParticipantRule: (id) => id === 'old' ? old.promise : Promise.resolve(ok({ rule: { classIds: ['new-class'] }, frozen: true }))
  }), { batchId: 'old' })
  const first = view.load()
  view.batchId = 'new'
  await view.load()
  old.resolve(ok({ rule: { classIds: ['old-class'] }, frozen: false }))
  await first
  assert.deepEqual(view.rule.classIds, ['new-class'])
  assert.equal(view.frozen, true)
  assert.equal(view.error, '')
  assert.equal(view.loading, false)
})

test('an older refresh of the same batch cannot overwrite a newer roster', async () => {
  const old = deferred()
  let count = 0
  const { instance: view } = component('components/BatchParticipantScope.vue', participantApi({
    getBatchParticipantSummary: () => ++count === 1 ? old.promise : Promise.resolve(ok({ activeCount: 12 }))
  }), { batchId: '1' })
  const first = view.load()
  await view.load()
  old.resolve(ok({ activeCount: 2 }))
  await first
  assert.equal(view.summary.activeCount, 12)
})

test('batch form conflict preserves input and original version, and blocks blind resubmission', async () => {
  let writes = 0
  const { instance: view, guard } = component('BatchFormView.vue', {
    updateBatch: async () => { writes++; return { code: 409001, message: '其他人已修改批次' } }
  }, {
    ctx: { permissionActions: { createBatch: { allowed: true } } },
    detail: { id: '7', status: 'DRAFT', version: 3 },
    $route: { params: { id: '7' }, path: '/admin/internship/batches/7/edit', query: {} },
    $refs: { batchForm: { validate: async () => ({ valid: true }) } }
  })
  view.form.batchName = '保留我的实习安排'
  await view.onSubmit()
  assert.equal(view.versionConflict, true)
  assert.equal(view.detail.version, 3)
  assert.equal(view.form.batchName, '保留我的实习安排')
  assert.equal(guard.saved, 0)
  await view.onSubmit()
  assert.equal(writes, 1)
})

test('successful creation clears dirty state only after success and opens the new batch roster', async () => {
  const writes = []
  const locations = []
  const { instance: view, guard } = component('BatchFormView.vue', {
    createBatch: async (body) => { writes.push(body); return ok({ id: '123' }) }
  }, {
    ctx: { permissionActions: { createBatch: { allowed: true } } },
    $route: { params: {}, path: '/admin/internship/batches/new', query: {} },
    $router: { push: (location) => locations.push(location) },
    $refs: { batchForm: { validate: async () => ({ valid: true }) } }
  })
  view.form.batchName = '本轮实习'
  view.form.batchNo = 'PREP-TEST'
  await view.onSubmit()
  assert.equal(writes.length, 1)
  assert.equal(guard.saved, 1)
  assert.equal(locations[0].path, '/admin/internship/batches/123')
  assert.deepEqual(locations[0].query, { setup: 'participants', batchId: '123' })
})

test('structured and advanced mode retain the edited stages and rule values', () => {
  const { instance: view } = component('BatchFormView.vue', {}, {
    $route: { params: {}, path: '/admin/internship/batches/new', query: {} }
  })
  view.stageRows = [{ code: 'PREP', name: '岗前准备', startDate: '2026-09-01', endDate: '2026-09-10' }]
  view.rulesForm.checkin.geofenceRadiusM = 750
  view.toggleAdvanced()
  assert.equal(JSON.parse(view.form.rulesJson).checkin.geofenceRadiusM, 750)
  view.form.rulesJson = view.form.rulesJson.replace('750', '900')
  view.toggleAdvanced()
  assert.equal(view.advancedJson, false)
  assert.equal(view.rulesForm.checkin.geofenceRadiusM, 900)
  assert.equal(view.stageRows[0].code, 'PREP')
})

test('assignment ledger opens the actual record batch and carries the exact return location', async () => {
  const calls = []
  const returnTo = '/admin/internship/assignment-logs?batchId=7&page=3&keyword=UITEST'
  const { instance: view } = component('AssignmentLogView.vue', { getStudentDetail: async () => ok({ batchId: '22' }) }, {
    ctx: { permissions: ['internship.student.view'] },
    $route: { fullPath: returnTo, query: { batchId: '7' } }, $router: { push: (to) => calls.push(to) }
  })
  await view.openStudent({ recordId: '9007199254740997' })
  assert.deepEqual(calls[0], { path: '/admin/internship/students/9007199254740997', query: { batchId: '22', returnTo } })
})

test('student dossier returns to the assignment ledger but rejects outside return destinations', () => {
  const calls = []
  const { instance: view } = component('InternshipStudentDetailView.vue', {}, {
    $route: { query: { batchId: '7', returnTo: '/admin/internship/assignment-logs?page=3&keyword=UITEST' } }, $router: { push: (to) => calls.push(to) }
  })
  view.goBack()
  assert.equal(calls[0], '/admin/internship/assignment-logs?page=3&keyword=UITEST')
  view.$route.query.returnTo = 'https://outside.example/'
  view.goBack()
  assert.deepEqual(calls[1], { path: '/admin/internship/students', query: { batchId: '7' } })
})

test('student dossier returns to the exact insurance record and rejects an outside or malformed policy path', () => {
  const calls = [], target = '/admin/internship/insurance/9007199254740995?batchId=7&page=3&status=ALL'
  const { instance: view } = component('InternshipStudentDetailView.vue', {}, { $route: { query: { batchId: '7', returnTo: target } }, $router: { push: to => calls.push(to) } })
  view.goBack(); assert.equal(calls[0], target)
  for (const invalid of ['https://outside.example' + target, '/admin/internship/insurance/not-a-record', '/admin/internship/insurance/31/other']) {
    view.$route.query.returnTo = invalid; view.goBack()
    assert.deepEqual(calls.at(-1), { path: '/admin/internship/students', query: { batchId: '7' } })
  }
})

test('a stale assignment dossier lookup cannot navigate after filters change', async () => {
  const work = deferred(), calls = []
  const { instance: view } = component('AssignmentLogView.vue', { getStudentDetail: () => work.promise }, {
    ctx: { permissions: ['internship.student.view'] },
    $route: { fullPath: '/admin/internship/assignment-logs' }, $router: { push: (to) => calls.push(to) }
  })
  const pending = view.openStudent({ recordId: '1' })
  view.ticket++
  work.resolve(ok({ batchId: '22' })); await pending
  assert.equal(calls.length, 0)
})

test('assignment ledger paging and retry keep the applied search', async () => {
  const requests = [], locations = []
  const { instance: view } = component('AssignmentLogView.vue', { getAssignmentLogs: async q => { requests.push(q); return ok({ list: [], total: 0 }) } }, {
    $route: { path: '/admin/internship/assignment-logs', fullPath: '/admin/internship/assignment-logs?keyword=已查询', query: { keyword: '已查询' } },
    $router: { resolve: () => ({ fullPath: 'changed' }), replace: to => locations.push(to) }
  })
  view.appliedKeyword = '已查询'; view.keyword = '未查询草稿'
  view.onPageChange(3); await view.load()
  assert.equal(locations[0].query.keyword, '已查询'); assert.equal(requests[0].keyword, '已查询')
  view.reload(); assert.equal(locations[1].query.keyword, '未查询草稿'); assert.equal(view.page, 1)
})

test('assignment ledger network failure clears stale rows and can recover', async () => {
  let fails = true
  const { instance: view } = component('AssignmentLogView.vue', { getAssignmentLogs: async () => { if (fails) throw new Error('网络不可用'); return ok({ list: [{ id: 'new' }], total: 1 }) } })
  view.rows = [{ id: 'old' }]; await view.load()
  assert.equal(view.loading, false); assert.equal(view.error, '网络不可用'); assert.deepEqual(view.rows, [])
  fails = false; await view.load(); assert.equal(view.error, ''); assert.equal(view.rows[0].id, 'new')
})

test('assignment dossier lookup failure releases the action and allows retry', async () => {
  let fails = true; const calls = []
  const { instance: view } = component('AssignmentLogView.vue', { getStudentDetail: async () => { if (fails) throw new Error('详情网络不可用'); return ok({ batchId: '22' }) } }, {
    ctx: { permissions: ['internship.student.view'] }, $route: { fullPath: '/admin/internship/assignment-logs' }, $router: { push: to => calls.push(to) }
  })
  await view.openStudent({ recordId: '1' }); assert.equal(view.opening, ''); assert.equal(view.openError, '详情网络不可用')
  fails = false; await view.openStudent({ recordId: '1' }); assert.equal(view.openError, ''); assert.equal(calls.length, 1)
})

test('assignment ledger permission does not imply student dossier permission', async () => {
  let reads = 0
  const { instance: view } = component('AssignmentLogView.vue', { getStudentDetail: async () => { reads++; return ok({ batchId: '1' }) } }, { ctx: { permissions: ['internship.match.log.view'] } })
  await view.openStudent({ recordId: '1' }); assert.equal(reads, 0)
})

test('an old dossier lookup cannot unlock the new lookup after navigation', async () => {
  const first = deferred(), second = deferred(), calls = []
  const { instance: view } = component('AssignmentLogView.vue', { getStudentDetail: id => id === '1' ? first.promise : second.promise }, {
    ctx: { permissions: ['internship.student.view'] }, $route: { fullPath: '/admin/internship/assignment-logs', query: {} }, $router: { push: to => calls.push(to) }
  })
  view.load = () => {}; const old = view.openStudent({ recordId: '1' })
  view.$route.fullPath += '?page=2'; view.restoreLocation()
  const next = view.openStudent({ recordId: '2' })
  first.resolve(ok({ batchId: '22' })); await old
  assert.equal(view.opening, '2'); assert.equal(calls.length, 0)
  second.resolve(ok({ batchId: '22' })); await next
  assert.equal(view.opening, ''); assert.equal(calls[0].path, '/admin/internship/students/2')
})

test('batch paging and export use the displayed query rather than an unsubmitted draft', async () => {
  const calls = [], locations = []
  const { instance: view } = component('InternshipBatchListView.vue', {
    exportBatches: async (query) => calls.push(query)
  }, {
    $route: { path: '/admin/internship/batches', query: { panel: 'list' }, fullPath: '/admin/internship/batches?panel=list' },
    $router: { resolve: () => ({ fullPath: '/new-query' }), replace: (to) => locations.push(to) }
  })
  view.appliedFilters = { keyword: '已查询', status: 'RUNNING' }
  view.filters = { keyword: '尚未查询', status: 'DRAFT' }
  view.turnPage(2)
  await view.exportFn()
  assert.equal(locations[0].query.keyword, '已查询')
  assert.equal(locations[0].query.status, 'RUNNING')
  assert.deepEqual(calls[0], view.appliedFilters)
  view.search()
  assert.equal(locations[1].query.keyword, '尚未查询')
  assert.equal(locations[1].query.page, '1')
})

test('batch configuration entry opens its section and keeps the precise list return', () => {
  const returnTo = '/admin/internship/batches?panel=configuration&keyword=春季&page=3'
  const { instance: view } = component('InternshipBatchListView.vue', {}, {
    $route: { query: { panel: 'configuration' }, fullPath: returnTo }
  })
  const location = view.detailLocation({ id: '9007199254740997' })
  assert.equal(location.query.setup, 'rules')
  assert.equal(location.query.batchId, '9007199254740997')
  assert.equal(location.query.returnTo, returnTo)
})

test('batch edit returns to its original section then the filtered list without browser history', () => {
  const returnTo = '/admin/internship/batches?panel=configuration&keyword=春季&page=3'
  const locations = []
  const { instance: form } = component('BatchFormView.vue', {}, {
    $route: { params: { id: '23' }, path: '/admin/internship/batches/23/edit', query: { returnTo, setup: 'rules' } },
    $router: { push: (to) => locations.push(to) }
  })
  form.goBack()
  assert.equal(locations[0].path, '/admin/internship/batches/23')
  assert.equal(locations[0].query.setup, 'rules')
  const { instance: detail } = component('BatchDetailView.vue', {}, {
    $route: { query: locations[0].query }, $router: { push: (to) => locations.push(to) }
  })
  detail.goBack()
  assert.equal(locations[1], returnTo)
})

test('batch return rejects external pages and sibling detail routes', () => {
  for (const returnTo of ['https://outside.example', '//outside.example', '/admin/internship/batches/1/edit', '/admin/internship/batches-other']) {
    assert.deepEqual(internshipBatchListReturn({ returnTo }, '23'), {
      path: '/admin/internship/batches', query: { panel: 'list', batchId: '23' }, hash: ''
    })
  }
})

test('batch reload failure clears old data and does not leave a loading spinner', async () => {
  const { instance: view } = component('BatchDetailView.vue', {
    getBatchDetail: async () => { throw new Error('网络暂不可用') }
  }, { $route: { params: { id: '23' }, query: {} } })
  view.detail = { id: '23', status: 'DRAFT' }
  await view.load()
  assert.equal(view.detail, null)
  assert.equal(view.error, '网络暂不可用')
  assert.equal(view.loading, false)
})

test('an earlier refresh of the same batch cannot overwrite the new version', async () => {
  const old = deferred()
  let count = 0
  const { instance: view } = component('BatchDetailView.vue', {
    getBatchDetail: () => ++count === 1 ? old.promise : Promise.resolve(ok({ id: '23', version: 4 }))
  }, { $route: { params: { id: '23' }, query: {} }, batchStore: { availableBatches: [] } })
  const pending = view.load()
  await view.load()
  old.resolve(ok({ id: '23', version: 3 })); await pending
  assert.equal(view.detail.version, 4)
})

test('batch rules show readable weekdays and the saved onboarding requirements', () => {
  const { instance: view } = component('BatchDetailView.vue', {})
  view.detail = { rules: {
    weeklyReport: { frequency: 'WEEKLY', minWordCount: 800, deadlineWeekday: 7 },
    onboard: { requireAgreement: true, requireInsurance: false }
  } }
  assert.match(view.rulesList[0].value, /周日前提交/)
  assert.match(view.rulesList[1].value, /三方协议生效：必需/)
  assert.match(view.rulesList[1].value, /保险核验：不要求/)
  assert.match(view.rulesList[1].value, /分配校内指导教师：未配置/)
})

test('internship layout exposes context failures and retry restores real batch loading', async () => {
  let failed = true, batchLoads = 0
  const { instance: view } = component('AdminInternshipLayout.vue', {
    getContext: async () => {
      if (failed) throw new Error('请求超时，请重试')
      return ok({ permissionPatterns: ['internship.batch.view'], tenantBrandConfig: { schoolName: '测试学校' } })
    }
  })
  view.reloadBatches = async () => { batchLoads++ }
  await view.reloadContext()
  assert.equal(view.contextError, '请求超时，请重试'); assert.equal(view.ctx, null)
  assert.equal(view.contextLoading, false); assert.equal(batchLoads, 0)
  failed = false; await view.reloadContext()
  assert.equal(view.contextError, ''); assert.equal(batchLoads, 1)
  assert.equal(view.brandTitle, '测试学校 · 管理端')
})

test('incomplete identity stops business loading but an explicit permission-service failure keeps its error', async () => {
  let data = { permissionPatterns: null }
  const { instance: view } = component('AdminInternshipLayout.vue', { getContext: async () => ok(data) })
  let batchLoads = 0; view.reloadBatches = async () => { batchLoads++ }
  await view.reloadContext()
  assert.match(view.contextError, /身份信息未能完整加载/)
  assert.equal(view.ctx, null); assert.equal(batchLoads, 0)
  data = { permissionPatterns: null, permissionServiceError: '权限服务维护中' }
  await view.reloadContext()
  assert.equal(view.contextError, ''); assert.equal(view.permissionServiceBlocked, true)
  assert.equal(view.ctx.permissionServiceError, '权限服务维护中'); assert.equal(batchLoads, 0)
})

test('layout ignores duplicate retries and an unmounted context result', async () => {
  const pending = deferred(); let requests = 0, batchLoads = 0
  const { instance: view } = component('AdminInternshipLayout.vue', { getContext: () => { requests++; return pending.promise } })
  view.reloadBatches = async () => { batchLoads++ }
  const first = view.reloadContext(); await view.reloadContext()
  assert.equal(requests, 1)
  view.contextTicket++
  pending.resolve(ok({ permissionPatterns: [] })); await first
  assert.equal(view.ctx, null); assert.equal(batchLoads, 0)
})

test('a layout hot update can mount while the page still owns the earlier dirty guard', () => {
  const { instance: view, options, guard } = component('AdminInternshipLayout.vue', {})
  assert.equal(guard.registerConfirmation, undefined)
  assert.doesNotThrow(() => options.mounted.call(view))
  assert.equal(view.removeLeaveConfirmation, undefined)
  assert.equal(guard.saved, 0)
})
