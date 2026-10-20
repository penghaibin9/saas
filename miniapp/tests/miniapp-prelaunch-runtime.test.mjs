import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { reactive, computed } from 'vue'
import { createPinia, defineStore, setActivePinia } from 'pinia'
import { createNetworkPager } from '../src/utils/networkPager.js'
import { teacherServices } from '../src/services/teacherServiceCatalog.mjs'
import { roleConfigs } from '../src/config/roles.config.js'
import { receiptTitle, receiptNodeTitle } from '../src/pages/student/my-work/presentation.mjs'

function component(path, deps) {
  const source = readFileSync(new URL('../src/' + path, import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\s*$/gm, '').replace('export default', 'module.exports =')
  const context = { module: { exports: {} }, receiptTitle, receiptNodeTitle, toast() {}, normalizeError: () => ({ pageState: 'error' }), ...deps }
  vm.runInNewContext(source, context)
  const options = context.module.exports, data = reactive(options.data()), page = {}
  for (const key of Object.keys(data)) Object.defineProperty(page, key, { get: () => data[key], set: value => { data[key] = value } })
  for (const [key, fn] of Object.entries(options.methods || {})) page[key] = fn.bind(page)
  for (const [key, fn] of Object.entries(options.computed || {})) {
    const value = computed(() => fn.call(page))
    Object.defineProperty(page, key, { get: () => value.value })
  }
  return { page, options }
}
const tick = () => new Promise(resolve => setImmediate(resolve))
const deferred = (calls, params) => new Promise((resolve, reject) => calls.push({ params, resolve, reject }))
function cases() {
  const calls = []; let generation = 1
  const result = component('pages/student/my-work/index.vue', {
    createNetworkPager, currentSessionGeneration: () => generation,
    studentApi: { getCases: (...params) => deferred(calls, params) }
  })
  return { ...result, calls, changeSession: () => generation++ }
}
const receipt = id => ({ items: [{ caseId: id }], tabs: [{ key: id }], nextCursor: '' })

test('student receipts notify Vue when the next page is appended', async () => {
  const { page, calls } = cases()
  const visibleCount = computed(() => page.items.length)
  const first = page.refresh()
  calls[0].resolve({ ...receipt('first'), nextCursor: 'page-2' }); await first
  assert.equal(visibleCount.value, 1)
  const more = page.loadMore(); calls[1].resolve(receipt('second')); await more
  assert.equal(visibleCount.value, 2)
})

test('student receipts ignore old category successes and failures', async () => {
  for (const rejectOld of [false, true]) {
    const { page, calls } = cases()
    const old = page.refresh(); page.switchTab('done')
    calls[1].resolve(receipt('done')); await tick()
    if (rejectOld) calls[0].reject(new Error('old network failure'))
    else calls[0].resolve(receipt('all'))
    await old
    assert.equal(page.items[0]?.caseId, 'done')
    assert.equal(page.tabs[0].key, 'done')
    assert.equal(page.state, 'ready')
  }
})

test('student receipts refresh on return and reject hidden or former-session responses', async () => {
  const { page, options, calls, changeSession } = cases()
  const old = page.refresh(); options.onHide.call(page)
  calls[0].resolve(receipt('hidden')); await old
  assert.equal(page.items.length, 0)
  options.onShow.call(page); calls[1].resolve(receipt('returned')); await tick()
  assert.equal(page.items[0].caseId, 'returned')
  const prior = page.refresh(); changeSession(); page.refresh()
  calls[3].resolve(receipt('new-account')); await tick()
  calls[2].resolve(receipt('old-account')); await prior
  assert.equal(page.items[0].caseId, 'new-account')
})

test('receipt details re-read after editing the original application and clear failed actions', async () => {
  const calls = []
  const { page, options } = component('pages/student/my-work/detail.vue', {
    currentSessionGeneration: () => 1,
    studentApi: { getCaseDetail: id => deferred(calls, id) }
  })
  page.caseId = 'application-1'
  const first = page.load(); calls[0].resolve({ statusGroup: 'returned' }); await first
  options.onHide.call(page); options.onShow.call(page)
  calls[1].resolve({ statusGroup: 'processing' }); await tick()
  assert.equal(page.row.statusGroup, 'processing')
  const failed = page.load(); calls[2].reject(new Error('forbidden')); await failed
  assert.equal(page.row, null)
})

test('internship services keep weekly, exception and visit destinations distinct', () => {
  const items = teacherServices(roleConfigs.intern_mentor, 'intern_mentor', { can: () => true })
  for (const key of ['weekly', 'checkin', 'visit']) assert.ok(items.some(row => row.key === key), key)
  assert.equal(items.find(row => row.key === 'checkin').path.endsWith('?tab=abnormal'), true)
  assert.equal(items.find(row => row.key === 'visit').path.endsWith('?tab=visit'), true)
})

function internship() {
  const calls = []
  const context = { loaded: true, selectedBatchId: 'A', batches: [{ id: 'A' }, { id: 'B' }], selectBatch(id) { this.selectedBatchId = id; return true } }
  const result = component('pages/teacher-internship/internship-review/index.vue', {
    currentSessionGeneration: () => 1, useInternshipContextStore: () => context,
    InternshipVisitEvidenceForm: {}, MobileSequentialQueue: {}, listPaging: () => ({}),
    teacherApi: { getWeeklyReports: params => deferred(calls, params), getInternshipVisitPlans: async () => ({ plans: [] }) }
  })
  result.page.pagedReset = () => {}; result.page.pagedLoadMore = () => {}
  return { ...result, calls, context }
}
const queue = id => ({ batchId: id, reports: [{ id: id + '-report' }], abnormal: [], pagination: {} })

test('no authorized internship batch is an explicit empty state, not a network failure', async () => {
  const { page, calls, context } = internship()
  context.selectedBatchId = ''; context.batches = []
  await page.load()
  assert.equal(calls.length, 0)
  assert.equal(page.state, 'empty')
  assert.match(page.loadError, /指导范围内没有实习批次/)
  assert.equal(page.data, null)
})

test('internship batch changes discard an earlier queue without selecting its batch again', async () => {
  const { page, calls, context } = internship()
  const old = page.load(); await tick()
  context.selectBatch('B'); const fresh = page.load(); await tick()
  calls[1].resolve(queue('B')); await fresh
  calls[0].resolve(queue('A')); await old
  assert.equal(page.batchId, 'B'); assert.equal(context.selectedBatchId, 'B')
  assert.equal(page.data.reports[0].id, 'B-report')
})

test('internship pagination cannot append the previous batch into a new batch', async () => {
  const { page, calls, context } = internship()
  const first = page.load(); await tick(); calls[0].resolve(queue('A')); await first
  page.pagerShown = 20; page.data.pagination = { weeklyHasMore: true, weeklyPage: 1 }
  const more = page.loadMoreQueue('weekly'); await tick()
  context.selectBatch('B'); const fresh = page.load(); await tick()
  calls[2].resolve(queue('B')); await fresh
  calls[1].resolve(queue('A')); await more
  assert.deepEqual(Array.from(page.data.reports, row => row.id), ['B-report'])
})

test('internship service deep links select their requested tab', async () => {
  const { page, options, calls } = internship()
  options.onLoad.call(page, { tab: 'abnormal' }); await tick()
  assert.equal(page.tab, 'abnormal')
  calls[0].resolve(queue('A')); await tick()
})

function topics() {
  const calls = []
  const result = component('pages/student/graduation/topics/index.vue', {
    currentSessionGeneration: () => 1,
    createSubmitLock: () => ({ run: fn => fn() }),
    studentApi: { getGraduationTopics: params => deferred(calls, params) }
  })
  result.page.batchId = 'batch-1'
  return { ...result, calls }
}
test('graduation category changes during a request actually load the new category', async () => {
  const { page, calls } = topics()
  const old = page.loadTopics(true)
  page.chooseCategory('设计')
  assert.equal(calls.length, 2)
  assert.equal(calls[1].params.category, '设计')
  calls[1].resolve({ items: [{ id: 'new' }] }); await tick()
  calls[0].resolve({ items: [{ id: 'old' }] }); await old
  assert.equal(page.topics[0].id, 'new'); assert.equal(page.topicLoading, false)
})

test('graduation old filter failure cannot clear the current topic list', async () => {
  const { page, calls } = topics()
  const old = page.loadTopics(true); page.chooseCategory('设计')
  assert.equal(calls.length, 2)
  calls[1].resolve({ items: [{ id: 'new' }] }); await tick()
  calls[0].reject(new Error('old failure')); await old
  assert.equal(page.topics[0].id, 'new'); assert.equal(page.topicError, '')
})

test('student internship writing pages keep the batch selected on the service entry', async () => {
  for (const path of ['pages/student/weekly-report/index.vue', ...['process-report', 'leave', 'makeup', 'self-eval'].map(name => `pages/student-internship/${name}/index.vue`)]) {
    const calls = []
    const { page, options } = component(path, {
      uni: { setNavigationBarTitle() {} },
      MobileInlineAlert: {},
      studentApi: { getInternship: async batch => { calls.push(batch); throw new Error('stop before business read') } }
    })
    options.onLoad.call(page, { batchId: '9007199254740993' }); await tick()
    assert.equal(calls[0], '9007199254740993', path)
  }
})

test('out-of-order internship queues cannot overwrite exception lock versions', async () => {
  const calls = []
  const source = readFileSync(new URL('../src/services/teacherSequentialV3Api.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/export /g, '')
  const context = { realRequest: (url, options) => deferred(calls, { url, options }), encodeURIComponent }
  vm.runInNewContext(source + '\nthis.api = {getInternshipReviewQueue, handleCheckin}', context)
  const old = context.api.getInternshipReviewQueue({ batchId: 'A' }).catch(error => error)
  const fresh = context.api.getInternshipReviewQueue({ batchId: 'B' })
  calls[1].resolve({ abnormalCheckins: [{ id: '1', version: 3 }] }); await fresh
  calls[0].resolve({ abnormalCheckins: [{ id: '1', version: 1 }] }); await old
  const write = context.api.handleCheckin('1', 'REASONABLE', '核实情况属实')
  assert.equal(calls[2].params.options.data.expectedVersion, 3)
  calls[2].resolve({}); await write
})

test('release gate distinguishes SVG namespace identifiers from cleartext network addresses', () => {
  const source = readFileSync(new URL('../scripts/finalize-mp-weixin-release.mjs', import.meta.url), 'utf8')
  const fn = new Function(source.match(/function hasCleartextNetworkAddress[\s\S]*?\n}/)[0] + '; return hasCleartextNetworkAddress')()
  assert.equal(fn('<svg xmlns="http://www.w3.org/2000/svg">'), false)
  assert.equal(fn(JSON.stringify('<svg xmlns="http://www.w3.org/2000/svg">')), false)
  assert.equal(fn('http://api.school.test'), true)
  assert.equal(fn('http://www.w3.org/2000/svg'), true)
  assert.equal(fn('<svg xmlns="http://www.w3.org/2000/svg"><image href="http://api.school.test"/>'), true)
  assert.equal(fn('http://localhost.evil.test/api'), true)
  assert.equal(fn('http://127.0.0.1:8000/api'), false)
})

test('a previous identity cannot restore or clear the new internship context', async () => {
  for (const failOld of [false, true]) {
    const calls = []; let generation = 1
    const source = readFileSync(new URL('../src/stores/internshipContext.js', import.meta.url), 'utf8')
      .replace(/^import .*$/gm, '').replace('export const', 'const').replace('export default useInternshipContextStore', 'return useInternshipContextStore')
    const useStore = new Function('defineStore', 'teacherInternshipContext', 'uni', 'currentSessionGeneration', 'sessionChangedError', source)(
      defineStore, () => deferred(calls), { getStorageSync() {}, setStorageSync() {}, removeStorageSync() {} },
      () => generation, () => ({ code: 'SESSION_CHANGED' }))
    setActivePinia(createPinia()); const context = useStore()
    const old = context.load().catch(error => error)
    generation++; context.clear()
    const fresh = context.load()
    assert.equal(calls.length, 2, 'new identity must not join the old request')
    calls[1].resolve({ roleCode: 'new-role', permissionPatterns: ['internship.new'], batches: [{ id: 'B' }], defaultBatchId: 'B' })
    await fresh
    if (failOld) calls[0].reject(new Error('old context failed'))
    else calls[0].resolve({ roleCode: 'old-role', permissionPatterns: ['internship.old'], batches: [{ id: 'A' }], defaultBatchId: 'A' })
    await old
    assert.equal(context.loaded, true); assert.equal(context.selectedBatchId, 'B')
    assert.deepEqual(Array.from(context.permissionPatterns), ['internship.new'])
  }
})
