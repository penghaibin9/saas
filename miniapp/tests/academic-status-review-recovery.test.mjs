import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const dir = new URL('../src/pages/teacher/academic-affairs/', import.meta.url)
const deferred = () => { let resolve; return { promise: new Promise(yes => { resolve = yes }), resolve: value => resolve(value) } }
function harness(done = async () => ({ items: [], total: 0 })) {
  const storage = new Map()
  const identity = { key: 'teacher-A' }
  let writes = 0
  const context = vm.createContext({
    teacherWriteContext: () => identity.key, useSessionStore: () => ({}), toast() {},
    uni: { getStorageSync: key => storage.get(key), setStorageSync: (key, value) => storage.set(key, value), removeStorageSync: key => storage.delete(key) },
    getDoneApprovals: done,
    teacherApi: { getStatusChangePending: async () => ({ list: [] }), reviewStatusChange: async () => { writes++; return {} } }
  })
  for (const file of ['approval-recovery.js', 'status-review-recovery.js']) {
    const source = readFileSync(new URL(file, dir), 'utf8').replace(/^import .*$/gm, '').replace(/export (function|const) /g, '$1 ')
    vm.runInContext(source, context)
  }
  const source = readFileSync(new URL('status-change-review.vue', dir), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(source, context)
  const helpers = vm.runInContext('({createApprovalAttempt, persistApprovalAttempt, restoreApprovalAttempts, matchCompletedStatusTask})', context)
  function mount() {
    const component = context.component, page = component.data()
    for (const [key, fn] of Object.entries(component.methods)) page[key] = fn.bind(page)
    for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(page, key, { get: () => fn.call(page) })
    page._pageActive = true
    page.restoreReviewAttempts()
    return page
  }
  const scope = 'status-change-review'
  const attempt = helpers.createApprovalAttempt(scope, identity.key, '43', 'APPROVE', { currentTaskId: '801', currentNode: 'COUNSELOR_REVIEW' })
  assert.equal(helpers.persistApprovalAttempt(scope, attempt), true)
  return { mount, identity, attempt, helpers, storage, writes: () => writes, pending: () => helpers.restoreApprovalAttempts(scope, 'teacher-A').attempts }
}
const task = { taskId: '801', sourceModule: 'academic-affairs', sourceBizType: 'AA_STATUS_CHANGE', sourceBizId: '43', nodeCode: 'COUNSELOR_REVIEW', status: 'APPROVED', submittedAt: '2026-09-09T01:00:00', actedAt: '2026-09-09T02:00:00' }

test('completed todo deep links read the exact personal receipt and cannot submit another approval', async () => {
  const h = harness(async () => ({ items: [task, { ...task, taskId: 'other', sourceBizId: '143' }] })), page = h.mount()
  page.reviewAttempts = {}; page.targetChangeId = '43'
  await page.load()
  assert.equal(page.completedTasks.length, 1)
  assert.equal(page.completedTasks[0].taskId, '801')
  assert.equal(page.targetUnavailable, false)
  page.doAct({ changeId: '43' }, 'APPROVE')
  assert.equal(h.writes(), 0)
  assert.equal(page.backToQueue(), false)
  assert.equal(page.completedTasks.length, 0)
})

test('missing completed records do not silently display an unrelated pending queue', async () => {
  const h = harness(), page = h.mount()
  page.reviewAttempts = {}; page.targetChangeId = '43'
  await page.load()
  assert.equal(page.completedTasks.length, 0); assert.equal(page.targetUnavailable, true)
  page.doAct({ changeId: '43' }, 'APPROVE'); assert.equal(h.writes(), 0)
})

test('a completed-detail response arriving after hiding the page cannot populate it', async () => {
  const response = deferred(), h = harness(() => response.promise), page = h.mount()
  page.reviewAttempts = {}; page.targetChangeId = '43'
  const loading = page.load(); await Promise.resolve(); page._pageActive = false
  response.resolve({ items: [task] }); await loading
  assert.equal(page.completedTasks.length, 0)
})

test('workbench recordId deep links preserve the exact approval object', () => {
  for (const file of ['status-change-review.vue', 'schedule-change-review.vue']) {
    const source = readFileSync(new URL(file, dir), 'utf8')
    assert.match(source, /options\.id\s*\|\|\s*options\.changeId\s*\|\|\s*options\.recordId/)
  }
})

test('reload recovers only the exact completed task, without replaying a write', async () => {
  const h = harness(async () => ({ items: [task], total: 1 })), page = h.mount()
  assert.equal(page.unresolvedCount, 1)
  await page.load()
  assert.equal(page.unresolvedCount, 0)
  assert.equal(h.pending().length, 0)
  assert.match(page.recoveredNotice, /正式任务 801.*单据 43 已通过/)
  assert.equal(h.writes(), 0)
  assert.equal(h.mount().unresolvedCount, 0)
})
for (const patch of [{ taskId: '802' }, { sourceBizId: '44' }, { sourceModule: 'student-affairs' }, { sourceBizType: 'LEAVE' }, { nodeCode: 'COLLEGE_REVIEW' }, { status: 'REJECTED' }, { actedAt: null }]) {
  test(`unrelated or incomplete formal task remains pending: ${JSON.stringify(patch)}`, async () => {
    const h = harness(async () => ({ items: [{ ...task, ...patch }], total: 1 })), page = h.mount()
    await page.load()
    assert.equal(page.unresolvedCount, 1)
    assert.equal(h.pending().length, 1)
    assert.equal(page.recoveredNotice, '')
    assert.equal(h.writes(), 0)
  })
}
for (const invalidation of ['identity', 'hide', 'new-load']) {
  test(`a delayed done queue cannot clear another context after ${invalidation}`, async () => {
    const response = deferred(), h = harness(() => response.promise), page = h.mount()
    const running = page.load()
    await Promise.resolve()
    if (invalidation === 'identity') h.identity.key = 'teacher-B'
    if (invalidation === 'hide') page._pageActive = false
    if (invalidation === 'new-load') page._loadEpoch++
    response.resolve({ items: [task], total: 1 }); await running
    assert.equal(h.pending().length, 1)
    assert.equal(page.recoveredNotice, '')
    assert.equal(h.writes(), 0)
  })
}
test('network failure and a failed storage removal both retain recovery references', async () => {
  const h = harness(async () => { throw new Error('timeout') }), page = h.mount()
  await page.load()
  assert.equal(h.pending().length, 1)
  assert.match(page.unresolvedAttempts[0].observation, /读取失败/)
  const saved = harness(async () => ({ items: [task], total: 1 })), other = saved.mount()
  saved.storage.delete = () => { throw new Error('storage unavailable') }
  await other.load()
  assert.equal(other.recoveryStorageBlocked, true)
  assert.equal(saved.pending().length, 1)
})
test('legacy references require a complete unique history in the attempt time window', () => {
  const h = harness(), started = Date.parse('2026-09-09T01:30:00Z')
  const attempt = { ...h.attempt, beforeTaskId: undefined, attemptKey: `${started.toString(36)}-old-attempt` }
  const match = page => h.helpers.matchCompletedStatusTask(attempt, page)
  assert.equal(match({ items: [task], total: 1 }).taskId, '801')
  assert.equal(match({ items: [task], total: 101 }), null)
  assert.equal(match({ items: [task, { ...task, taskId: '802' }], total: 2 }), null)
  assert.equal(match({ items: [{ ...task, actedAt: '2026-09-09T01:00:00' }], total: 1 }), null)
  assert.equal(match({ items: [{ ...task, submittedAt: '2026-09-09T02:00:00' }], total: 1 }), null)
})

test('the real approval adapter exposes recovery fields and labels status-change returns without changing other domains', async () => {
  const source = readFileSync(new URL('../src/services/approvalApi.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/export (async )?function /g, '$1function ')
  const context = vm.createContext({ realRequest: async () => ({ items: [
    { ...task, status: 'TRANSFERRED' }, { ...task, sourceBizType: 'LEAVE', status: 'TRANSFERRED' }
  ], total: 2 }) })
  vm.runInContext(source, context)
  const result = await vm.runInContext("getDoneApprovals(1, 100, '43', 'AA_STATUS_CHANGE')", context)
  assert.equal(result.items[0].status, 'RETURNED')
  assert.equal(result.items[1].status, 'TRANSFERRED')
  assert.equal(result.items[0].nodeCode, task.nodeCode)
  assert.equal(result.items[0].actedAt, task.actedAt)
  assert.equal(result.items[0].sourceModule, task.sourceModule)
})
