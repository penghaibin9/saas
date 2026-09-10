import test, { beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import * as approvalRecovery from './approval-recovery.js'

// Each test represents an isolated device; page recreations within a test share its storage.
beforeEach(() => {
  const values = new Map()
  globalThis.uni = {
    getStorageSync: key => values.get(key) || '',
    setStorageSync: (key, value) => values.set(key, value),
    removeStorageSync: key => values.delete(key)
  }
})

function storageStub(seed = '') {
  let value = seed
  return {
    getStorageSync: () => value,
    setStorageSync: (_key, next) => { value = next },
    value: () => value
  }
}

function loadWriteResultContract(storage = storageStub()) {
  const source = fs.readFileSync(new URL('./write-result.js', import.meta.url), 'utf8')
    .replace(/export function/g, 'function')
    .replace(/export const/g, 'const')
  const sandbox = { uni: storage }
  vm.runInNewContext(`${source}\nglobalThis.contract = { TEACHER_WRITE_STORAGE_KEY, isExplicitWriteRejection, isForbiddenResponse, teacherWriteContext, listPersistentWrites, getPersistentWrite, beginPersistentWrite, persistWriteAck, clearPersistentWrite }`, sandbox)
  sandbox.contract.storage = storage
  return sandbox.contract
}

const writeResultContract = loadWriteResultContract()

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

// Execute the actual page methods against controlled transport delays.
function page(file, dependencies = {}) {
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8')
    .split('<script>')[1].split('</script>')[0]
    .replace(/^import .*$/gm, '').replace('export default', 'globalThis.options =')
  const contract = dependencies.writeContract || loadWriteResultContract()
  const suppliedUni = dependencies.uni || {}
  const sandbox = {
    teacherApi: {}, academicGradeEntryApi: {}, toast() {}, go() {},
    createSubmitLock: () => ({ run: (fn) => fn() }),
    normalizeError: () => ({ text: '请求失败' }),
    ...contract,
    ...approvalRecovery,
    useSessionStore: () => ({ identity: { tenantId: 1, userId: 1, activeContextId: 10 }, currentRole: 'teacher', realUser: { tenantId: 1 } }),
    ...dependencies,
    uni: { getStorageSync: contract.storage.getStorageSync, setStorageSync: contract.storage.setStorageSync, ...suppliedUni }
  }
  const decoder = fs.readFileSync(new URL('../../../utils/nav.js', import.meta.url), 'utf8').match(/export function decodeQueryText[\s\S]*?\n\}/)[0].replace('export ', '')
  vm.runInNewContext(decoder + '\n' + source, sandbox)
  const options = sandbox.options
  const instance = options.data()
  for (const [name, method] of Object.entries(options.methods)) instance[name] = method.bind(instance)
  for (const [name, getter] of Object.entries(options.computed || {})) {
    Object.defineProperty(instance, name, { get: () => getter.call(instance) })
  }
  instance._pageActive = true
  for (const name of ['onHide', 'onShow']) if (options[name]) instance[name] = options[name].bind(instance)
  return instance
}

const ambiguousServerFailure = () => ({ code: 500001, biz: true, httpStatus: 500, message: '服务端异常' })

function grade(dependencies) {
  const instance = page('./grade-entry.vue', dependencies)
  instance.active = { gradeTaskId: '8', status: 'INPUTTING' }
  instance._rosterEpoch = 1
  instance.roster = [{ studentId: 11 }]
  instance.scores = { 11: { usualScore: '70', finalScore: '80', exceptionFlag: 'NORMAL' } }
  instance.markDirty(11)
  return instance
}

function dynamicRoster(overrides = {}) {
  const base = {
    gradeTaskId: '8', taskVersion: 1, courseName: 'PLC', status: 'INPUTTING', passLine: 60,
    entryMode: 'COMPONENTS', canWriteComponents: true,
    scheme: {
      schemeId: '3', schemeVersion: 2, status: 'LOCKED',
      components: [
        { code: 'PROJECT', name: 'Project', weight: 60, required: true },
        { code: 'LAB', name: 'Lab', weight: 40, required: true }
      ]
    },
    rosterIdentity: { source: 'TEACHING_CLASS_ROSTER', teachingClassId: '4', rosterVersionId: '5', rosterVersionNo: 1, rosterHash: 'a'.repeat(64), memberCount: 1 },
    total: 1, page: 1, pageSize: 30, hasMore: false,
    items: [{ studentId: '11', studentNo: 'S11', realName: 'Student 11', scores: { PROJECT: 80, LAB: 90 }, totalScore: 84, exceptionFlag: 'NORMAL', recordId: '21', rowVersion: 4 }]
  }
  return { ...base, ...overrides, scheme: overrides.scheme || base.scheme, rosterIdentity: overrides.rosterIdentity || base.rosterIdentity }
}

function dynamicGrade(dependencies = {}, roster = dynamicRoster()) {
  const instance = page('./grade-entry.vue', dependencies)
  instance.active = { gradeTaskId: '8', courseName: 'PLC', status: 'INPUTTING', passLine: 60 }
  instance._rosterEpoch = 1
  instance.applyDynamicRoster(instance.active, roster)
  instance.rosterState = 'ready'
  return instance
}

test('single save preserves a newer special status and its unsaved marker', async () => {
  const request = deferred()
  const instance = grade({ teacherApi: { enterGradeScore: () => request.promise } })
  const saving = instance.saveScore(instance.roster[0])
  instance.changeException(instance.roster[0], { detail: { value: 1 } })
  request.resolve({ totalScore: 75, exceptionFlag: 'NORMAL' })
  assert.equal(await saving, false)
  assert.equal(instance.scores[11].exceptionFlag, 'ABSENT')
  assert.equal(instance.dirty[11], true)
})

test('batch save clears only rows unchanged since the submitted snapshot', async () => {
  const request = deferred()
  const instance = grade({ academicGradeEntryApi: { batchSave: () => request.promise } })
  instance.roster.push({ studentId: 12 })
  instance.scores[12] = { usualScore: '80', finalScore: '90', exceptionFlag: 'NORMAL' }
  instance.markDirty(12)
  const saving = instance.saveAll()
  instance.scores[11].finalScore = '91'
  instance.markDirty(11)
  request.resolve({ items: [{ studentId: 11, totalScore: 75 }, { studentId: 12, totalScore: 85 }], qualityReport: { canSubmit: true } })
  assert.equal(await saving, false)
  assert.equal(instance.dirty[11], true)
  assert.equal(instance.scores[11].finalScore, '91')
  assert.equal(instance.dirty[12], false)
  assert.equal(instance.scores[12].totalScore, 85)
  assert.equal(instance.qualityReport, null)
})

test('quality response cannot certify edits made while the check was running', async () => {
  const request = deferred()
  const instance = grade({ academicGradeEntryApi: { qualityReport: () => request.promise } })
  instance.dirty[11] = false
  const checking = instance.loadQualityReport()
  instance.markDirty(11)
  request.resolve({ canSubmit: true })
  assert.equal(await checking, null)
  assert.equal(instance.qualityReport, null)
})

test('edits during submission confirmation require a new save and quality check', async () => {
  let submissions = 0
  const instance = grade({
    academicGradeEntryApi: { qualityReport: async () => ({ canSubmit: true, summary: '通过' }) },
    teacherApi: { submitGradeTask: async () => { submissions += 1 } }
  })
  instance.dirty[11] = false
  instance.confirmModal = async () => { instance.markDirty(11); return true }
  await instance.submitTask()
  assert.equal(submissions, 0)
  assert.equal(instance.dirty[11], true)
})

test('failed save retains editable data and releases the write lock', async () => {
  const instance = grade({ teacherApi: { enterGradeScore: async () => { throw new Error('断网') } } })
  assert.equal(await instance.saveScore(instance.roster[0]), false)
  assert.equal(instance.dirty[11], true)
  assert.equal(instance.scores[11].finalScore, '80')
  assert.equal(instance.saving, null)
})

test('batch save cannot overlap an in-flight single save', async () => {
  const request = deferred()
  let batchCalls = 0
  const instance = grade({
    teacherApi: { enterGradeScore: () => request.promise },
    academicGradeEntryApi: { batchSave: async () => { batchCalls += 1 } }
  })
  const saving = instance.saveScore(instance.roster[0])
  assert.equal(await instance.saveAll(), false)
  assert.equal(batchCalls, 0)
  request.resolve({ totalScore: 75 })
  assert.equal(await saving, true)
})

test('home counts use each business queue status rather than a generic pending state', () => {
  const instance = page('./index.vue')
  for (const [key, status] of [['academicTask', 'ASSIGNED'], ['defer', 'TEACHER_CONFIRM'], ['warning', 'PENDING_HANDLE'], ['scheduleReview', 'COLLEGE_REVIEW']]) {
    instance.setResult(key, { status: 'fulfilled', value: { items: [{ status }] } }, true)
    assert.equal(instance.counts[key], 1, key)
  }
  instance.setResult('grade', { status: 'fulfilled', value: { items: [{ status: 'PUBLISHED' }] } }, true)
  assert.equal(instance.counts.grade, 0)
})

test('roster groups stay bounded while unsaved scores survive forward and back navigation', () => {
  const instance = grade()
  instance.roster = Array.from({ length: 65 }, (_, i) => ({ studentId: i + 11 }))
  assert.equal(instance.visibleRoster.length, 30)
  instance.showMoreRoster()
  assert.equal(instance.visibleRoster.length, 30)
  assert.equal(instance.visibleRoster[0].studentId, 41)
  instance.showMoreRoster()
  assert.equal(instance.visibleRoster.length, 5)
  instance.showPreviousRoster()
  instance.showPreviousRoster()
  assert.equal(instance.visibleRoster[0].studentId, 11)
  assert.equal(instance.scores[11].finalScore, '80')
  assert.equal(instance.dirty[11], true)
})

test('overdue quality report blocks submission even when score completeness is ready', async () => {
  let submissions = 0
  const instance = grade({
    academicGradeEntryApi: { qualityReport: async () => ({ ready: true, canSubmit: false, isOverdue: true }) },
    teacherApi: { submitGradeTask: async () => { submissions += 1 } }
  })
  instance.dirty[11] = false
  instance.confirmModal = async () => { throw new Error('must not confirm an overdue task') }
  await instance.submitTask()
  assert.equal(submissions, 0)
})

test('stale roster errors cannot replace a newer task roster', async () => {
  const first = deferred()
  const second = deferred()
  const instance = grade({ teacherApi: { getGradeRoster: (id) => id === '1' ? first.promise : second.promise } })
  const openingFirst = instance.openTask({ gradeTaskId: '1' })
  const openingSecond = instance.openTask({ gradeTaskId: '2' })
  second.resolve({ items: [{ studentId: 20 }] })
  await openingSecond
  first.reject(new Error('old error'))
  await openingFirst
  assert.equal(instance.active.gradeTaskId, '2')
  assert.equal(instance.roster[0].studentId, 20)
  assert.equal(instance.rosterState, 'ready')
})

test('old quality finally cannot unlock a newer check after background recovery', async () => {
  const first = deferred()
  const second = deferred()
  let calls = 0
  const instance = grade({ academicGradeEntryApi: { qualityReport: () => ++calls === 1 ? first.promise : second.promise } })
  instance.dirty[11] = false
  const checkingFirst = instance.loadQualityReport()
  instance.onHide()
  instance._pageActive = true
  const checkingSecond = instance.loadQualityReport()
  first.resolve({ canSubmit: true })
  await checkingFirst
  assert.equal(instance.qualityLoading, true)
  second.resolve({ canSubmit: false })
  await checkingSecond
  assert.equal(instance.qualityLoading, false)
  assert.equal(instance.qualityReport.canSubmit, false)
})

test('home selects remaining formal course times and does not invent a next class without them', () => {
  const instance = page('./index.vue')
  instance.todayDate = instance.clockDate = '2026-09-08'
  instance.clockMinute = 10 * 60
  instance.todayItems = [{ slotNo: 1 }, { slotNo: 2 }]
  instance.timeBands = [{ slotNo: 1, startTime: '08:00', endTime: '09:00' }, { slotNo: 2, startTime: '10:30', endTime: '11:15' }]
  assert.equal(instance.nextCourse.slotNo, 2)
  assert.equal(instance.courseSectionTitle, '下一节课')
  instance.clockMinute = 11 * 60
  assert.equal(instance.courseSectionTitle, '当前课次')
  instance.clockMinute = 12 * 60
  assert.equal(instance.nextCourse, null)
  instance.timeBands = []
  assert.equal(instance.courseSectionTitle, '今日课次')
})

test('identity switch refreshes the visible evaluation panel', () => {
  const instance = page('../evaluation/index.vue')
  instance.tab = 'results'
  instance._viewContext = 'old-user'
  let results = 0, tasks = 0
  instance.loadResults = () => { results += 1 }
  instance.loadTasks = () => { tasks += 1 }
  instance.onShow()
  assert.equal(results, 1)
  assert.equal(tasks, 0)
  assert.equal(instance.tasksState, 'idle')
})

test('stale discard confirmation cannot clear another task', async () => {
  const instance = grade()
  instance.confirmModal = async () => {
    instance.active = { gradeTaskId: '9', status: 'INPUTTING' }
    return true
  }
  assert.equal(await instance.leaveActiveTask(), false)
  assert.equal(instance.active.gradeTaskId, '9')
  assert.equal(instance.dirty[11], true)
})

const approvalPages = [
  ['./schedule-change-review.vue', 'list', 'changeId', 'doAct', 'APPROVE', 'getScheduleChangePending', 'reviewScheduleChange'],
  ['./status-change-review.vue', 'list', 'changeId', 'doAct', 'APPROVE', 'getStatusChangePending', 'reviewStatusChange'],
  ['../exam-defer/index.vue', 'list', 'deferId', 'doAct', 'APPROVE', 'getAcademicDeferPending', 'reviewAcademicDefer'],
  ['../academic-task/index.vue', 'tasks', 'taskId', 'doConfirm', null, 'getAcademicMyTasks', 'actAcademicTask']
]
const flush = () => new Promise((resolve) => setImmediate(resolve))

for (const error of [Object.assign(new Error('服务响应超时'), { status: 503, code: 'SERVICE_UNAVAILABLE' }), new TypeError('Failed to fetch')]) {
  test(`status-change unknown write stays locked after queue observation: ${error.message}`, async () => {
    let modal, writes = 0, reads = 0
    const row = { changeId: '9007199254740993', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW' }
    const instance = page('./status-change-review.vue', {
      uni: { showModal: (options) => { modal = options } },
      teacherApi: { getStatusChangePending: async () => { reads += 1; return { items: [row] } }, reviewStatusChange: async () => { writes += 1; throw error } }
    })
    await instance.load()
    instance.doAct(row, 'APPROVE'); modal.success({ confirm: true }); await flush()
    assert.equal(instance.unresolvedCount, 1)
    instance.doAct(row, 'APPROVE'); modal.success({ confirm: true }); await flush()
    assert.equal(writes, 1); assert.equal(reads, 1)
    await instance.load()
    instance.doAct(instance.list[0], 'APPROVE'); modal.success({ confirm: true }); await flush()
    assert.equal(writes, 1); assert.equal(reads, 2)
    assert.match(instance.reviewObservation(row), /只读观察.*仍未确认/)
  })
}

test('status-change POST 403 clears sensitive rows and invalidates a late read without erasing an unknown write', async () => {
  let modal, reads = 0
  const request = deferred(), lateRead = deferred()
  const row = { changeId: '9007199254740993', realName: '旧身份私密姓名', reason: '私密原因', status: 'IN_REVIEW' }
  const instance = page('./status-change-review.vue', {
    uni: { showModal: (options) => { modal = options } },
    teacherApi: { getStatusChangePending: () => ++reads === 1 ? Promise.resolve({ items: [row] }) : lateRead.promise, reviewStatusChange: () => request.promise }
  })
  await instance.load(); instance.openEvidence(row)
  instance.doAct(row, 'APPROVE'); modal.success({ confirm: true })
  const loading = instance.load()
  request.reject(Object.assign(new Error('无权限'), { status: 403, code: 'REQUEST_FAILED', bizCode: 'NO_DATA_SCOPE' }))
  await flush()
  assert.equal(instance.list.length, 0); assert.equal(instance.detailId, ''); assert.equal(instance.targetChangeId, '')
  assert.equal(instance.unresolvedCount, 1)
  assert.doesNotMatch(JSON.stringify(instance.reviewAttempts), /旧身份私密姓名|私密原因/)
  lateRead.resolve({ items: [row] }); await loading
  assert.equal(instance.list.length, 0); assert.equal(instance.state, 'error')
})

test('status-change GET 403 clears the old drawer but keeps an earlier unresolved command', async () => {
  let modal, deny = false
  const row = { changeId: '9007199254740993', realName: '旧姓名', status: 'IN_REVIEW' }
  const instance = page('./status-change-review.vue', {
    uni: { showModal: (options) => { modal = options } },
    teacherApi: { getStatusChangePending: async () => { if (deny) throw { code: 'REQUEST_FAILED', bizCode: 'NO_DATA_SCOPE' }; return { items: [row] } }, reviewStatusChange: async () => { throw new Error('断网') } }
  })
  await instance.load(); instance.openEvidence(row)
  instance.doAct(row, 'APPROVE'); modal.success({ confirm: true }); await flush()
  deny = true; await instance.load()
  assert.equal(instance.list.length, 0); assert.equal(instance.detailId, ''); assert.equal(instance.unresolvedCount, 1)
})

test('status-change unresolved original object survives identity visits while another object remains actionable', async () => {
  let modal, writes = 0
  const session = { identity: { userId: 'A' }, currentRole: 'teacher', realUser: { tenantId: '1' } }
  const first = { changeId: '9007199254740992', realName: 'A范围姓名', status: 'IN_REVIEW' }
  const second = { changeId: '9007199254740993', realName: '另一对象', status: 'IN_REVIEW' }
  const instance = page('./status-change-review.vue', {
    useSessionStore: () => session, uni: { showModal: (options) => { modal = options } },
    teacherApi: { getStatusChangePending: async () => ({ items: session.identity.userId === 'A' ? [first, second] : [] }), reviewStatusChange: async () => { writes += 1; if (writes === 1) throw new TypeError('Failed to fetch'); return { changeId: second.changeId, status: 'APPROVED' } } }
  })
  await instance.load(); instance.doAct(first, 'APPROVE'); modal.success({ confirm: true }); await flush()
  session.identity.userId = 'B'; instance.onShow()
  assert.equal(instance.list.length, 0); assert.equal(instance.unresolvedCount, 0)
  await flush()
  session.identity.userId = 'A'; await instance.load()
  assert.equal(instance.unresolvedCount, 1)
  instance.doAct(first, 'APPROVE'); modal.success({ confirm: true }); await flush()
  assert.equal(writes, 1)
  instance.doAct(second, 'APPROVE'); modal.success({ confirm: true }); await flush()
  assert.equal(writes, 2); assert.equal(instance.unresolvedCount, 1)
})

test('status-change queue absence or a changed node never claims the timed-out command succeeded', async () => {
  let modal, rows, writes = 0
  const messages = [], row = { changeId: '9007199254740993', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW' }
  rows = [row]
  const instance = page('./status-change-review.vue', {
    toast: value => messages.push(value), uni: { showModal: (options) => { modal = options } },
    teacherApi: { getStatusChangePending: async () => ({ items: rows }), reviewStatusChange: async () => { writes += 1; throw Object.assign(new Error('超时'), { status: 503 }) } }
  })
  await instance.load(); instance.doAct(row, 'APPROVE'); modal.success({ confirm: true }); await flush()
  rows = []; await instance.load()
  assert.equal(instance.unresolvedCount, 1)
  assert.match(instance.reviewObservation(row), /未返回原对象.*不能据此确认/)
  rows = [{ ...row, currentNode: 'AA_OFFICE_FINAL' }]; await instance.load()
  instance.doAct(rows[0], 'APPROVE'); modal.success({ confirm: true }); await flush()
  assert.equal(writes, 1); assert.equal(instance.unresolvedCount, 1)
  assert.match(instance.reviewObservation(rows[0]), /教务终审.*仍未确认/)
  assert.equal(messages.some(message => message === '已处理'), false)
})

test('status-change an old identity failure cannot expose its notice or unlock the current write', async () => {
  let modal, calls = 0
  const requests = [deferred(), deferred()]
  const session = { identity: { userId: 'A' }, currentRole: 'teacher', realUser: { tenantId: '1' } }
  const row = { changeId: '9007199254740993', status: 'IN_REVIEW' }
  const instance = page('./status-change-review.vue', {
    useSessionStore: () => session, uni: { showModal: options => { modal = options } },
    teacherApi: { getStatusChangePending: async () => ({ items: [row] }), reviewStatusChange: () => requests[calls++].promise }
  })
  await instance.load(); instance.doAct(row, 'APPROVE'); modal.success({ confirm: true })
  session.identity.userId = 'B'; await instance.load(); instance.doAct(row, 'APPROVE'); modal.success({ confirm: true })
  requests[0].reject(new TypeError('Failed to fetch')); await flush()
  assert.equal(instance.acting, true); assert.equal(instance.unresolvedCount, 0)
  requests[1].resolve({ changeId: row.changeId, status: 'APPROVED' }); await flush()
  assert.equal(instance.acting, false); assert.equal(instance.unresolvedCount, 0)
  session.identity.userId = 'A'; await instance.load(); assert.equal(instance.unresolvedCount, 1)
})

for (const [file, list, id, action, choice, read, write] of approvalPages) {
  test(`${file}: refreshed, hidden or changed evidence invalidates its confirmation`, () => {
    for (const stale of ['refreshed', 'hidden', 'changed', 'replaced']) {
      let modal, calls = 0
      const row = { [id]: 7, status: 'SUBMITTED' }
      const instance = page(file, { uni: { showModal: (options) => { modal = options } }, teacherApi: { [write]: () => { calls += 1; return Promise.resolve() } } })
      instance[list] = [row]
      instance._loadEpoch = 1
      instance[action](row, choice)
      if (stale === 'refreshed') instance._loadEpoch += 1
      if (stale === 'hidden') instance.onHide()
      if (stale === 'changed') row.status = 'APPROVED'
      if (stale === 'replaced') instance[list] = [{ ...row }]
      modal.success({ confirm: true, content: '已经核实处理情况' })
      assert.equal(calls, 0, stale)
    }
  })

  test(`${file}: repeated confirmation sends one command`, async () => {
    let modal, calls = 0
    const pending = deferred()
    const row = { [id]: 7 }
    const instance = page(file, { uni: { showModal: (options) => { modal = options } }, teacherApi: { [write]: () => { calls += 1; return pending.promise } } })
    instance[list] = [row]
    instance.load = () => {}
    instance[action](row, choice)
    const result = { confirm: true, content: '已经核实处理情况' }
    modal.success(result)
    modal.success(result)
    assert.equal(calls, 1)
    pending.resolve({})
    await flush()
  })

  test(`${file}: late command from an earlier identity visit cannot unlock the current command`, async () => {
    let modal, calls = 0
    const pending = [deferred(), deferred()]
    const session = { identity: { tenantId: 1, userId: 1, activeContextId: 10 }, currentRole: 'teacher', realUser: { tenantId: 1 } }
    const instance = page(file, {
      useSessionStore: () => session,
      uni: { showModal: (options) => { modal = options } },
      teacherApi: { [read]: async () => ({ items: [{ [id]: 7 }, { [id]: 8 }] }), [write]: () => pending[calls++].promise }
    })
    await instance.load()
    instance[action](instance[list][0], choice)
    modal.success({ confirm: true, content: '已经核实处理情况' })
    session.identity.userId = 2
    await instance.load()
    session.identity.userId = 1
    await instance.load()
    // Every unsettled approval command still owns its original object after an identity round trip.
    // Use a different object to prove the old acknowledgement cannot release the newer command's lock.
    instance[action](instance[list][1], choice)
    modal.success({ confirm: true, content: '已经核实处理情况' })
    pending[0].resolve({})
    await flush()
    assert.ok(instance.acting || instance.actingId)
    pending[1].resolve({})
    await flush()
    assert.ok(!instance.acting && !instance.actingId)
    assert.equal(calls, 2)
  })
}

test('attendance confirmation cannot submit results edited while the modal was open', async () => {
  let submissions = 0
  const instance = page('./attendance.vue', { teacherApi: { submitAttendanceSession: () => { submissions += 1; return Promise.resolve() } } })
  instance.active = { sessionId: 5 }
  instance.items = [{ studentId: 1, status: 'PRESENT' }]
  instance.confirmModal = async () => { instance.items[0].status = 'ABSENT'; return true }
  await instance.submitSession()
  assert.equal(submissions, 0)
})

test('attendance reloads after an in-flight mark settles across hide/show without replaying the write', async () => {
  const pending = deferred()
  let reads = 0, writes = 0
  const instance = page('./attendance.vue', { teacherApi: {
    markAttendance: () => { writes += 1; return pending.promise },
    getAttendanceDetail: async () => { reads += 1; return { sessionId: 5, items: [{ studentId: 1, status: 'PRESENT' }] } }
  } })
  instance.active = { sessionId: 5 }
  instance.items = [{ studentId: 1, status: '' }]
  instance.mark(instance.items[0], 'PRESENT')
  instance.onHide()
  instance._pageActive = true
  instance.openSession(instance.active)
  assert.equal(reads, 0)
  pending.resolve({})
  await flush()
  assert.equal(reads, 1)
  assert.equal(writes, 1)
  assert.equal(instance.hasPendingMarks, false)
})

test('workload acknowledgement preserves form contents changed during submission', async () => {
  const pending = deferred()
  const instance = page('./workload.vue', { teacherApi: { submitWorkload: () => pending.promise } })
  instance.showForm = true
  instance.form.hours = '3'
  instance.load = () => {}
  instance.submit()
  instance.form.hours = '5'
  pending.resolve({})
  await flush()
  assert.equal(instance.form.hours, '5')
  assert.equal(instance.showForm, true)
  assert.equal(instance.submitting, false)
})

test('evaluation does not submit a task changed during confirmation', async () => {
  const task = { taskId: 7, status: 'PENDING' }
  let writes = 0
  const instance = page('../evaluation/index.vue', {
    teacherApi: { submitAcademicEvaluation: () => { writes += 1; return Promise.resolve() } },
    uni: { showModal: (options) => { task.status = 'SUBMITTED'; options.success({ confirm: true }) } }
  })
  instance.tasks = [task]
  instance.openSubmit(task)
  instance.score = '87'
  await instance.doSubmitEvaluation()
  assert.equal(writes, 0)
})

test('evaluation keeps its object stable until the current submission settles', async () => {
  const task = { taskId: 7 }
  const pending = deferred()
  const instance = page('../evaluation/index.vue', {
    teacherApi: { submitAcademicEvaluation: () => pending.promise },
    uni: { showModal: (options) => options.success({ confirm: true }) }
  })
  instance.tasks = [task]
  instance.openSubmit(task)
  instance.score = '87'
  instance.loadTasks = () => {}
  await instance.doSubmitEvaluation()
  instance.openSubmit({ taskId: 8 })
  instance.switchTab('results')
  assert.equal(instance.submitTarget.taskId, 7)
  assert.equal(instance.score, '87')
  assert.equal(instance.tab, 'tasks')
  pending.resolve({})
  await flush()
  assert.equal(instance.submitTarget, null)
  assert.equal(instance.submitting, false)
})

for (const [file, list, id] of approvalPages.filter(([file]) => !file.includes('academic-warning'))) {
  test(`${file}: object review returns to the same bounded queue group`, () => {
    const instance = page(file)
    instance[list] = Array.from({ length: 45 }, (_, i) => ({ [id]: i + 1 }))
    instance.queuePage = 1
    assert.equal(instance.displayedRows.length, 20)
    instance.openEvidence(instance[list][23])
    assert.equal(instance.displayedRows.length, 1)
    assert.equal(instance.displayedRows[0][id], 24)
    assert.equal(instance.backToQueue(), false)
    assert.equal(instance.displayedRows[0][id], 21)
    assert.equal(instance.queuePage, 1)
  })
}

test('formal occurrence detail navigates with its exact schedule identity', () => {
  let route = ''
  const instance = page('../my-schedule/index.vue', { go: (value) => { route = value } })
  instance.todayItems = [{ scheduleItemId: 27, courseName: '目标课程' }]
  instance.openLesson(instance.todayItems[0], true)
  assert.equal(instance.lesson.courseName, '目标课程')
  instance.requestChange(instance.lesson)
  assert.equal(route, '/pages/teacher/schedule-change/index?scheduleItemId=27')
  instance.backToSchedule()
  assert.equal(instance.lesson, null)
})

test('schedule-change seed fails closed when the formal course position is absent', async () => {
  const instance = page('../schedule-change/index.vue', { teacherApi: { getAcademicMySchedule: async () => ({ items: [{ itemId: 28 }] }) } })
  instance.requestedItemId = '27'
  await instance.loadSchedule()
  assert.equal(instance.itemIndex, -1)
  assert.equal(instance.canSubmit, false)
  assert.ok(instance.scheduleError)
})

test('pre-submit review is a separate view and cannot itself submit grades', async () => {
  let submissions = 0
  const instance = grade({
    academicGradeEntryApi: { qualityReport: async () => ({ canSubmit: false, missingCount: 1 }) },
    teacherApi: { submitGradeTask: () => { submissions += 1 } }
  })
  instance.dirty[11] = false
  await instance.reviewForSubmit()
  assert.equal(instance.reviewMode, true)
  assert.equal(instance.qualityReport.canSubmit, false)
  assert.equal(submissions, 0)
  assert.equal(await instance.beforePageBack(), false)
  assert.equal(instance.reviewMode, false)
  assert.equal(instance.active.gradeTaskId, '8')
  assert.equal(instance.scores[11].finalScore, '80')
})

test('appeal form submits only the displayed evaluation result and preserves failed content', async () => {
  let submitted
  const instance = page('../evaluation/index.vue', {
    uni: { showModal: (options) => options.success({ confirm: true }) },
    teacherApi: { appealAcademicEvaluation: async (id, reason) => { submitted = { id, reason }; throw new Error('连接中断') } }
  })
  instance.results = [{ resultId: 9 }, { resultId: 10 }]
  instance.doAppeal(instance.results[1])
  instance.appealReason = '申请核对评价统计范围'
  await instance.submitAppeal()
  assert.deepEqual(submitted, { id: '10', reason: '申请核对评价统计范围' })
  assert.equal(instance.appealTarget.resultId, 10)
  assert.equal(instance.appealReason, '申请核对评价统计范围')
  assert.equal(instance.acting, false)
})

test('missing identifiers do not accidentally open occurrence or invigilation detail', () => {
  const schedule = page('../my-schedule/index.vue')
  schedule.items = [{ courseName: '缺失编号的课程' }]
  assert.equal(schedule.lesson, null)
  const home = page('./index.vue')
  home.invigilationWorkbench = { items: [{ courseName: '缺失编号的监考' }] }
  assert.equal(home.selectedInvig, null)
})

test('attendance groups preserve marks and block submission for an unseen unmarked student', async () => {
  let submissions = 0
  const instance = page('./attendance.vue', { teacherApi: { submitAttendanceSession: async () => { submissions += 1 } } })
  instance.active = { sessionId: 1, status: 'DRAFT' }
  instance.items = Array.from({ length: 65 }, (_, i) => ({ studentId: i + 1, status: i === 64 ? null : 'PRESENT' }))
  assert.equal(instance.visibleStudents.length, 30)
  assert.equal(instance.unmarkedCount, 1)
  instance.showNextUnmarked()
  assert.equal(instance.studentPageIndex, 2)
  assert.equal(instance.visibleStudents.length, 5)
  instance.studentPage = 0
  assert.equal(instance.items[30].status, 'PRESENT')
  await instance.submitSession()
  assert.equal(submissions, 0)
  assert.equal(instance.items.length, 65)
})

test('attendance grouping submits the formal whole session once all students are marked', async () => {
  const calls = []
  const instance = page('./attendance.vue', {
    teacherApi: { submitAttendanceSession: async (id) => { calls.push(id) } },
    uni: { showToast() {} }
  })
  instance.active = { sessionId: 9, status: 'DRAFT' }
  instance.items = Array.from({ length: 65 }, (_, i) => ({ studentId: i + 1, status: 'PRESENT' }))
  instance.confirmModal = async () => true
  instance.load = () => {}
  instance.studentPage = 2
  await instance.submitSession()
  await flush()
  assert.deepEqual(calls, ['9'])
})

test('attendance return blocks pending marks and preserves the session queue group', () => {
  const instance = page('./attendance.vue')
  instance.sessions = Array.from({ length: 42 }, (_, i) => ({ sessionId: i + 1 }))
  instance.sessionPage = 1
  instance.active = instance.sessions[25]
  instance.marking = { 1: 7 }
  assert.equal(instance.backToSessions(), false)
  assert.equal(instance.active.sessionId, 26)
  instance.marking = {}
  instance.backToSessions()
  assert.equal(instance.active, null)
  assert.equal(instance.visibleSessions[0].sessionId, 21)
})

test('evaluation discard cancellation retains content; confirmed discard clears it', async () => {
  let confirm = false
  const instance = page('../evaluation/index.vue', { uni: { showModal: (options) => options.success({ confirm }) } })
  instance.openSubmit({ taskId: 4 })
  instance.score = '88'; instance.comment = '保留评价草稿'
  await instance.backToEvaluation()
  assert.equal(instance.submitTarget.taskId, 4)
  assert.equal(instance.comment, '保留评价草稿')
  confirm = true
  await instance.backToEvaluation()
  assert.equal(instance.submitTarget, null)
  assert.equal(instance.score, '')
  assert.equal(instance.comment, '')
})

test('stale discard confirmation cannot erase newer evaluation content', async () => {
  let dialog
  const instance = page('../evaluation/index.vue', { uni: { showModal: (options) => { dialog = options } } })
  instance.openSubmit({ taskId: 4 })
  instance.score = '88'
  const leaving = instance.backToEvaluation()
  instance.comment = '确认窗口打开后继续填写'
  dialog.success({ confirm: true })
  await leaving
  assert.equal(instance.submitTarget.taskId, 4)
  assert.equal(instance.comment, '确认窗口打开后继续填写')
})

test('evaluation queue groups are independent and detail return preserves the selected group', async () => {
  const instance = page('../evaluation/index.vue')
  instance.tasks = Array.from({ length: 45 }, (_, i) => ({ taskId: i + 1 }))
  instance.results = Array.from({ length: 43 }, (_, i) => ({ resultId: i + 1 }))
  instance.taskPage = 1; instance.resultPage = 2
  instance.openSubmit(instance.visibleTasks[2])
  assert.equal(instance.submitTarget.taskId, 23)
  await instance.backToEvaluation()
  assert.equal(instance.visibleTasks[0].taskId, 21)
  assert.equal(instance.visibleResults.length, 3)
  instance.results = [{ resultId: 90 }]
  assert.equal(instance.resultPageIndex, 0)
  assert.equal(instance.visibleResults[0].resultId, 90)
})

test('warning queue uses server paging and preserves its page after detail return', async () => {
  const calls = []
  const instance = page('../academic-warning/index.vue', { teacherApi: {
    getAcademicWarnings: async (params) => {
      calls.push(params)
      const start = params.page === 2 ? 21 : 1
      return { list: Array.from({ length: 20 }, (_, i) => ({ warningId: start + i, level: params.level || 'HIGH' })), total: 45, hasMore: params.page < 3 }
    },
    getAcademicWarningDetail: async (id) => ({ warning: { warningId: id }, interventions: [] })
  } })
  await instance.load()
  instance.changeQueuePage(1); await flush()
  assert.equal(calls.at(-1).page, 2)
  instance.openWarning(instance.displayedWarnings[3]); await flush()
  assert.equal(instance.displayedWarnings[0].warningId, 24)
  instance.backToWarnings()
  assert.equal(instance.queuePageIndex, 1)
  instance.setLevel('LOW'); await flush()
  assert.equal(calls.at(-1).page, 1)
  assert.equal(calls.at(-1).level, 'LOW')
})

test('workload grouping keeps the declaration form and clamps after list shrink', () => {
  const instance = page('./workload.vue')
  instance.d = { items: Array.from({ length: 43 }, (_, i) => ({ declarationId: i + 1 })) }
  instance.declarationPage = 2
  instance.showForm = true
  instance.form.hours = '8'
  instance.backToDeclarations()
  assert.equal(instance.visibleDeclarations[0].declarationId, 41)
  assert.equal(instance.form.hours, '8')
  instance.d.items = [{ declarationId: 1 }]
  assert.equal(instance.declarationPageIndex, 0)
  assert.equal(instance.visibleDeclarations.length, 1)
})

for (const mode of ['single', 'batch']) {
  test(`grade ${mode} save from an earlier identity visit cannot unlock a newer save`, async () => {
    let user = 1
    const requests = []
    const write = () => { const request = deferred(); requests.push(request); return request.promise }
    const instance = grade({
      useSessionStore: () => ({ identity: { tenantId: 1, userId: user, activeContextId: user }, currentRole: 'teacher' }),
      teacherApi: { enterGradeScore: write }, academicGradeEntryApi: { batchSave: write }
    })
    instance._viewContext = instance.contextKey()
    instance.load = () => {}
    const oldSave = mode === 'single' ? instance.saveScore(instance.roster[0]) : instance.saveAll()
    for (const identity of [2, 1]) { instance.onHide(); user = identity; instance.onShow() }
    instance.active = { gradeTaskId: '8', status: 'INPUTTING' }
    instance.roster = [{ studentId: 11 }]
    instance.scores = { 11: { usualScore: '80', finalScore: '90', exceptionFlag: 'NORMAL' } }
    instance.markDirty(11)
    const newSave = mode === 'single' ? instance.saveScore(instance.roster[0]) : instance.saveAll()
    assert.equal(requests.length, 2)
    requests[0].resolve({ totalScore: 75, items: [{ studentId: 11, totalScore: 75 }] })
    await oldSave
    assert.equal(mode === 'single' ? instance.saving : instance.savingAll, mode === 'single' ? 11 : true)
    assert.equal(instance.dirty[11], true)
    requests[1].resolve({ totalScore: 85, items: [{ studentId: 11, totalScore: 85 }] })
    await newSave
    assert.equal(mode === 'single' ? instance.saving : instance.savingAll, mode === 'single' ? null : false)
  })
}

test('schedule cancellation ignores a late acknowledgement across identity round trips', async () => {
  let user = 1
  const requests = []
  const instance = page('../schedule-change/index.vue', {
    useSessionStore: () => ({ identity: { tenantId: 1, userId: user, activeContextId: user }, currentRole: 'teacher' }),
    uni: { showModal: (options) => options.success({ confirm: true }) },
    teacherApi: { cancelAcademicScheduleChange: () => { const r = deferred(); requests.push(r); return r.promise } }
  })
  instance.load = () => {}
  instance._viewContext = instance.contextKey()
  instance.changes = [{ changeId: 7, status: 'SUBMITTED' }]
  instance.doCancel(instance.changes[0])
  for (const identity of [2, 1]) { instance.onHide(); user = identity; instance.onShow() }
  instance.changes = [{ changeId: 8, status: 'SUBMITTED' }]
  instance.doCancel(instance.changes[0])
  requests[0].resolve({})
  await flush()
  assert.equal(instance.acting, true)
  assert.equal(instance.receipt, null)
  requests[1].resolve({})
  await flush()
  assert.equal(instance.acting, false)
  assert.equal(instance.receipt.changeId, '8')
})

test('attendance late submission cannot close a new identity session', async () => {
  let user = 1
  const requests = []
  const instance = page('./attendance.vue', {
    useSessionStore: () => ({ identity: { tenantId: 1, userId: user, activeContextId: user }, currentRole: 'teacher' }),
    uni: { showToast() {} },
    teacherApi: {
      submitAttendanceSession: () => { const r = deferred(); requests.push(r); return r.promise },
      getAttendanceSessions: async () => ({ items: [{ sessionId: 8, status: 'SUBMITTED' }] })
    }
  })
  instance.load = () => {}
  instance._viewContext = instance.contextKey()
  instance.confirmModal = async () => true
  instance.active = { sessionId: 7, status: 'DRAFT' }
  instance.items = [{ studentId: 1, status: 'PRESENT' }]
  await instance.submitSession()
  for (const identity of [2, 1]) { instance.onHide(); user = identity; instance.onShow() }
  instance.active = { sessionId: 8, status: 'DRAFT' }
  instance.items = [{ studentId: 2, status: 'PRESENT' }]
  await instance.submitSession()
  requests[0].resolve({})
  await flush()
  assert.equal(instance.submitting, true)
  assert.equal(instance.active.sessionId, 8)
  requests[1].resolve({ sessionId: 8, status: 'SUBMITTED' })
  await flush()
  assert.equal(instance.submitting, false)
  assert.equal(instance.active, null)
})

test('schedule day strip uses calendar dates but today lessons remain server authoritative', () => {
  const instance = page('../my-schedule/index.vue')
  instance.todayDate = '2026-09-08'; instance.currentWeek = 2; instance.selectedWeek = 2; instance.selectedDay = 2
  instance.items = [{ itemId: 1, weekday: 2, slotNo: 1, startWeek: 1, endWeek: 18, weekParity: 'ALL' }]
  instance.todayItems = []
  instance.calendarSource = 'HOLIDAY'
  assert.equal(instance.weekDays[0].dateNumber, 7)
  assert.equal(instance.weekDays[6].dateNumber, 13)
  assert.equal(instance.dayIsToday, true)
  assert.equal(instance.dayItems.length, 0)
  instance.todayItems = [{ scheduleItemId: 99, weekday: 5, slotNo: 3, attendanceRoute: '/formal' }]
  assert.equal(instance.dayItems[0].scheduleItemId, 99)
  instance.selectedWeek = 3
  assert.equal(instance.weekDays[0].dateNumber, undefined)
  assert.equal(instance.dayIsToday, false)
  assert.equal(instance.dayItems[0].itemId, 1)
})

test('schedule rejects invalid date labels and retains selected day across same-identity refresh', async () => {
  const data = { todayDate: '2026-09-08', currentWeek: 2, teachingWeeks: 18, items: [], todayItems: [] }
  const instance = page('../my-schedule/index.vue', { teacherApi: { getMySchedule: async () => data } })
  await instance.load()
  assert.equal(instance.selectedDay, 2)
  instance.selectedDay = 4; instance.selectedWeek = 3
  await instance.load()
  assert.equal(instance.selectedDay, 4)
  assert.equal(instance.selectedWeek, 3)
  instance.todayDate = '2026-02-31'
  assert.equal(instance.todayCalendarDate, null)
  assert.equal(instance.weekDateLabel, '')
})

test('write result classification keeps 5xx and transport failures unresolved even with biz=true', () => {
  const explicit = writeResultContract.isExplicitWriteRejection
  assert.equal(explicit({ code: 500001, biz: true, httpStatus: 500 }), false)
  assert.equal(explicit({ code: 'NETWORK', message: 'timeout' }), false)
  assert.equal(explicit({ code: 'BAD_RESPONSE', biz: true, httpStatus: 502 }), false)
  assert.equal(explicit({ code: 422001, biz: true, httpStatus: 422 }), true)
  assert.equal(explicit({ code: 403001, biz: true, httpStatus: 200 }), true)
  assert.equal(explicit({ code: 'DATA_CONFLICT', biz: true, httpStatus: 200 }), true)
  assert.equal(explicit({ code: 500001, biz: true, httpStatus: 409 }), false)
  assert.equal(explicit({ code: '422001', bizCode: '500001', httpStatus: 422 }), false)
})

test('workload 5xx business envelope stays unresolved and blocks the same payload', async () => {
  let writes = 0
  const instance = page('./workload.vue', { teacherApi: { submitWorkload: async () => { writes += 1; throw ambiguousServerFailure() } } })
  instance.showForm = true; instance.form.hours = '3'; instance.load = () => {}
  instance.submit(); await flush()
  assert.equal(instance.hasUnknownWrite(instance.writeObjectId), true)
  instance.submit(); await flush()
  assert.equal(writes, 1)
})

test('attendance create and submit 5xx responses block replay of each formal object', async () => {
  let creates = 0, submissions = 0
  const instance = page('./attendance.vue', { teacherApi: {
    createAttendanceSession: async () => { creates += 1; throw ambiguousServerFailure() },
    submitAttendanceSession: async () => { submissions += 1; throw ambiguousServerFailure() }
  } })
  instance.load = () => {}
  instance.taskOptions = [{ teachingTaskId: 5, classId: 6, formalSchedulePatterns: [{ slotNo: 2, scheduleItemId: 7 }] }]
  instance.taskIndex = 0; instance.patternIndex = 0
  instance.form = { teachingTaskId: '5', classId: '6', sessionDate: '2026-09-09', slotNo: '2', scheduleItemId: '7', sessionType: '常规' }
  instance.createSession(); await flush()
  assert.equal(instance.hasUnknownWrite('create', instance.occurrenceKey), true)
  instance.createSession(); await flush()
  assert.equal(creates, 1)
  instance.active = { sessionId: 9, status: 'DRAFT' }
  instance.items = [{ studentId: 1, status: 'PRESENT' }]
  instance.confirmModal = async () => true
  await instance.submitSession(); await flush()
  assert.equal(instance.hasUnknownWrite('submit', 9), true)
  await instance.submitSession(); await flush()
  assert.equal(submissions, 1)
})

test('schedule submit and cancellation 5xx responses remain separately unresolved', async () => {
  let submissions = 0, cancellations = 0
  const instance = page('../schedule-change/index.vue', {
    uni: { showModal: (options) => options.success({ confirm: true, content: '教学安排变化' }) },
    teacherApi: {
      submitAcademicScheduleChange: async () => { submissions += 1; throw ambiguousServerFailure() },
      cancelAcademicScheduleChange: async () => { cancellations += 1; throw ambiguousServerFailure() }
    }
  })
  instance.load = () => {}
  instance.items = [{ itemId: 7, courseName: 'PLC应用基础' }]
  instance.itemIndex = 0; instance.targetWeekday = '3'; instance.targetSlotNo = '2'; instance.reason = '教学安排需要调整'
  instance.conflictChecked = true; instance.conflictResult = null; instance.checkedFingerprint = instance.bodyFingerprint
  await instance.doSubmit(); await flush()
  assert.equal(instance.hasUnknownWrite('submit', 7), true)
  await instance.doSubmit(); await flush()
  assert.equal(submissions, 1)
  const row = { changeId: 12, status: 'SUBMITTED' }
  instance.changes = [row]
  instance.doCancel(row); await flush()
  assert.equal(instance.hasUnknownWrite('cancel', 12), true)
  instance.doCancel(row); await flush()
  assert.equal(cancellations, 1)
})

test('evaluation and appeal 5xx responses retain drafts and block replay per object', async () => {
  let evaluations = 0, appeals = 0
  const instance = page('../evaluation/index.vue', {
    uni: { showModal: (options) => options.success({ confirm: true }) },
    teacherApi: {
      submitAcademicEvaluation: async () => { evaluations += 1; throw ambiguousServerFailure() },
      appealAcademicEvaluation: async () => { appeals += 1; throw ambiguousServerFailure() }
    }
  })
  instance.loadTasks = () => {}; instance.loadResults = () => {}
  const task = { taskId: 7, status: 'PENDING' }
  instance.tasks = [task]; instance.openSubmit(task); instance.score = '88'; instance.comment = '课堂组织清晰'
  await instance.doSubmitEvaluation(); await flush()
  assert.equal(instance.hasUnknownWrite('evaluation', 7), true)
  await instance.doSubmitEvaluation(); await flush()
  assert.equal(evaluations, 1)
  const result = { resultId: 9 }
  instance.submitTarget = null; instance.results = [result]; instance.doAppeal(result); instance.appealReason = '申请核对评价统计范围'
  await instance.submitAppeal(); await flush()
  assert.equal(instance.hasUnknownWrite('appeal', 9), true)
  await instance.submitAppeal(); await flush()
  assert.equal(appeals, 1)
})

test('warning handling 5xx response blocks all further writes for that object', async () => {
  let writes = 0
  const instance = page('../academic-warning/index.vue', {
    uni: { showModal: (options) => options.success({ confirm: true, content: '已经核实处理情况' }) },
    teacherApi: { handleWarning: async () => { writes += 1; throw ambiguousServerFailure() } }
  })
  instance.load = () => {}; instance._loadEpoch = 1
  const row = { warningId: 7, status: 'PENDING_HANDLE' }
  instance.list = [row]; instance.detailId = '7'
  instance.handle(row, 'CLOSE'); await flush()
  assert.equal(instance.hasUnknownWrite(row, 'CLOSE'), true)
  instance.handle(row, 'ESCALATE'); await flush()
  assert.equal(writes, 1)
})

test('warning followup requires original ACK id and exact detail record before success', async () => {
  let writes = 0
  const row = { warningId: 7, status: 'PENDING_HANDLE' }
  const instance = page('../academic-warning/index.vue', { teacherApi: {
    addAcademicWarningIntervention: async () => { writes += 1; return { warningId: 7, interventionId: 31, status: 'PROCESSING' } },
    getAcademicWarningDetail: async () => ({ warning: { warningId: 7, status: 'PROCESSING' }, interventions: [{ id: 31, content: '正式记录' }] })
  } })
  instance.load = () => {}; instance.list = [row]; instance.detailId = '7'; instance._detailEpoch = 1
  instance.followForm.content = '已经完成第一次面谈'
  assert.equal(await instance.submitFollowup(row), true)
  assert.equal(writes, 1)
  assert.equal(instance.followAck, null)
  assert.equal(instance.followForm.content, '')
})

test('warning followup never matches old content when ACK is missing or unverified', async () => {
  let writes = 0
  const row = { warningId: 7, status: 'PENDING_HANDLE' }
  const unknown = page('../academic-warning/index.vue', { teacherApi: {
    addAcademicWarningIntervention: async () => { writes += 1; throw ambiguousServerFailure() },
    getAcademicWarningDetail: async () => ({ warning: { warningId: 7, status: 'PROCESSING' }, interventions: [{ id: 4, content: '已经完成第一次面谈' }] })
  } })
  unknown.list = [row]; unknown.detailId = '7'; unknown._detailEpoch = 1; unknown.followForm.content = '已经完成第一次面谈'
  await unknown.submitFollowup(row)
  assert.equal(unknown.hasUnknownWrite(row, 'FOLLOWUP'), true)
  await unknown.submitFollowup(row)
  assert.equal(writes, 1)

  const delayed = page('../academic-warning/index.vue', { teacherApi: {
    addAcademicWarningIntervention: async () => ({ warningId: 7, interventionId: 32 }),
    getAcademicWarningDetail: async () => ({ warning: { warningId: 7, status: 'PROCESSING' }, interventions: [{ id: 4, content: '已经完成第一次面谈' }] })
  } })
  delayed.list = [row]; delayed.detailId = '7'; delayed._detailEpoch = 1; delayed.followForm.content = '已经完成第一次面谈'
  assert.equal(await delayed.submitFollowup(row), false)
  assert.equal(delayed.followAck.interventionId, '32')
  assert.equal(delayed.followForm.content, '已经完成第一次面谈')
})

test('pending reservation survives a new component before POST and contains no form text', () => {
  const contract = loadWriteResultContract()
  const context = contract.teacherWriteContext({ identity: { tenantId: 1, userId: 2, activeContextId: 3 }, currentRole: 'teacher' })
  assert.equal(contract.beginPersistentWrite(context, 'workload', 'NEW_DECLARATION').ok, true)
  const fresh = page('./workload.vue', { writeContract: contract, useSessionStore: () => ({ identity: { tenantId: 1, userId: 2, activeContextId: 3 }, currentRole: 'teacher' }) })
  fresh.syncUnknownWrites()
  assert.equal(fresh.hasUnknownWrite('NEW_DECLARATION'), true)
  assert.equal(contract.storage.value().includes('期末监考三场'), false)
})

test('ambiguous POST result survives a new component and blocks replay', async () => {
  const contract = loadWriteResultContract()
  let writes = 0
  const dependencies = { writeContract: contract, teacherApi: { submitWorkload: async () => { writes += 1; throw ambiguousServerFailure() } } }
  const first = page('./workload.vue', dependencies)
  first.form.hours = '3'; first.form.description = '含学生姓名的说明不应持久化'; first.load = () => {}
  first.submit(); await flush()
  const second = page('./workload.vue', dependencies)
  second.form.hours = '3'; second.submit(); await flush()
  assert.equal(writes, 1)
  assert.equal(second.hasUnknownWrite(second.writeObjectId), true)
  assert.equal(contract.storage.value().includes('学生姓名'), false)
})

test('late acknowledgement is persisted under frozen A context across hide and A-B-A', async () => {
  const contract = loadWriteResultContract()
  const request = deferred()
  const session = { identity: { tenantId: 1, userId: 1, activeContextId: 'A' }, currentRole: 'teacher' }
  const first = page('../evaluation/index.vue', {
    writeContract: contract,
    useSessionStore: () => session,
    uni: { showModal: (options) => options.success({ confirm: true }) },
    teacherApi: { submitAcademicEvaluation: () => request.promise }
  })
  const task = { taskId: 7, status: 'PENDING' }
  first.tasks = [task]; first.openSubmit(task); first.score = '88'
  const write = first.doSubmitEvaluation()
  await flush(); first.onHide(); session.identity.activeContextId = 'B'; first.syncUnknownWrites()
  request.resolve({ evaluationId: 91 })
  await write; await flush()
  assert.equal(first.submitTarget.taskId, 7)
  session.identity.activeContextId = 'A'
  const returned = page('../evaluation/index.vue', { writeContract: contract, useSessionStore: () => session })
  returned.syncUnknownWrites()
  assert.equal(returned.hasUnknownWrite('evaluation', 7), true)
  const record = contract.getPersistentWrite(returned.contextKey(), 'evaluation', 7).record
  assert.equal(record.state, 'ACK')
  assert.equal(record.ackId, '91')
})

test('storage write failure sends zero POST requests', async () => {
  const contract = loadWriteResultContract({ getStorageSync: () => '', setStorageSync: () => { throw new Error('quota') }, value: () => '' })
  let writes = 0
  const instance = page('./workload.vue', { writeContract: contract, teacherApi: { submitWorkload: async () => { writes += 1 } } })
  instance.form.hours = '2'
  instance.submit(); await flush()
  assert.equal(writes, 0)
  assert.equal(instance.submitting, false)
})

test('missing tenant user role or active context sends zero POST requests', async () => {
  let writes = 0
  const instance = page('./workload.vue', {
    useSessionStore: () => ({ identity: { tenantId: 1, userId: 2 }, currentRole: 'teacher' }),
    teacherApi: { submitWorkload: async () => { writes += 1 } }
  })
  instance.form.hours = '2'
  instance.submit(); await flush()
  assert.equal(writes, 0)
  assert.equal(instance.writeStorageBlocked, true)
})

test('warning GET 403 clears private UI but preserves the minimal pending reference', async () => {
  const contract = loadWriteResultContract()
  const instance = page('../academic-warning/index.vue', {
    writeContract: contract,
    teacherApi: { getAcademicWarnings: async () => { throw { code: 403001, httpStatus: 403 } } }
  })
  const context = instance.contextKey()
  assert.equal(contract.beginPersistentWrite(context, 'FOLLOWUP', '7').ok, true)
  instance.list = [{ warningId: 7, studentName: '张同学' }]
  instance.detailId = '7'; instance.detail = { student: { realName: '张同学' } }
  instance.followAck = { warningId: '7', interventionId: '31' }
  instance.followForm = { content: '私密跟进内容', result: '结果', nextPlan: '计划' }
  await instance.load()
  assert.equal(instance.list.length, 0)
  assert.equal(instance.detail, null)
  assert.equal(instance.followForm.content, '')
  assert.equal(instance.writeAccessDenied, true)
  assert.ok(contract.getPersistentWrite(context, 'FOLLOWUP', '7').record)
})

test('warning followup and legacy handling write 403 clear private UI but preserve pending references', async () => {
  const forbidden = { code: 403001, httpStatus: 403, message: 'NO_PERMISSION' }
  const row = { warningId: 7, status: 'PENDING_HANDLE', studentName: '张同学' }

  const followContract = loadWriteResultContract()
  const follow = page('../academic-warning/index.vue', {
    writeContract: followContract,
    teacherApi: { addAcademicWarningIntervention: async () => { throw forbidden } }
  })
  const followContext = follow.contextKey()
  follow.list = [row]; follow.detailId = '7'; follow.detail = { warning: row }
  follow.followForm = { content: '已经完成第一次面谈', result: '继续观察', nextPlan: '下周复查' }
  await follow.submitFollowup(row)
  assert.equal(follow.list.length, 0)
  assert.equal(follow.detail, null)
  assert.equal(follow.followForm.content, '')
  assert.equal(follow.writeAccessDenied, true)
  assert.ok(followContract.getPersistentWrite(followContext, 'FOLLOWUP', '7').record)

  const handleContract = loadWriteResultContract()
  const handled = page('../academic-warning/index.vue', {
    writeContract: handleContract,
    uni: { showModal: (options) => options.success({ confirm: true, content: '已经核实处理情况' }) },
    teacherApi: { handleWarning: async () => { throw forbidden } }
  })
  const handleContext = handled.contextKey()
  handled.list = [row]; handled.detailId = '7'; handled.detail = { warning: row }; handled._loadEpoch = 1
  handled.handle(row, 'CLOSE')
  await flush()
  assert.equal(handled.list.length, 0)
  assert.equal(handled.detail, null)
  assert.equal(handled.writeAccessDenied, true)
  assert.ok(handleContract.getPersistentWrite(handleContext, 'CLOSE', '7').record)
})

test('wrong warning parent object never verifies or clears an ACK', async () => {
  const contract = loadWriteResultContract()
  const instance = page('../academic-warning/index.vue', {
    writeContract: contract,
    teacherApi: { getAcademicWarningDetail: async () => ({ warning: { warningId: 8 }, interventions: [{ id: 31 }] }) }
  })
  const context = instance.contextKey()
  contract.beginPersistentWrite(context, 'FOLLOWUP', '7')
  contract.persistWriteAck(context, 'FOLLOWUP', '7', { ackId: 31, parentId: 7 })
  instance.detailId = '7'; instance.syncUnknownWrites()
  assert.equal(await instance.verifyFollowup(), false)
  assert.equal(instance.detail, null)
  assert.equal(instance.detailState, 'error')
  assert.ok(contract.getPersistentWrite(context, 'FOLLOWUP', '7').record)
})


test('warning detail 403 invalidates an overlapping list read and retains only pending references', async () => {
  const late = deferred()
  const instance = page('../academic-warning/index.vue', { teacherApi: {
    getAcademicWarnings: () => late.promise,
    getAcademicWarningDetail: async () => { throw { httpStatus: 403, code: '403001' } }
  } })
  instance.list = [{ warningId: '8', studentName: '旧姓名' }]; instance.detailId = '8'
  instance._actionContext = instance.contextKey()
  instance.beginWrite(instance.contextKey(), 'FOLLOWUP', '8')
  const load = instance.load()
  await instance.loadDetail('8')
  late.resolve({ items: [{ warningId: '8', studentName: '迟到姓名' }], total: 1 })
  await load
  assert.equal(instance.list.length, 0)
  assert.equal(instance.detail, null)
  assert.equal(instance.state, 'error')
  assert.ok(instance.hasUnknownWrite({ warningId: '8' }, 'FOLLOWUP'))
})

test('warning empty handle ACK cannot claim a different observed terminal state as its own result', async () => {
  let modal, reads = 0
  const messages = []
  const instance = page('../academic-warning/index.vue', { toast: text => messages.push(text), uni: { showModal: value => { modal = value } }, teacherApi: {
    handleWarning: async () => ({}),
    getAcademicWarningDetail: async () => { reads++; return { warning: { warningId: '8', status: 'CLOSED' } } }
  } })
  const warning = { warningId: '8', status: 'PROCESSING' }
  instance.list = [warning]; instance.detailId = '8'
  instance.handle(warning, 'CLOSE'); modal.success({ confirm: true, content: '已经核实处理情况' })
  await flush()
  assert.ok(instance.hasUnknownWrite(warning, 'CLOSE'))
  assert.equal(reads, 0)
  assert.equal(messages.includes('预警已关闭'), false)
})

test('workload empty ACK leaves draft and pending reference without a success notice', async () => {
  const notices = []
  const instance = page('./workload.vue', { uni: { showToast: message => notices.push(message.title) }, teacherApi: { submitWorkload: async () => ({}) } })
  instance.showForm = true; instance.form.hours = '3'; instance.form.description = '待核对原说明'
  instance.submit(); await flush()
  assert.equal(instance.form.description, '待核对原说明')
  assert.equal(instance.showForm, true)
  assert.ok(instance.hasUnknownWrite(instance.writeObjectId))
  assert.equal(notices.length, 0)
})

for (const editDuringRead of [false, true]) {
  test(`workload confirms original declaration before clearing unchanged draft (new edit: ${editDuringRead})`, async () => {
    const reading = deferred(), notices = []
    const instance = page('./workload.vue', { uni: { showToast: message => notices.push(message.title) }, teacherApi: {
      submitWorkload: async () => ({ declarationId: '9007199254740993' }),
      getWorkloadDeclarations: () => reading.promise
    } })
    instance.showForm = true; instance.form.hours = '3'
    instance.submit(); await flush()
    assert.equal(instance.form.hours, '3')
    assert.equal(notices.length, 0)
    if (editDuringRead) instance.form.hours = '5'
    reading.resolve({ items: [{ declarationId: '9007199254740993', hours: 3, status: 'SUBMITTED' }] }); await flush()
    assert.equal(instance.hasUnknownWrite(instance.writeObjectId), false)
    assert.equal(instance.form.hours, editDuringRead ? '5' : '')
    assert.equal(instance.showForm, editDuringRead)
    assert.equal(notices.length, editDuringRead ? 0 : 1)
  })
}
