import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

function storageStub() {
  let value = ''
  return { getStorageSync: () => value, setStorageSync: (_key, next) => { value = next } }
}

function loadWriteContract(storage = storageStub()) {
  const source = fs.readFileSync(new URL('./write-result.js', import.meta.url), 'utf8')
    .replace(/export function/g, 'function').replace(/export const/g, 'const')
  const sandbox = { uni: storage }
  vm.runInNewContext(`${source}\nglobalThis.contract = { beginPersistentWrite, clearPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, listPersistentWrites, persistWriteAck, teacherWriteContext }`, sandbox)
  return { ...sandbox.contract, storage }
}

function flush() { return new Promise((resolve) => setTimeout(resolve, 0)) }
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function page(file, dependencies = {}) {
  const contract = dependencies.contract || loadWriteContract()
  const session = dependencies.session || { identity: { tenantId: 1, userId: 2, activeContextId: 'ctx' }, currentRole: 'teacher', realUser: {} }
  const events = { toasts: [], successToasts: [], routes: [] }
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8')
    .split('<script>')[1].split('</script>')[0]
    .replace(/^import .*$/gm, '').replace('export default', 'globalThis.options =')
  const sandbox = {
    teacherApi: dependencies.teacherApi || {}, useSessionStore: () => session,
    normalizeError: (error) => ({ kind: error && (error.status === 403 || error.httpStatus === 403) ? 'forbidden' : 'unknown', text: (error && error.message) || '请求失败' }),
    createSubmitLock: () => ({ run: (fn) => fn() }), getStatusBarHeight: () => 20,
    go: (route) => events.routes.push(route), toast: (message) => events.toasts.push(message),
    ...contract,
    uni: {
      getStorageSync: contract.storage.getStorageSync, setStorageSync: contract.storage.setStorageSync,
      showToast: (options) => events.successToasts.push(options.title), navigateBack() {}, stopPullDownRefresh() {},
      ...(dependencies.uni || {})
    },
    console
  }
  const decoder = fs.readFileSync(new URL('../../../utils/nav.js', import.meta.url), 'utf8').match(/export function decodeQueryText[\s\S]*?\n\}/)[0].replace('export ', '')
  vm.runInNewContext(decoder + '\n' + source, sandbox)
  const options = sandbox.options
  const instance = options.data()
  for (const [name, method] of Object.entries(options.methods || {})) instance[name] = method.bind(instance)
  for (const [name, getter] of Object.entries(options.computed || {})) Object.defineProperty(instance, name, { get: () => getter.call(instance) })
  for (const name of ['onLoad', 'onShow', 'onHide', 'onUnload']) if (options[name]) instance[name] = options[name].bind(instance)
  instance._pageActive = true
  return { instance, session, events }
}

function attendanceSetup(instance) {
  const task = { teachingTaskId: '11', classId: '4', courseName: 'PLC', taskStatus: 'READY', formalOccurrenceReady: true, formalSchedulePatterns: [{ scheduleItemId: '31', slotNo: 2, weekday: 2, startWeek: 1, endWeek: 18 }] }
  instance.taskOptions = [task]; instance.taskIndex = 0; instance.applyTask(task); instance.patternIndex = 0
  instance.form = { ...instance.form, teachingTaskId: '11', classId: '4', sessionDate: '2026-09-08', slotNo: '2', scheduleItemId: '31' }
  instance.showForm = true
  return task
}

test('an older attendance readback cannot overwrite a newer list read', async () => {
  const response = deferred()
  const { instance } = page('./attendance.vue', { teacherApi: { getAttendanceSessions: () => response.promise } })
  instance._writeEpoch = 1
  const read = instance.readBackSession('7', instance.contextKey(), 1, true)
  instance._listEpoch += 1
  instance.sessions = [{ sessionId: '8', status: 'DRAFT' }]
  response.resolve({ items: [{ sessionId: '7', status: 'SUBMITTED' }] })
  assert.equal(await read, null)
  assert.equal(instance.sessions[0].sessionId, '8')
})

test('an old submitted session cannot close a different session opened during formal readback', async () => {
  const response = deferred()
  const { instance, events } = page('./attendance.vue', { teacherApi: {
    submitAttendanceSession: async () => ({ sessionId: '7', status: 'SUBMITTED' }),
    getAttendanceSessions: () => response.promise
  } })
  instance.active = { sessionId: '7', status: 'DRAFT' }
  instance.items = [{ studentId: '11', status: 'PRESENT' }]
  instance.confirmModal = async () => true
  await instance.submitSession()
  await flush()
  instance.active = { sessionId: '8', status: 'DRAFT' }
  instance.items = [{ studentId: '22', status: 'ABSENT' }]
  response.resolve({ items: [{ sessionId: '7', status: 'SUBMITTED' }] })
  await flush()
  assert.equal(instance.active.sessionId, '8')
  assert.equal(instance.items[0].studentId, '22')
  assert.equal(events.successToasts.length, 0)
})

test('home validates formal attendance route', () => {
  const { instance, events } = page('./index.vue')
  const valid = '/pages/teacher/academic-affairs/attendance?teachingTaskId=11&sessionDate=2026-09-08&slotNo=2&scheduleItemId=31'
  const item = { scheduleItemId: '31', teachingTaskId: '11', sessionDate: '2026-09-08', weekNo: 2, weekday: 2, slotNo: 2, attendanceRoute: valid }
  instance.todayItems = [item]
  instance.openTodayCourse(item)
  assert.equal(events.routes[0], valid)
  item.attendanceRoute = valid.replace('teachingTaskId=11', 'teachingTaskId=12')
  instance.openTodayCourse(item)
  assert.equal(events.routes[1], '/pages/teacher/my-schedule/index?scheduleItemId=31&week=2&weekday=2')
})

test('home 403 clears private facts', async () => {
  const { instance } = page('./index.vue', { teacherApi: { getMySchedule: async () => { throw { status: 403 } } } })
  instance.loadedContext = instance.contextKey()
  instance.todayItems = [{ scheduleItemId: '31' }]
  instance.invigilationWorkbench = { items: [{ invigilatorId: '9' }] }
  instance.counts = { grade: 2 }
  await instance.load()
  assert.equal(instance.todayItems.length, 0)
  assert.equal(instance.invigilationWorkbench.items.length, 0)
  assert.equal(Object.keys(instance.counts).length, 0)
  assert.equal(instance.state, 'error')
})

test('attendance create needs exact ACK and formal list readback', async () => {
  let posts = 0
  const { instance, events } = page('./attendance.vue', {
    teacherApi: {
      createAttendanceSession: async () => { posts += 1; return {} },
      getAttendanceSessions: async () => ({ items: [] })
    }
  })
  attendanceSetup(instance)
  instance.createSession()
  await flush(); await flush()
  assert.equal(posts, 1)
  assert.equal(events.successToasts.includes('考勤场次已创建'), false)
  assert.equal(instance.showForm, true)
  instance.createSession()
  await flush()
  assert.equal(posts, 1)
})

test('attendance create succeeds after matching ACK and formal row', async () => {
  const { instance, events } = page('./attendance.vue', {
    teacherApi: {
      createAttendanceSession: async () => ({ sessionId: '7', teachingTaskId: '11', sessionDate: '2026-09-08', slotNo: 2, status: 'DRAFT', occurrenceEvidence: { scheduleItemId: '31' } }),
      getAttendanceSessions: async () => ({ items: [{ sessionId: '7', status: 'DRAFT' }] })
    }
  })
  attendanceSetup(instance)
  instance.createSession()
  await flush(); await flush(); await flush()
  assert.equal(events.successToasts.includes('考勤场次已创建'), true)
  assert.equal(instance.showForm, false)
  assert.equal(instance.hasUnknownWrite('create', '11|2026-09-08|2|31|'), false)
})

test('attendance submit keeps ambiguous command locked and exact submit closes only after readback', async () => {
  let exact = false
  const { instance, events } = page('./attendance.vue', {
    teacherApi: {
      submitAttendanceSession: async () => exact ? { sessionId: '8', status: 'SUBMITTED' } : {},
      getAttendanceSessions: async () => ({ items: [{ sessionId: exact ? '8' : '7', status: exact ? 'SUBMITTED' : 'DRAFT' }] })
    }
  })
  instance.confirmModal = async () => true
  instance.active = { sessionId: '7', status: 'DRAFT', courseName: 'PLC' }
  instance.items = [{ studentId: '1', status: 'PRESENT' }]
  instance.submitSession()
  await flush(); await flush()
  assert.equal(instance.active.sessionId, '7')
  assert.equal(events.successToasts.includes('考勤已提交'), false)
  assert.equal(instance.hasUnknownWrite('submit', '7'), true)

  const next = page('./attendance.vue', {
    teacherApi: {
      submitAttendanceSession: async () => ({ sessionId: '8', status: 'SUBMITTED' }),
      getAttendanceSessions: async () => ({ items: [{ sessionId: '8', status: 'SUBMITTED' }] })
    }
  })
  next.instance.confirmModal = async () => true
  next.instance.active = { sessionId: '8', status: 'DRAFT', courseName: 'PLC' }
  next.instance.items = [{ studentId: '2', status: 'LATE' }]
  next.instance.submitSession()
  await flush(); await flush(); await flush()
  assert.equal(next.instance.active, null)
  assert.equal(next.events.successToasts.includes('考勤已提交'), true)
})

test('attendance displays server summary for a 65-person class while rendering only the current thirty-person page', () => {
  const { instance } = page('./attendance.vue')
  instance.applyRosterPage({
    items: Array.from({ length: 30 }, (_, index) => ({ studentId: String(index + 1), status: 'PRESENT' })),
    total: 65, page: 1, pageSize: 30, hasMore: true,
    summary: { PRESENT: 17, LATE: 16, ABSENT: 16, LEAVE: 16, UNMARKED: 0 },
    rosterIntegrity: 'READY'
  })
  assert.equal(instance.visibleStudents.length, 30)
  assert.equal(Object.values(instance.statusCounts).reduce((sum, count) => sum + count, 0), 65)
  assert.equal(instance.rosterPageCount, 3)
  assert.equal(instance.rosterHasMore, true)
})

test('an unconfirmed student mark blocks whole-session submission', async () => {
  let submits = 0
  const { instance } = page('./attendance.vue', {
    teacherApi: {
      markAttendance: async () => ({}),
      getAttendanceDetail: async () => ({ sessionId: '7', status: 'DRAFT', items: [{ studentId: '1', status: 'PRESENT' }] }),
      submitAttendanceSession: async () => { submits += 1; return { sessionId: '7', status: 'SUBMITTED' } }
    }
  })
  instance.active = { sessionId: '7', status: 'DRAFT' }
  instance.items = [{ studentId: '1', status: 'PRESENT' }]
  instance.mark(instance.items[0], 'LATE')
  await flush(); await flush(); await flush()
  assert.equal(instance.hasUnknownMarks, true)
  instance.confirmModal = async () => true
  instance.submitSession()
  await flush()
  assert.equal(submits, 0)
})

test('session deep link returns to the group containing that formal session', () => {
  const { instance } = page('./attendance.vue')
  instance.sessions = Array.from({ length: 45 }, (_, index) => ({ sessionId: String(index + 1) }))
  instance.sessionSeed = { invalid: false, sessionId: '37' }
  let opened = ''
  instance.openSession = (row) => { opened = String(row.sessionId) }
  instance.applySessionSeed()
  assert.equal(opened, '37')
  assert.equal(instance.sessionPage, 1)
})

test('workload empty ACK is not success and the same command is not replayed', async () => {
  let posts = 0
  const { instance, events } = page('./workload.vue', {
    teacherApi: {
      submitWorkload: async () => { posts += 1; return {} },
      getWorkloadDeclarations: async () => ({ items: [] })
    }
  })
  instance._viewContext = instance.contextKey(); instance.d = { items: [] }; instance.state = 'ready'; instance.showForm = true
  instance.form = { hours: '4', termCode: '2026-1', description: '期末监考' }
  instance.submit()
  await flush(); await flush()
  assert.equal(posts, 1)
  assert.equal(events.successToasts.includes('申报已提交'), false)
  assert.equal(instance.form.hours, '4')
  instance.submit()
  await flush()
  assert.equal(posts, 1)
})

test('workload exact ACK requires formal declaration readback and preserves newer draft', async () => {
  const request = deferred()
  const { instance, events } = page('./workload.vue', {
    teacherApi: {
      submitWorkload: () => request.promise,
      getWorkloadDeclarations: async () => ({ items: [{ declarationId: '91', status: 'PENDING', hours: 4 }] })
    }
  })
  instance._viewContext = instance.contextKey(); instance.d = { items: [] }; instance.state = 'ready'; instance.showForm = true
  instance.form = { hours: '4', termCode: '2026-1', description: '期末监考' }
  instance.submit()
  instance.form = { hours: '6', termCode: '2026-1', description: '新增阅卷' }
  request.resolve({ declarationId: '91', status: 'PENDING' })
  await flush(); await flush(); await flush()
  assert.equal(instance.form.hours, '6')
  assert.equal(instance.form.description, '新增阅卷')
  assert.equal(instance.showForm, true)
  assert.equal(events.toasts.includes('原申报已核对，当前新内容已保留'), true)
  assert.equal(instance.hasUnknownWrite('NEW_DECLARATION'), false)
})

test('attendance session list requests the next formal server page instead of slicing a local fifty-row cap', async () => {
  const requests = []
  const { instance } = page('./attendance.vue', { teacherApi: {
    getAttendanceSessions: async (params) => {
      requests.push(params)
      return {
        items: [{ sessionId: String(params.page) }], total: 41,
        page: params.page, pageSize: params.pageSize, hasMore: params.page === 1
      }
    }
  } })
  await instance.load(1)
  assert.equal(requests[0].page, 1)
  assert.equal(requests[0].pageSize, 20)
  assert.equal(instance.sessions.length, 1)
  assert.equal(instance.sessionPageCount, 3)
  assert.equal(instance.sessionHasMore, true)
  await instance.load(2)
  assert.equal(requests[1].page, 2)
  assert.equal(requests[1].pageSize, 20)
  assert.equal(instance.sessions[0].sessionId, '2')
  assert.equal(instance.sessionHasMore, false)
})

test('workload uses a durable command key and resolves an uncertain POST from the formal receipt', async () => {
  const pageCalls = []
  let sent = null
  const { instance } = page('./workload.vue', {
    teacherApi: {
      submitWorkload: async (body) => { sent = body; throw { code: 'NETWORK' } },
      getWorkloadDeclarations: async (params) => {
        pageCalls.push(params)
        return { items: [], total: 21, page: params.page, pageSize: params.pageSize, hasMore: params.page === 1 }
      },
      getWorkloadCommandReceipt: async (key) => ({
        commandKey: key, operation: 'WORKLOAD_SUBMIT', state: 'SUCCESS', result: { declarationId: '91' }
      })
    }
  })
  instance._viewContext = instance.contextKey(); instance.showForm = true
  instance.form = { hours: '4', termCode: '2026-1', description: '期末监考' }
  instance.submit()
  await flush(); await flush(); await flush()
  assert.match(sent.commandKey, /^wmp_[A-Za-z0-9_]+$/)
  assert.equal(pageCalls[0].page, 1)
  assert.equal(pageCalls[0].pageSize, 20)
  assert.equal(instance.hasUnknownWrite('NEW_DECLARATION'), false)
  assert.equal(instance.declarationPageCount, 2)
  await instance.load(null, 2)
  assert.equal(pageCalls.at(-1).page, 2)
})

test('workload 403 clears private data and entered form', async () => {
  const { instance } = page('./workload.vue', { teacherApi: { getWorkloadDeclarations: async () => { throw { status: 403 } } } })
  instance.d = { items: [{ declarationId: '1', description: 'private' }] }; instance.showForm = true
  instance.form = { hours: '8', termCode: '2026-1', description: 'private draft' }
  await instance.load()
  assert.equal(instance.d, null)
  assert.equal(instance.showForm, false)
  assert.equal(instance.form.hours, '')
  assert.equal(instance.state, 'error')
})
