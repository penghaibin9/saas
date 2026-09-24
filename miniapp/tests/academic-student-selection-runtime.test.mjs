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
  // Production uses bounded mobile endpoints.  Keep the existing action-state
  // fixtures compact by adapting their old array fixtures into those contracts.
  studentApi.getSelectionBatches = studentApi.getSelectionBatches || (async () => {
    const value = await studentApi.getSelectionCourses()
    const groups = Array.isArray(value) ? value : (value && value.groups) || []
    return { items: groups.map(item => item.batch).filter(Boolean), total: groups.length, page: 1, pageSize: 20, hasMore: false }
  })
  studentApi.getSelectionCoursesPage = studentApi.getSelectionCoursesPage || (async params => {
    const value = await studentApi.getSelectionCourses(params && params.batchId)
    const groups = Array.isArray(value) ? value : (value && value.groups) || []
    const selected = groups.find(item => String(item?.batch?.batchId) === String(params?.batchId)) || groups[0]
    const items = (selected && selected.courses) || []
    const keyword = String(params?.keyword || '').toLowerCase()
    const filtered = keyword ? items.filter(item => [item.courseName, item.courseCode, item.teacherName].join(' ').toLowerCase().includes(keyword)) : items
    return { batch: selected?.batch || { batchId: params?.batchId || 'A', batchName: 'A' }, items: filtered, total: filtered.length, page: 1, pageSize: 20, hasMore: false }
  })
  studentApi.getMySelectionsPage = studentApi.getMySelectionsPage || (async params => {
    const value = await studentApi.getMySelections(params && params.batchId)
    const rows = Array.isArray(value) ? value : (value && value.items) || []
    const filtered = params?.selectionCourseId == null ? rows : rows.filter(item => String(item.selectionCourseId) === String(params.selectionCourseId))
    return { items: filtered, total: filtered.length, page: 1, pageSize: 20, hasMore: false }
  })
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

test('selection sends batch, course search and personal history paging to the server', async () => {
  const courseCalls = [], recordCalls = []
  const rows = Array.from({ length: 20 }, (_, index) => course(`c-${index + 1}`))
  const { page } = mount({
    getSelectionCoursesPage: async params => {
      courseCalls.push(params)
      return { batch: { batchId: 'A', batchName: '当前批次' }, items: rows, total: 45, page: params.page, pageSize: params.pageSize, hasMore: params.page < 3 }
    },
    getMySelectionsPage: async params => {
      recordCalls.push(params)
      return { items: [record('SELECTED', `r-${params.page}`)], total: 41, page: params.page, pageSize: params.pageSize, hasMore: params.page < 3 }
    }
  })
  await page.readCourses('A')
  await page.readRecords('A')
  assert.equal(page.courseTotal, 45)
  assert.equal(page.activeGroups[0].courses.length, 20)
  assert.equal(page.recordTotal, 41)
  page.searchDraft = '人工智能'
  await page.searchCourses()
  assert.equal(courseCalls.at(-1).keyword, '人工智能')
  await page.changeCoursePage(2)
  await page.changeRecordPage(2)
  assert.equal(courseCalls.at(-1).page, 2)
  assert.equal(recordCalls.at(-1).page, 2)
})

test('selection keeps a failed batch catalog in an error state with a retry path', async () => {
  const { page } = mount({ getSelectionBatches: async () => { throw new Error('网络中断') } })
  page.activeBatchId = ''
  page.courseState = 'loading'
  page.recordsState = 'loading'
  await page.load()
  assert.equal(page.courseState, 'error')
  assert.equal(page.recordsState, 'error')
  assert.match(page.courseError, /网络异常|网络中断/)
})

test('selection retries the same batch catalog page after load-more fails', async () => {
  const pages = []
  let failPageTwo = true
  const { page } = mount({
    getSelectionBatches: async ({ page: requestedPage }) => {
      pages.push(requestedPage)
      if (requestedPage === 2 && failPageTwo) {
        failPageTwo = false
        throw new Error('网络中断')
      }
      return { items: [{ batchId: `batch-${requestedPage}`, batchName: `第${requestedPage}页` }], total: 40, page: requestedPage, pageSize: 20, hasMore: requestedPage < 2 }
    }
  })
  page.batchCatalog = [{ batchId: 'batch-1', batchName: '第1页' }]
  page.batchPage = 1
  page.batchHasMore = true
  await page.loadMoreBatches()
  assert.equal(page.batchPage, 1)
  await page.loadMoreBatches()
  assert.deepEqual(pages, [2, 2])
  assert.equal(page.batchPage, 2)
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
