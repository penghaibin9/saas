import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { reactive, createSSRApp, h } from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { normalizeFileReadiness, refreshFileReadiness } from '../src/services/fileReadiness.mjs'
import { checkinLocationPolicy } from '../src/services/checkinPresentation.mjs'

const target = { batchId: '9007199254741001', planId: '9007199254741002', internshipId: '9007199254741003',
  expectedVersion: 4, expectedPlanVersion: 2, name: '合成学生', generation: 1 }
const plan = (overrides = {}) => ({ id: target.planId, batchId: target.batchId, version: 2,
  studentTotal: 28, visitedStudentCount: 3, studentPage: 1, studentHasMore: true,
  students: [{ ...target, resolvable: true, visited: false }], ...overrides })
const result = (plans = [plan()], overrides = {}) => ({ batchId: target.batchId, plans, total: 1, page: 1, hasMore: false, ...overrides })
const photo = { fileId: '9007199254741004', fileName: '合成巡访.png', status: 'AVAILABLE', scanStatus: 'CLEAN', readyForBusiness: true }
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const flush = () => new Promise(resolve => setImmediate(resolve))

function load(form = false, extra = {}) {
  let generation = 1, chooser
  const notices = [], emitted = []
  const store = { loaded: true, selectedBatchId: target.batchId, batches: [{ id: target.batchId, name: '合成批次' }],
    selectBatch(id) { this.selectedBatchId = String(id); return true }, can: () => true }
  const deps = { teacherApi: { getInternshipVisitPlans: async () => result() },
    teacherInternshipEvidenceV3Api: { visitTargets: async () => result() },
    fileSdk: {}, uploadBusinessFile: async () => photo, normalizeFileReadiness, refreshFileReadiness, checkinLocationPolicy,
    currentSessionGeneration: () => generation, useInternshipContextStore: () => store,
    normalizeError: e => ({ text: e.message || '操作未完成', kind: e.httpStatus === 409 ? 'conflict' : 'network' }),
    toast: text => notices.push(text), listPaging: () => ({}), handleCheckinV3() {},
    InternshipVisitEvidenceForm: {}, MobileSequentialQueue: {}, ReportFilePreview: {}, ReportObligations: {},
    uni: { chooseImage: options => { chooser = options }, navigateTo() {} }, ...extra }
  const path = form ? '../src/components/teacher/InternshipVisitEvidenceForm.vue' : '../src/pages/teacher-internship/internship-review/index.vue'
  const script = fs.readFileSync(new URL(path, import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const props = form ? { target: { ...target }, active: true, submitting: false, conflicted: false } : {}
  const vm = reactive({ ...props, ...component.data.call(props), $refs: {},
    $emit: (...args) => emitted.push(args), pagedReset() {} })
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: fn.bind(vm) })
  if (form) vm.originalContext = { ...target }
  else { vm.batchId = target.batchId; vm.state = 'ready'; vm.data = { reports: [], abnormal: [] } }
  return { vm, component, notices, emitted, store, chooser: () => chooser, logout: () => generation++ }
}
const fill = vm => Object.assign(vm.form, { title: '合成岗位适应巡访', contactPerson: '合成企业导师', workStatus: '合成岗位工作正常',
  enterpriseFeedback: '合成企业反馈良好', facts: '合成巡访测试事实记录，不能作为真实巡访证明。' })
const visitDetail = (extra = {}) => ({ id: '100', batchId: target.batchId, internId: target.internshipId,
  studentName: '合成学生', version: 3, rectifyStatus: 'PENDING', attachment: null, ...extra })
const showReceipt = page => {
  page.vm.tab = 'visit'
  page.vm.visitReceipt = { visitId: '100', batchId: target.batchId, internshipId: target.internshipId, generation: 1, fileId: '' }
  page.vm.visitDetail = visitDetail()
}

async function renderPage(page) {
  const template = fs.readFileSync(new URL('../src/pages/teacher-internship/internship-review/index.vue', import.meta.url), 'utf8')
    .match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render = new Function('Vue', compile(template, { prefixIdentifiers: true }).code)(Vue)
  const app = createSSRApp({ render() { return render(page.vm, []) } })
  app.component('MobileGlobalState', { props: ['state'], render() { return this.state === 'ready' ? this.$slots.default?.() : h('div', '正在读取') } })
  app.component('InternshipVisitEvidenceForm', { props: ['target'], render() { return h('div', { 'data-visit-draft': this.target.internshipId }, '巡访草稿') } })
  for (const name of ['MobileNavBar', 'ReportFilePreview', 'MobileInlineAlert', 'MobileStatusTag', 'MobileSegmented', 'MobileSequentialQueue']) app.component(name, { render: () => null })
  return renderToString(app)
}

test('camera parent hide/show keeps the actual template draft while queues reload or fail', async () => {
  const queue = deferred(), page = load(false, { teacherApi: { getWeeklyReports: () => queue.promise, getInternshipVisitPlans: async () => result() } })
  page.vm.tab = 'visit'; page.vm.visitTarget = { ...target }
  const original = page.vm.visitTarget
  page.component.onHide.call(page.vm); page.component.onShow.call(page.vm)
  assert.equal(page.vm.visitTarget, original); assert.equal(page.vm.state, 'loading'); assert.equal(page.vm.data, null)
  assert.match(await renderPage(page), /data-visit-draft="9007199254741003"/)
  queue.reject(new Error('合成来源故障')); await flush()
  assert.match(await renderPage(page), /data-visit-draft="9007199254741003"/)
  page.logout(); page.component.onHide.call(page.vm); page.component.onShow.call(page.vm)
  assert.equal(page.vm.visitTarget, null)
})

test('saved receipt stays visible when unrelated page reload fails', async () => {
  const page = load(false); showReceipt(page); page.vm.state = 'error'; page.vm.data = null
  assert.match(await renderPage(page), /巡访已登记/)
})

test('followup keeps original note and version until a successful explicit comparison is adopted', async () => {
  const writes = []; let fail = false
  const page = load(false, { teacherInternshipEvidenceV3Api: {
    rectifyVisit: async (...args) => { writes.push(args); throw { httpStatus: 409 } },
    visitDetail: async () => { if (fail) throw new Error('合成回读失败'); return visitDetail({ version: 5 }) }
  } })
  showReceipt(page); page.vm.beginVisitFollow(); page.vm.visitFollowDraft.note = '合成整改跟进说明'
  await page.vm.submitVisitFollow('DONE')
  assert.deepEqual(writes[0], ['100', { batchId: target.batchId, expectedVersion: 3, status: 'DONE', note: '合成整改跟进说明' }])
  await page.vm.refreshVisitReceipt()
  assert.equal(page.vm.visitFollowDraft.version, 3); assert.equal(page.vm.visitFollowDraft.comparison.version, 5)
  fail = true; await page.vm.refreshVisitReceipt(); page.vm.adoptVisitFollow()
  assert.equal(page.vm.visitFollowDraft.version, 3); assert.equal(page.vm.visitFollowDraft.comparison, null)
  await page.vm.submitVisitFollow('DONE'); assert.equal(writes.length, 1)
  fail = false; await page.vm.refreshVisitReceipt(); page.vm.adoptVisitFollow()
  assert.equal(page.vm.visitFollowDraft.version, 5); assert.equal(page.vm.visitFollowDraft.note, '合成整改跟进说明')
  await page.vm.submitVisitFollow('DONE'); assert.equal(writes[1][1].expectedVersion, 5)
})

test('followup completed elsewhere cannot be adopted and late writes cannot replace another draft', async () => {
  const pending = deferred(), page = load(false, { teacherInternshipEvidenceV3Api: {
    rectifyVisit: () => pending.promise, visitDetail: async () => visitDetail({ version: 5, rectifyStatus: 'DONE' })
  } })
  showReceipt(page); page.vm.beginVisitFollow(); page.vm.visitFollowDraft.note = '合成跟进'
  page.vm.visitFollowDraft.conflict = true; await page.vm.refreshVisitReceipt(); page.vm.adoptVisitFollow()
  assert.equal(page.vm.visitFollowDraft.conflict, true); assert.equal(page.vm.visitFollowDraft.version, 3)
  page.vm.visitFollowDraft.conflict = false
  const writing = page.vm.submitVisitFollow('DONE')
  page.vm.invalidateReads(); page.vm.hidden = false
  page.vm.visitFollowDraft = { id: 'new', version: 8, note: '另一个草稿', conflict: false }; page.vm.visitActing = true
  pending.resolve({ id: '100', rectifyStatus: 'DONE' }); await writing
  assert.equal(page.vm.visitFollowDraft.id, 'new'); assert.equal(page.vm.visitActing, true); assert.equal(page.vm.visitFollowResult, '')
})

test('opening or saving another visit clears the earlier followup completion receipt', async () => {
  const page = load(false, { teacherApi: { getWeeklyReports: async () => ({ reports: [], abnormal: [] }), getInternshipVisitPlans: async () => result() },
    teacherInternshipEvidenceV3Api: { visitDetail: async id => visitDetail({ id }), createVisit: async () => ({ visitId: '102' }) } })
  showReceipt(page); page.vm.visitFollowResult = '上一条已完成'
  page.vm.focusVisitId = '101'; await page.vm.loadFocusedVisit()
  assert.equal(page.vm.visitReceipt.visitId, '101'); assert.equal(page.vm.visitFollowResult, '')
  page.vm.visitFollowResult = '上一条已完成'; page.vm.visitTarget = { ...target }
  await page.vm.submitVisit({ batchId: target.batchId, planId: target.planId, expectedVersion: 4, expectedPlanVersion: 2 })
  assert.equal(page.vm.visitReceipt.visitId, '102'); assert.equal(page.vm.visitFollowResult, '')
})

test('form reads the clicked batch, plan and student, preserving all large identifiers', async () => {
  const reads = [], page = load(true, { teacherInternshipEvidenceV3Api: { visitTargets: async (...args) => { reads.push(args); return result() } } })
  await page.vm.loadContext(); fill(page.vm); page.vm.submit()
  assert.deepEqual(reads, [[target.batchId, { planId: target.planId, internshipId: target.internshipId }]])
  const submitted = page.emitted[0][1]
  assert.equal(submitted.batchId, target.batchId); assert.equal(submitted.planId, target.planId)
  assert.equal(submitted.expectedVersion, 4); assert.equal(submitted.expectedPlanVersion, 2)
})

test('rereading changed versions preserves input and requires explicit adoption', async () => {
  const current = plan({ students: [{ ...target, resolvable: true, visited: false, expectedVersion: 7, expectedPlanVersion: 5 }] })
  const page = load(true, { teacherInternshipEvidenceV3Api: { visitTargets: async () => result([current]) } })
  fill(page.vm); page.vm.pendingEvidence = normalizeFileReadiness(photo)
  await page.vm.loadContext(); page.vm.submit()
  assert.equal(page.emitted.length, 0); assert.equal(page.vm.originalContext.expectedVersion, 4)
  page.vm.adoptContext(); page.vm.submit()
  assert.equal(page.emitted[1][1].expectedVersion, 7); assert.equal(page.emitted[1][1].expectedPlanVersion, 5)
  assert.deepEqual(page.emitted[1][1].fileIds, [photo.fileId]); assert.match(page.vm.form.facts, /合成巡访/)
})

test('wrong context and already visited targets cannot authorize another registration', async () => {
  for (const response of [result([], { batchId: 'other' }), result([plan({ students: [{ ...target, resolvable: true, visited: true }] })])]) {
    const page = load(true, { teacherInternshipEvidenceV3Api: { visitTargets: async () => response } })
    fill(page.vm); await page.vm.loadContext(); page.vm.submit()
    assert.equal(page.vm.contextState, 'error'); assert.equal(page.emitted.length, 0)
  }
})

test('late context after hide cannot replace a new comparison or release its lock', async () => {
  const old = deferred(), fresh = deferred(); let calls = 0
  const page = load(true, { teacherInternshipEvidenceV3Api: { visitTargets: () => ++calls === 1 ? old.promise : fresh.promise } })
  const first = page.vm.loadContext()
  page.vm.active = false; page.component.watch.active.call(page.vm, false)
  page.vm.active = true; page.component.watch.active.call(page.vm, true)
  old.resolve(result()); await first
  assert.equal(page.vm.reading, true); assert.equal(page.vm.latestContext, null)
  fresh.resolve(result()); await flush(); assert.equal(page.vm.contextState, 'ready')
})

test('camera temporary hide retains the same draft photo and upload lock ownership', async () => {
  const page = load(true); await page.vm.loadContext(); page.vm.choosePhoto()
  page.vm.active = false; page.component.watch.active.call(page.vm, false)
  await page.chooser().success({ tempFilePaths: ['private-photo.png'], tempFiles: [{ name: '合成巡访.png', size: 123 }] })
  assert.equal(page.vm.pendingEvidence.fileId, photo.fileId); assert.equal(page.vm.uploading, false)
  assert.equal(page.vm.submitDisabled, true)
  page.vm.active = true; page.component.watch.active.call(page.vm, true); await flush()
  assert.equal(page.vm.contextState, 'ready'); assert.equal(page.vm.pendingEvidence.fileId, photo.fileId)
})

test('account switch and unmount discard photo callbacks before uploading', async () => {
  for (const dispose of [page => page.logout(), page => page.component.beforeUnmount.call(page.vm)]) {
    let uploads = 0
    const page = load(true, { uploadBusinessFile: async () => { uploads++; return photo } })
    await page.vm.loadContext(); page.vm.choosePhoto(); dispose(page)
    await page.chooser().success({ tempFilePaths: ['private-photo.png'] })
    assert.equal(uploads, 0); assert.equal(page.vm.pendingEvidence, null)
  }
})

test('pending photo blocks submission and mismatched metadata cannot replace it', async () => {
  const page = load(true, { fileSdk: { metadata: async () => ({ ...photo, fileId: 'other' }) } })
  await page.vm.loadContext(); fill(page.vm)
  page.vm.pendingEvidence = normalizeFileReadiness({ ...photo, status: 'QUARANTINED', scanStatus: 'PENDING', readyForBusiness: false })
  page.vm.submit(); assert.equal(page.emitted.length, 0)
  await page.vm.refreshEvidence()
  assert.equal(page.vm.pendingEvidence.fileId, photo.fileId); assert.equal(page.vm.submitDisabled, true)
  assert.match(page.vm.photoError, /读取失败/)
})

test('plan and student pagination use backend totals and preserve exact targets', async () => {
  const calls = [], next = plan({ students: [{ ...target, internshipId: 'next', resolvable: true }], studentPage: 2, studentHasMore: false })
  const page = load(false, { teacherApi: { getInternshipVisitPlans: async (batch, options) => {
    calls.push([batch, options]); return options.planId ? result([next]) : result()
  } } })
  await page.vm.loadVisits(); assert.equal(page.vm.pendingVisitStudentCount, 25)
  const first = page.vm.visitPlans[0]; await page.vm.loadMoreVisitStudents(first)
  assert.deepEqual(calls[1], [target.batchId, { planId: target.planId, studentPage: 2, keyword: '' }])
  assert.equal(first.students.length, 2); assert.equal(first.studentHasMore, false)
  page.vm.openVisitForm(first.students[0], first)
  assert.equal(page.vm.visitTarget.planId, target.planId); assert.equal(page.vm.visitTarget.batchId, target.batchId)
  assert.equal(page.vm.visitTarget.expectedPlanVersion, 2)
})

test('late plan response after batch switch does not populate the new batch', async () => {
  const response = deferred(), page = load(false, { teacherApi: { getInternshipVisitPlans: () => response.promise } })
  const reading = page.vm.loadVisits(); await flush()
  page.vm.batchId = 'other'; page.vm.visitEpoch++; page.vm.visitPaging = false
  response.resolve(result()); await reading
  assert.equal(page.vm.visitPlans.length, 0); assert.equal(page.vm.visitPaging, false)
})

test('write success keeps receipt when reread fails and retries only rereading', async () => {
  let writes = 0, reads = 0
  const page = load(false, { teacherInternshipEvidenceV3Api: {
    createVisit: async () => { writes++; return { visitId: 'visit1', expectedVersion: 5 } },
    visitDetail: async () => { reads++; throw new Error('合成回读失败') }
  } })
  page.vm.visitTarget = { ...target }
  await page.vm.submitVisit({ batchId: target.batchId, planId: target.planId, expectedVersion: 4, expectedPlanVersion: 2 })
  assert.equal(page.vm.visitReceipt.visitId, 'visit1'); assert.equal(page.vm.visitTarget, null)
  assert.match(page.vm.visitResultError, /已登记/)
  await page.vm.refreshVisitReceipt(); assert.equal(writes, 1); assert.equal(reads, 2)
})

test('late write callback cannot close a later student draft or clear its new lock', async () => {
  const pending = deferred(), page = load(false, { teacherInternshipEvidenceV3Api: { createVisit: () => pending.promise } })
  page.vm.visitTarget = { ...target }
  const writing = page.vm.submitVisit({ batchId: target.batchId, planId: target.planId, expectedVersion: 4, expectedPlanVersion: 2 })
  page.vm.invalidateReads(); page.vm.hidden = false; page.vm.visitTarget = { ...target, internshipId: 'next' }; page.vm.visitActing = true
  pending.resolve({ visitId: 'old' }); await writing
  assert.equal(page.vm.visitTarget.internshipId, 'next'); assert.equal(page.vm.visitActing, true)
  assert.equal(page.vm.visitReceipt, null)
})

test('version conflict keeps the same target and blocks automatic retry', async () => {
  let writes = 0
  const page = load(false, { teacherInternshipEvidenceV3Api: { createVisit: async () => { writes++; throw { httpStatus: 409 } } } })
  page.vm.visitTarget = { ...target }
  const body = { batchId: target.batchId, planId: target.planId, expectedVersion: 4, expectedPlanVersion: 2 }
  await page.vm.submitVisit(body); await page.vm.submitVisit(body)
  assert.equal(writes, 1); assert.equal(page.vm.visitConflict, true); assert.equal(page.vm.visitTarget.expectedVersion, 4)
})

test('巡访标题必填，进入草稿不采集位置，拒绝或移除定位仍保留正文与照片', async () => {
  let capture, calls = 0
  const page = load(true, { uni: { getLocation: options => { calls++; capture = options } } })
  await page.vm.loadContext(); fill(page.vm); page.vm.pendingEvidence = normalizeFileReadiness(photo)
  assert.equal(calls, 0)
  for (const title of ['', ' 一 ']) { page.vm.form.title = title; page.vm.submit() }
  assert.equal(page.emitted.length, 0)
  page.vm.form.title = ' 合成岗位适应巡访 '
  page.vm.captureLocation(); assert.equal(page.vm.submitDisabled, true)
  capture.fail(); page.vm.submit()
  assert.equal(page.emitted[0][1].title, '合成岗位适应巡访')
  assert.equal(page.emitted[0][1].location, null)
  assert.deepEqual(page.emitted[0][1].fileIds, [photo.fileId])
  assert.match(page.vm.locationError, /正文和照片已保留/)
  page.vm.captureLocation(); capture.success({ latitude: 28.1, longitude: 112.2, accuracy: 8 })
  page.vm.submit(); const captured = page.emitted[1][1].location
  assert.equal(captured.consent, true); assert.equal(captured.latitude, 28.1)
  assert.equal(captured.coordinateSystem, checkinLocationPolicy(false).coordinateSystem)
  assert.ok(Number.isFinite(Date.parse(captured.capturedAt)))
  page.vm.removeLocation(); page.vm.submit(); assert.equal(page.emitted[2][1].location, null)
  assert.equal(page.vm.pendingEvidence.fileId, photo.fileId)
})

test('非法或迟到设备定位不进入当前巡访，也不覆盖新的定位请求', async () => {
  const changes = [p => p.logout(), p => { p.vm.active = false; p.component.watch.active.call(p.vm, false) },
    p => { p.vm.target = { ...target, internshipId: 'other' } }, p => p.component.beforeUnmount.call(p.vm), p => p.vm.removeLocation()]
  for (const change of changes) {
    let capture
    const p = load(true, { uni: { getLocation: options => { capture = options } } })
    await p.vm.loadContext(); p.vm.captureLocation(); change(p)
    capture.success({ latitude: 28.1, longitude: 112.2, accuracy: 8 })
    assert.equal(p.vm.location, null)
  }
  const callbacks = [], p = load(true, { uni: { getLocation: o => callbacks.push(o) } })
  await p.vm.loadContext(); fill(p.vm)
  p.vm.captureLocation(); callbacks[0].success({ latitude: NaN, longitude: 112, accuracy: 8 })
  assert.equal(p.vm.location, null); assert.match(p.vm.locationError, /完整有效/)
  p.vm.captureLocation(); p.vm.removeLocation(); p.vm.captureLocation()
  callbacks[1].success({ latitude: 1, longitude: 2, accuracy: 3 })
  assert.equal(p.vm.locating, true); assert.equal(p.vm.location, null)
  callbacks[2].success({ latitude: 28.1, longitude: 112.2, accuracy: 8 })
  assert.equal(p.vm.location.latitude, 28.1)
})

test('企业查询只在明确执行后生效，计划页与学生页沿用同一查询，旧响应不回填', async () => {
  const calls = [], old = deferred()
  const p = load(false, { teacherApi: { getInternshipVisitPlans: async (batch, options) => {
    calls.push(options)
    if (options.keyword === '旧企业') return old.promise
    return result([plan({ id: options.page === 2 ? 'next-plan' : target.planId })], { page: options.page || 1, hasMore: !options.planId })
  } } })
  p.vm.visitKeyword = '  合成企业%_  '; p.vm.searchVisitTargets(); await flush()
  p.vm.visitKeyword = '尚未查询的另一企业'
  await p.vm.loadVisits({ append: true }); await p.vm.loadMoreVisitStudents(p.vm.visitPlans[0])
  assert.deepEqual(calls.map(c => c.keyword), ['合成企业%_', '合成企业%_', '合成企业%_'])
  p.vm.visitSearch = '旧企业'; const reading = p.vm.loadVisits(); await flush()
  p.vm.visitSearch = '合成企业%_'; await p.vm.loadVisits()
  old.resolve(result([plan({ id: 'stale-plan' })])); await reading
  assert.equal(p.vm.visitPlans.some(plan => plan.id === 'stale-plan'), false)
})

test('教师位置披露绑定原单用途与版本，错误明确提示，切对象或账号丢弃明文', async () => {
  const coords = { latitude: 28.1, longitude: 112.2, accuracyM: 8 }, reads = []
  const p = load(false, { teacherInternshipEvidenceV3Api: { visitLocation: async (...args) => {
    reads.push(args); return { visitId: '100', batchId: target.batchId, location: coords }
  } } }); showReceipt(p)
  await p.vm.readVisitLocation(); assert.equal(reads.length, 0)
  Object.assign(p.vm.visitDetail, { hasLocation: true, canViewLocation: true })
  await p.vm.readVisitLocation(); assert.deepEqual(p.vm.visitLocation, coords)
  assert.deepEqual(reads[0], ['100', { batchId: target.batchId, expectedVersion: 3, reason: '核对本次巡访发生位置' }])
  p.vm.tab = 'weekly'; p.component.watch.tab.call(p.vm); assert.equal(p.vm.visitLocation, null)
  for (const response of [{ visitId: 'other', batchId: target.batchId }, { visitId: '100', batchId: 'other' }]) {
    const wrong = load(false, { teacherInternshipEvidenceV3Api: { visitLocation: async () => response } }); showReceipt(wrong)
    Object.assign(wrong.vm.visitDetail, { hasLocation: true, canViewLocation: true })
    await wrong.vm.readVisitLocation(); assert.equal(wrong.vm.visitLocation, null); assert.match(wrong.notices[0], /不一致/)
  }
  for (const change of [p => p.logout(), p => p.vm.invalidateReads(), p => { p.vm.batchId = 'other' },
    p => { p.vm.visitDetail = visitDetail({ id: 'other' }); p.vm.clearVisitLocation() }]) {
    const later = deferred(), q = load(false, { teacherInternshipEvidenceV3Api: { visitLocation: () => later.promise } }); showReceipt(q)
    Object.assign(q.vm.visitDetail, { hasLocation: true, canViewLocation: true })
    const reading = q.vm.readVisitLocation(); change(q)
    later.resolve({ visitId: '100', batchId: target.batchId, location: coords }); await reading
    assert.equal(q.vm.visitLocation, null)
  }
})
