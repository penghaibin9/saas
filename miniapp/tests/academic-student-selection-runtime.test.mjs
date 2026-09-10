import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

const stateSource = readFileSync(new URL('../src/pages/student/academic-affairs/selection-state.js', import.meta.url), 'utf8')
const helpers = await import(`data:text/javascript;base64,${Buffer.from(stateSource).toString('base64')}`)
const source = readFileSync(new URL('../src/pages/student/academic-affairs/selection.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const course = (id = 'a', mode = 'FCFS', actions = ['ENROLL']) => ({ selectionCourseId: id, courseName: id, allowedActions: actions, lottery: { mode }, remain: null })
const group = (batch = 'A', courses = [course()]) => ({ batch: { batchId: batch, batchName: batch }, courses })
const record = (status, id = 'a', batchId = 'A') => ({ recordId: 'r', batchId, selectionCourseId: id, status })

function mount(overrides = {}) {
  let generation = 1
  let command = 0
  let failSaves = false
  const dialogs = [], toasts = [], calls = [], saved = []
  let ledger = null
  const studentApi = {
    getSelectionCourses: async () => [group()], getMySelections: async () => [],
    preflightSelection: async () => ({ allowed: true }),
    preflightDropSelection: async id => ({ allowed: true, action: 'DROP', selectionCourseId: id, batchId: 'A', selectionRecordId: 'r' }),
    enrollSelection: async id => { calls.push(['enroll', id]); return { recordId: 'r' } },
    dropSelection: async id => { calls.push(['drop', id]); return { recordId: 'r' } },
    ...overrides
  }
  const context = {
    ...helpers, studentApi, bookIcon: '', currentSessionGeneration: () => generation,
    readPending: () => ledger, savePending: (_key, value) => { if (failSaves) return false; ledger = value; saved.push(value); return true },
    createPendingCommand: (_scope, value) => ({ ...value, commandId: 'cmd-' + (++command), _pendingOwner: 'test-owner' }),
    canUpdatePendingCommand: () => true,
    AcademicPageNav: {}, AcademicPageState: {}, MobileAcademicDecisionCard: {}, normalizeError: e => ({ text: e.message || '业务拒绝' }),
    toast: text => toasts.push(text), uni: { showModal: dialog => dialogs.push(dialog), showToast: value => toasts.push(value.title) }
  }
  vm.runInNewContext(script, context)
  const definition = context.component
  const page = definition.data()
  for (const [name, fn] of Object.entries(definition.methods)) page[name] = fn.bind(page)
  for (const [name, get] of Object.entries(definition.computed)) Object.defineProperty(page, name, { get: () => get.call(page) })
  page.activeBatchId = 'A'; page.courseCache.A = [group()]; page.recordCache.A = []
  page.courseState = 'ready'; page.recordsState = 'ready'; page.loaded = true
  return { page, definition, dialogs, toasts, calls, saved, failStorage: () => { failSaves = true }, switchIdentity: () => { generation += 1 } }
}

test('canonical lottery.mode and null capacity snapshots retain their actual meaning', () => {
  const { page } = mount()
  assert.equal(page.isLottery(course('a', 'LOTTERY')), true)
  assert.equal(page.remain({ remain: null, capacity: 20, selectedCount: 3 }), null)
  assert.equal(page.remain({ capacity: null, selectedCount: null }), null)
  assert.equal(page.remain({ remain: 0 }), 0)
})

test('an acknowledged lottery POST reads personal records and never emits seat success', async () => {
  const { page, dialogs, toasts, calls } = mount({ getMySelections: async () => [record('PENDING_LOTTERY')] })
  page.courseCache.A = [group('A', [course('a', 'LOTTERY')])]
  page.enroll(page.activeGroups[0].courses[0])
  await dialogs[0].success({ confirm: true })
  assert.equal(calls.length, 1)
  assert.equal(page.receipt.status, 'PENDING_LOTTERY')
  assert.equal(page.receipt.label, '已报名待抽签')
  assert.equal(page.confirmedRecords.length, 0)
  assert.ok(!toasts.includes('选课成功'))
})

for (const ack of [null, { recordId: 'another-record' }]) {
  test(`a live read cannot settle the original POST with ${ack ? 'a different' : 'no'} receipt`, async () => {
    let writes = 0
    const { page, dialogs } = mount({ enrollSelection: async () => { writes += 1; return ack }, getMySelections: async () => [record('SELECTED')] })
    page.enroll(page.activeGroups[0].courses[0])
    await dialogs[0].success({ confirm: true })
    assert.equal(page.activeRecords[0].status, 'SELECTED')
    assert.equal(page.receipt.status, 'RESULT_UNKNOWN')
    assert.ok(page.unresolved['A:a'])
    page.enroll(page.activeGroups[0].courses[0])
    assert.equal(writes, 1)
  })
}

test('failed ledger cleanup keeps the original selection blocker until it can be persisted', () => {
  const { page, failStorage } = mount()
  page.unresolved = { 'A:a': { commandId: 'cmd-1', operation: 'ENROLL', selectionCourseId: 'a', batchId: 'A', returnedId: 'r', recoveryOnly: true } }
  failStorage()
  page.reconcilePending([record('SELECTED')], 'A')
  assert.ok(page.unresolved['A:a'])
  assert.equal(page.receipt, null)
  assert.match(page.decisionError.message, /无法安全清除/)
})

test('an ACK persists its original selection record ID before readback', async () => {
  const { page, dialogs, saved } = mount({
    enrollSelection: async () => ({ recordId: 'r' }),
    getMySelections: async () => [record('SELECTED')]
  })
  page.enroll(page.activeGroups[0].courses[0])
  await dialogs[0].success({ confirm: true })
  assert.ok(saved.some(value => value['A:a']?.returnedId === 'r'))
})

test('cold recovery clears only a record tied to its stored original ACK', () => {
  const { page } = mount()
  page.unresolved = {
    'A:a': { commandId: 'cmd-1', operation: 'ENROLL', selectionCourseId: 'a', selectionRecordId: '', batchId: 'A', returnedId: 'r', recoveryOnly: true },
    'A:b': { commandId: 'cmd-2', operation: 'ENROLL', selectionCourseId: 'b', selectionRecordId: '', batchId: 'A', returnedId: '', recoveryOnly: true }
  }
  page.reconcilePending([record('SELECTED', 'a'), record('SELECTED', 'b')], 'A')
  assert.equal(page.unresolved['A:a'], undefined)
  assert.ok(page.unresolved['A:b'])
})

test('timed-out enroll plus empty GET stays unresolved across navigation and cannot be replayed', async () => {
  const { page, dialogs, calls } = mount({ enrollSelection: async id => { calls.push(['enroll', id]); throw { errMsg: 'request:fail timeout' } } })
  page.enroll(page.activeGroups[0].courses[0])
  await dialogs[0].success({ confirm: true })
  assert.equal(page.receipt.status, 'RESULT_UNKNOWN')
  await page.switchBatch('B')
  await page.switchBatch('A')
  page.enroll(page.activeGroups[0].courses[0])
  assert.equal(dialogs.length, 1)
  assert.equal(calls.length, 1)
  assert.equal(page.receipt.status, 'RESULT_UNKNOWN')
})

test('old SELECTED record after DROP is not a successful receipt', async () => {
  const target = course('a', 'FCFS', ['DROP'])
  const { page, dialogs, toasts } = mount({ getMySelections: async () => [record('SELECTED')] })
  page.courseCache.A = [group('A', [target])]; page.recordCache.A = [record('SELECTED')]
  page.drop(target)
  await dialogs[0].success({ confirm: true })
  assert.equal(page.receipt.status, 'RESULT_UNKNOWN')
  assert.equal(toasts.length, 0)
})

test('DROP preflight must match the confirmed record and batch before sending the command', async () => {
  const target = course('a', 'FCFS', ['DROP'])
  const { page, dialogs, calls } = mount({
    getMySelections: async () => [record('SELECTED')],
    preflightDropSelection: async id => { calls.push(['drop-preflight', id]); return { allowed: true, action: 'DROP', selectionCourseId: id, batchId: 'A', selectionRecordId: 'r' } }
  })
  page.courseCache.A = [group('A', [target])]; page.recordCache.A = [record('SELECTED')]
  page.drop(target)
  await dialogs[0].success({ confirm: true })
  assert.deepEqual(calls.slice(0, 2), [['drop-preflight', 'a'], ['drop', 'a']])
})

test('wrong or late DROP preflight never submits a command for a changed object', async () => {
  const target = course('a', 'FCFS', ['DROP'])
  const pending = deferred()
  const { page, dialogs, calls } = mount({ preflightDropSelection: () => pending.promise })
  page.courseCache.A = [group('A', [target])]; page.recordCache.A = [record('SELECTED')]
  page.drop(target)
  const completion = dialogs[0].success({ confirm: true })
  await Promise.resolve()
  page.invalidateContext()
  pending.resolve({ allowed: true, action: 'DROP', selectionCourseId: 'a', batchId: 'A', selectionRecordId: 'r' })
  await completion
  assert.equal(calls.filter(([name]) => name === 'drop').length, 0)
})

test('DROP preflight 403 clears private selection state and sends no drop command', async () => {
  const target = course('a', 'FCFS', ['DROP'])
  const { page, dialogs, calls, saved } = mount({
    preflightDropSelection: async () => { throw { biz: true, code: 403, httpStatus: 403, message: '无权办理' } }
  })
  page.courseCache.A = [group('A', [target])]; page.recordCache.A = [record('SELECTED')]
  page.batchCatalog = [{ batchId: 'A', batchName: '当前批次' }]
  page.detailId = 'a'; page.unresolved = { 'A:stale': { operation: 'ENROLL', selectionCourseId: 'stale', batchId: 'A', returnedId: 'r-private', courseName: 'Private course name' } }
  page.drop(target)
  await dialogs[0].success({ confirm: true })
  assert.equal(calls.filter(([name]) => name === 'drop').length, 0)
  assert.equal(Object.keys(page.courseCache).length, 0)
  assert.equal(Object.keys(page.recordCache).length, 0)
  assert.equal(Object.keys(page.unresolved).length, 0)
  assert.equal(page.batchCatalog.length, 0)
  assert.equal(page.detailId, '')
  assert.equal(page.activeBatchId, '')
  assert.equal(page.courseState, 'error'); assert.equal(page.recordsState, 'error')
  assert.equal(page.decisionError.restricted, true)
  assert.equal(page.pageState, 'forbidden')
  assert.equal(saved.length, 1)
  assert.equal(saved[0]['A:stale'].selectionCourseId, 'stale')
  assert.equal(saved[0]['A:stale'].returnedId, 'r-private')
  assert.equal(saved[0]['A:stale'].courseName, undefined)
  await page.load()
  assert.equal(page.unresolved['A:stale'].operation, 'ENROLL')
  assert.equal(page.recordAllowed(course('stale', 'FCFS', ['ENROLL']), 'ENROLL'), false)
})

test('an authorized reload replaces a DROP-preflight denial with fresh server facts', async () => {
  const target = course('a', 'FCFS', ['DROP'])
  const { page, dialogs, calls } = mount({
    preflightDropSelection: async () => { throw { biz: true, code: 403, httpStatus: 403, message: '无权办理' } },
    getSelectionCourses: async () => [group('A', [course('fresh', 'FCFS', ['ENROLL'])])],
    getMySelections: async () => []
  })
  page.courseCache.A = [group('A', [target])]; page.recordCache.A = [record('SELECTED')]
  page.drop(target)
  await dialogs[0].success({ confirm: true })
  await page.load()
  assert.equal(page.decisionError, null)
  assert.equal(page.activeGroups[0].courses[0].selectionCourseId, 'fresh')
  assert.equal(page.recordAllowed(page.activeGroups[0].courses[0], 'DROP'), false)
  assert.equal(calls.filter(([name]) => name === 'drop').length, 0)
})

test('slow old batch success and failure cannot pollute current data, error or loading flags', async () => {
  const oldCourses = deferred(), oldRecords = deferred()
  const { page } = mount({
    getSelectionCourses: batch => batch === 'A' ? oldCourses.promise : Promise.resolve([group('B', [course('b')])]),
    getMySelections: batch => batch === 'A' ? oldRecords.promise : Promise.resolve([record('LOCKED', 'b', 'B')])
  })
  const old = page.loadBatch('A')
  await page.switchBatch('B')
  oldCourses.reject({ biz: true, code: 403 }); oldRecords.resolve([record('SELECTED')])
  await old
  assert.equal(page.activeGroups[0].courses[0].selectionCourseId, 'b')
  assert.equal(page.activeRecords[0].selectionCourseId, 'b')
  assert.equal(page.courseState, 'ready'); assert.equal(page.recordsState, 'ready')
  assert.equal(page.courseError, '')
})

test('personal-record refresh does not cancel the independent course read', async () => {
  const pending = deferred()
  const { page } = mount({ getSelectionCourses: () => pending.promise })
  const read = page.loadBatch('A')
  await page.refreshRecords()
  pending.resolve([group('A', [course('new')])])
  await read
  assert.equal(page.activeGroups[0].courses[0].selectionCourseId, 'new')
})

test('rapid clicks produce one modal; a refreshed object cancels an old confirmation', async () => {
  const { page, dialogs, calls } = mount()
  const target = page.activeGroups[0].courses[0]
  page.enroll(target); page.enroll(target)
  assert.equal(dialogs.length, 1)
  await page.readCourses('A')
  await dialogs[0].success({ confirm: true })
  assert.equal(calls.length, 0)
  assert.equal(page.acting, null)
})

test('preflight failure does not claim an enroll has been sent; 403/409 never replay', async () => {
  for (const code of [403, 409]) {
    const { page, dialogs, calls } = mount({ preflightSelection: async () => { throw { biz: true, code } } })
    page.enroll(page.activeGroups[0].courses[0])
    await dialogs[0].success({ confirm: true })
    assert.equal(calls.length, 0)
    assert.equal(page.receipt, null)
    assert.ok(page.decisionError)
  }
})

test('identity switch drops cached objects, receipts and requests before showing the new identity', async () => {
  const old = deferred()
  const { page, definition, switchIdentity } = mount({ getMySelections: () => old.promise })
  const read = page.refreshRecords()
  page.receipt = { status: 'SELECTED' }
  page.unresolved = { 'A:a': { selectionCourseId: 'a', batchId: 'A' } }
  switchIdentity(); definition.onHide.call(page)
  page.resetIdentity()
  old.resolve([record('SELECTED')]); await read
  assert.equal(Object.keys(page.recordCache).length, 0)
  assert.equal(Object.keys(page.courseCache).length, 0)
  assert.equal(Object.keys(page.unresolved).length, 0)
  assert.equal(page.receipt, null)
})


test('a successful refresh clears obsolete read denial but preserves a write decision', async () => {
  const { page } = mount()
  page.consumeReadError('courses', { biz: true, code: '403001', httpStatus: 403, message: '无权查看' })
  await page.loadBatch('A')
  assert.equal(page.decisionError, null)
  page.decisionError = { message: '本次写入未受理' }
  await page.loadBatch('A')
  assert.equal(page.decisionError.message, '本次写入未受理')
})
