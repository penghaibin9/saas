import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { approvalContextKey, approvalReceiptChanged, hasExplicitApprovalReceipt, isApprovalConflict, isApprovalForbidden } from './approval-recovery.js'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function settle() { return new Promise((resolve) => setTimeout(resolve, 0)) }

function createPage(file, dependencies = {}) {
  const session = dependencies.session || { identity: { tenantId: '1', userId: '2', activeContextId: 'A' }, currentRole: 'teacher', realUser: {} }
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8')
    .split('<script>')[1].split('</script>')[0]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'globalThis.options =')
  const events = { toasts: [], routes: [], modals: [] }
  const suppliedUni = dependencies.uni || {}
  const sandbox = {
    teacherApi: dependencies.teacherApi || {},
    useSessionStore: () => session,
    approvalContextKey,
    approvalReceiptChanged,
    hasExplicitApprovalReceipt,
    isApprovalConflict,
    isApprovalForbidden,
    toast: (message) => events.toasts.push(message),
    go: (route) => events.routes.push(route),
    uni: {
      showModal(options) { events.modals.push(options); options.success({ confirm: true, content: dependencies.modalContent || '' }) },
      stopPullDownRefresh() {},
      ...suppliedUni
    },
    console
  }
  vm.runInNewContext(source, sandbox)
  const options = sandbox.options
  const instance = options.data()
  for (const [name, method] of Object.entries(options.methods || {})) instance[name] = method.bind(instance)
  for (const [name, getter] of Object.entries(options.computed || {})) Object.defineProperty(instance, name, { get: () => getter.call(instance) })
  for (const name of ['onLoad', 'onShow', 'onHide', 'onUnload', 'onBackPress']) if (options[name]) instance[name] = options[name].bind(instance)
  instance._pageActive = true
  return { instance, session, events }
}

test('approval identity includes tenant, user, role and active context', () => {
  const session = { identity: { tenantId: 1, userId: 2, activeContextId: 'A' }, currentRole: 'teacher' }
  const first = approvalContextKey(session)
  session.identity.activeContextId = 'B'
  assert.notEqual(approvalContextKey(session), first)
})

test('only a matching object receipt with a formal state is explicit success', () => {
  assert.equal(hasExplicitApprovalReceipt({}, '7', ['taskId']), false)
  assert.equal(hasExplicitApprovalReceipt({ taskId: '8', status: 'READY' }, '7', ['taskId']), false)
  assert.equal(hasExplicitApprovalReceipt({ taskId: '7' }, '7', ['taskId']), false)
  assert.equal(hasExplicitApprovalReceipt({ taskId: '7', status: 'TEACHER_CONFIRMED' }, '7', ['taskId']), true)
  assert.equal(approvalReceiptChanged({ taskId: '7', status: 'ASSIGNED' }, { taskId: '7', status: 'ASSIGNED' }), false)
  assert.equal(approvalReceiptChanged({ taskId: '7', status: 'TEACHER_CONFIRMED' }, { taskId: '7', status: 'ASSIGNED' }), true)
})

test('teaching task ambiguous receipt locks the original object and never repeats POST', async () => {
  let posts = 0
  const row = { taskId: 'T1', courseName: 'PLC', status: 'ASSIGNED' }
  const { instance, events } = createPage('../academic-task/index.vue', {
    teacherApi: { actAcademicTask: async () => { posts += 1; return {} }, getAcademicMyTasks: async () => ({ items: [row] }) }
  })
  instance.tasks = [row]; instance._loadEpoch = 1; instance._actionContext = instance.contextKey()
  instance.doConfirm(row)
  await settle(); await settle()
  assert.equal(posts, 1)
  assert.equal(instance.reviewLocked(row), true)
  assert.equal(instance.unresolvedCount, 1)
  assert.equal(events.toasts.includes('已确认'), false)
  instance.doConfirm(row)
  await settle()
  assert.equal(posts, 1)
})

test('teaching task exact receipt is the only success path', async () => {
  let posts = 0
  const row = { taskId: 'T2', courseName: 'PLC', status: 'ASSIGNED' }
  const { instance, events } = createPage('../academic-task/index.vue', {
    teacherApi: {
      actAcademicTask: async () => { posts += 1; return { taskId: 'T2', status: 'TEACHER_CONFIRMED' } },
      getAcademicMyTasks: async () => ({ items: [] })
    }
  })
  instance.tasks = [row]; instance._loadEpoch = 1; instance._actionContext = instance.contextKey()
  instance.doConfirm(row)
  await settle(); await settle()
  assert.equal(posts, 1)
  assert.equal(Object.keys(instance.reviewAttempts).length, 0)
  assert.equal(events.toasts.includes('已确认'), true)
})

test('defer conflict clears transport attempt and refreshes formal facts', async () => {
  let reads = 0
  const row = { deferId: 'D1', studentName: '甲', status: 'TEACHER_CONFIRM' }
  const { instance } = createPage('../exam-defer/index.vue', {
    teacherApi: {
      reviewAcademicDefer: async () => { throw { code: 'APPROVAL_VERSION_CONFLICT' } },
      getAcademicDeferPending: async () => { reads += 1; return { items: [row] } }
    }
  })
  instance.list = [row]; instance._loadEpoch = 1; instance._actionContext = instance.contextKey()
  instance.doAct(row, 'APPROVE')
  await settle(); await settle()
  assert.equal(Object.keys(instance.reviewAttempts).length, 0)
  assert.equal(reads, 1)
  assert.equal(instance.list[0].deferId, 'D1')
})

test('schedule-change 403 clears private evidence but retains minimal command reference', async () => {
  const row = { changeId: 'C1', courseName: 'PLC', status: 'SUBMITTED', currentNode: 'COLLEGE_REVIEW', reason: 'private' }
  const { instance } = createPage('./schedule-change-review.vue', {
    teacherApi: { reviewScheduleChange: async () => { throw { status: 403 } } }
  })
  instance.list = [row]; instance.detailId = 'C1'; instance._loadEpoch = 1; instance._actionContext = instance.contextKey()
  instance.doAct(row, 'APPROVE')
  await settle(); await settle()
  assert.equal(instance.list.length, 0)
  assert.equal(instance.detailId, '')
  const attempts = Object.values(instance.reviewAttempts)
  assert.equal(attempts.length, 1)
  assert.deepEqual(Object.keys(attempts[0]).sort(), ['action', 'context', 'epoch', 'objectId', 'observation', 'state'].sort())
  assert.equal(attempts[0].state, 'UNKNOWN')
})

test('late status-change receipt cannot alter the new identity page', async () => {
  const request = deferred()
  const oldRow = { changeId: 'S1', realName: '甲', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW' }
  const newRow = { changeId: 'S2', realName: '乙', status: 'IN_REVIEW', currentNode: 'AA_OFFICE_FINAL' }
  const { instance, session, events } = createPage('./status-change-review.vue', {
    teacherApi: { reviewStatusChange: () => request.promise }
  })
  instance.list = [oldRow]; instance._loadEpoch = 1; instance._writeEpoch = 0; instance._actionContext = instance.contextKey()
  instance.doAct(oldRow, 'APPROVE')
  session.identity.activeContextId = 'B'
  instance._writeEpoch += 1
  instance.list = [newRow]; instance.detailId = 'S2'; instance.acting = false
  request.resolve({ changeId: 'S1', status: 'APPROVED' })
  await settle(); await settle()
  assert.equal(instance.list[0].changeId, 'S2')
  assert.equal(instance.detailId, 'S2')
  assert.equal(events.toasts.includes('已处理'), false)
})

function schedulePayload() {
  return {
    items: [{ scheduleItemId: 'P1', courseName: '常规课程', weekday: 3, slotNo: 2, startWeek: 1, endWeek: 18 }],
    todayItems: [{ scheduleItemId: 'TODAY', courseName: '今日课程', weekday: 2, slotNo: 1, attendanceRoute: '/attendance' }],
    todayDate: '2026-09-08', currentWeek: 2, teachingWeeks: 18, termCode: '2026-1', timeBands: []
  }
}

test('schedule deep link opens only the exact formal lesson and preserves selection on return', async () => {
  const { instance } = createPage('../my-schedule/index.vue', { teacherApi: { getMySchedule: async () => schedulePayload() } })
  instance.onLoad({ scheduleItemId: 'P1', week: '5', weekday: '3' })
  await instance.load()
  assert.equal(instance.lessonId, 'P1')
  assert.equal(instance.lesson.courseName, '常规课程')
  assert.equal(instance.selectedWeek, 5)
  assert.equal(instance.selectedDay, 3)
  instance.backToSchedule()
  assert.equal(instance.lessonId, '')
  assert.equal(instance.selectedWeek, 5)
  assert.equal(instance.selectedDay, 3)
})

test('missing schedule deep link fails closed without falling back to another lesson', async () => {
  const { instance, events } = createPage('../my-schedule/index.vue', { teacherApi: { getMySchedule: async () => schedulePayload() } })
  instance.onLoad({ scheduleItemId: 'MISSING' })
  await instance.load()
  assert.equal(instance.lessonId, '')
  assert.equal(events.toasts.some((text) => text.includes('不存在')), true)
})

test('late schedule response cannot overwrite a switched identity', async () => {
  const request = deferred()
  const session = { identity: { tenantId: '1', userId: '2', activeContextId: 'A' }, currentRole: 'teacher', realUser: {} }
  const { instance } = createPage('../my-schedule/index.vue', { session, teacherApi: { getMySchedule: () => request.promise } })
  const loading = instance.load()
  session.identity.activeContextId = 'B'
  instance.items = [{ scheduleItemId: 'NEW' }]
  request.resolve(schedulePayload())
  await loading
  assert.equal(instance.items[0].scheduleItemId, 'NEW')
})

test('schedule 403 removes private lesson and roster-free course facts', async () => {
  const { instance } = createPage('../my-schedule/index.vue', { teacherApi: { getMySchedule: async () => { throw { status: 403 } } } })
  instance.items = [{ scheduleItemId: 'P1' }]; instance.todayItems = [{ scheduleItemId: 'TODAY' }]; instance.lessonId = 'P1'
  await instance.load()
  assert.equal(instance.items, null)
  assert.equal(instance.todayItems.length, 0)
  assert.equal(instance.lessonId, '')
  assert.equal(instance.state, 'error')
})

test('forbidden and conflict detection accepts HTTP and business error shapes', () => {
  assert.equal(isApprovalForbidden({ statusCode: 403 }), true)
  assert.equal(isApprovalForbidden({ bizCode: 'NO_DATA_SCOPE' }), true)
  assert.equal(isApprovalConflict({ response: { status: 409 } }), true)
  assert.equal(isApprovalConflict({ code: 'APPROVAL_VERSION_CONFLICT' }), true)
})

test('5xx with a conflict-shaped envelope keeps the approval reference and prevents replay', async () => {
  const error = { httpStatus: 500, code: 'APPROVAL_VERSION_CONFLICT' }
  assert.equal(isApprovalConflict(error), false)
  assert.equal(isApprovalForbidden({ httpStatus: 500, bizCode: '403001' }), false)
  let posts = 0
  const row = { deferId: 'D1', status: 'TEACHER_CONFIRM' }
  const { instance } = createPage('../exam-defer/index.vue', {
    teacherApi: { reviewAcademicDefer: async () => { posts++; throw error }, getAcademicDeferPending: async () => ({ items: [row] }) }
  })
  instance.list = [row]; instance._loadEpoch = 1; instance._actionContext = instance.contextKey()
  instance.doAct(row, 'APPROVE'); await settle(); await settle()
  assert.equal(instance.reviewLocked(row), true)
  assert.equal(instance.unresolvedCount, 1)
  instance.doAct(row, 'APPROVE'); await settle()
  assert.equal(posts, 1)
})

test('status review sends the captured decision version through both actual API adapters including zero', async () => {
  const requests = []
  const realSource = fs.readFileSync(new URL('../../../services/realApi.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/^export /gm, '')
  const realSandbox = { ENV: {}, commitNewSessionTokens() {}, realRequest: async (url, options) => {
    requests.push(JSON.parse(JSON.stringify({ url, options })))
    return { changeId: 'S1', status: 'APPROVED', decisionVersion: 1 }
  } }
  vm.runInNewContext(realSource + '\nglobalThis.api = { teacherAcademicStatusChangeReview }', realSandbox)
  const teacherSource = fs.readFileSync(new URL('../../../services/teacherApi.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/^export default .*$/gm, '').replace(/^export /gm, '')
  const teacherSandbox = { real: realSandbox.api, academicGradeEntryApi: {}, teacherSequentialV3: {} }
  vm.runInNewContext(teacherSource + '\nglobalThis.api = teacherApi', teacherSandbox)
  const row = { changeId: 'S1', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW', decisionVersion: 0 }
  const { instance } = createPage('./status-change-review.vue', {
    teacherApi: { ...teacherSandbox.api, getStatusChangePending: async () => ({ list: [] }) }
  })
  instance.list = [row]; instance._loadEpoch = 1; instance._actionContext = instance.contextKey()
  instance.doAct(row, 'APPROVE'); await settle(); await settle()
  assert.equal(requests.length, 1)
  assert.equal(requests[0].url, '/mobile/teacher/academic/status-changes/S1/review')
  assert.equal(requests[0].options.data.expectedDecisionVersion, 0)
  await teacherSandbox.api.reviewStatusChange('S2', 'RETURN', '补充材料')
  assert.equal(Object.hasOwn(requests[1].options.data, 'expectedDecisionVersion'), false)
})
