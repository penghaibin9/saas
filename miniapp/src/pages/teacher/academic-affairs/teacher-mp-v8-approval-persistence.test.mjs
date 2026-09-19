import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { approvalContextKey, approvalReceiptChanged, hasExplicitApprovalReceipt, isApprovalConflict, isApprovalForbidden } from './approval-recovery.js'

function settle() { return new Promise((resolve) => setTimeout(resolve, 0)) }

function makeStorage() {
  const values = new Map()
  return {
    values,
    failGet: false,
    failSet: false,
    failRemove: false,
    getStorageSync(key) { if (this.failGet) throw new Error('get failed'); return values.get(key) || '' },
    setStorageSync(key, value) { if (this.failSet) throw new Error('set failed'); values.set(key, value) },
    removeStorageSync(key) { if (this.failRemove) throw new Error('remove failed'); values.delete(key) }
  }
}

function createPage(file, dependencies = {}) {
  const session = dependencies.session || { identity: { tenantId: 'tenant', userId: 'teacher', activeContextId: 'ctx' }, currentRole: 'teacher', realUser: {} }
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8')
    .split('<script>')[1].split('</script>')[0]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'globalThis.options =')
  const events = { toasts: [] }
  const sandbox = {
    teacherApi: dependencies.teacherApi || {},
    useSessionStore: () => session,
    approvalContextKey,
    approvalReceiptChanged,
    hasExplicitApprovalReceipt,
    isApprovalConflict,
    isApprovalForbidden,
    toast: (message) => events.toasts.push(message),
    uni: {
      showModal(options) { options.success({ confirm: true, content: dependencies.modalContent || '' }) },
      stopPullDownRefresh() {}
    },
    console
  }
  vm.runInNewContext(source, sandbox)
  const options = sandbox.options
  const instance = options.data()
  for (const [name, method] of Object.entries(options.methods || {})) instance[name] = method.bind(instance)
  for (const [name, getter] of Object.entries(options.computed || {})) Object.defineProperty(instance, name, { get: () => getter.call(instance) })
  for (const name of ['onLoad', 'onShow', 'onHide', 'onUnload']) if (options[name]) instance[name] = options[name].bind(instance)
  instance._pageActive = true
  return { instance, session, events }
}

function parseOnlyStoredRecord(storage) {
  assert.equal(storage.values.size, 1)
  const records = JSON.parse([...storage.values.values()][0])
  assert.equal(records.length, 1)
  return records[0]
}

test('corrupt records and foreign scope fail closed without losing the stored bytes', () => {
  for (const invalid of ['[{}]', '[null]', '{"broken":true}']) {
    const storage = makeStorage()
    globalThis.uni = storage
    const attempt = approvalContextKey.createAttempt('review', 'ctx', '1', 'APPROVE')
    assert.equal(approvalContextKey.persistAttempt('review', attempt), true)
    const key = [...storage.values.keys()][0]
    storage.values.set(key, invalid)
    assert.equal(approvalContextKey.restoreAttempts('review', 'ctx').ok, false)
    assert.equal(approvalContextKey.persistAttempt('review', attempt), false)
    assert.equal(storage.values.get(key), invalid)
  }
  const storage = makeStorage()
  globalThis.uni = storage
  const attempt = approvalContextKey.createAttempt('review', 'ctx', '1', 'APPROVE')
  assert.equal(approvalContextKey.persistAttempt('review', attempt), true)
  const key = [...storage.values.keys()][0]
  storage.values.set(key, JSON.stringify([{ ...attempt, context: 'other' }]))
  assert.equal(approvalContextKey.restoreAttempts('review', 'ctx').ok, false)
})

test('a pending object cannot be replaced and stale handles cannot change or clear the next command', () => {
  const storage = makeStorage()
  globalThis.uni = storage
  const first = approvalContextKey.createAttempt('review', 'ctx', '1', 'APPROVE')
  const next = approvalContextKey.createAttempt('review', 'ctx', '1', 'RETURN')
  assert.notEqual(first.attemptKey, next.attemptKey)
  assert.equal(approvalContextKey.persistAttempt('review', first), true)
  assert.equal(approvalContextKey.persistAttempt('review', next), false)
  assert.equal(parseOnlyStoredRecord(storage).action, 'APPROVE')
  assert.equal(approvalContextKey.clearAttempt('review', 'ctx', '1', first), true)
  assert.equal(approvalContextKey.persistAttempt('review', next), true)
  const saved = [...storage.values.values()][0]
  assert.equal(approvalContextKey.persistReceipt('review', first, { receiptId: 'late' }), false)
  assert.equal(approvalContextKey.clearAttempt('review', 'ctx', '1', first), false)
  assert.equal(approvalContextKey.clearAttempt('review', 'other', '1', next), false)
  assert.equal([...storage.values.values()][0], saved)
})

test('storage silently dropping a write fails verification before a command can be sent', () => {
  const storage = makeStorage()
  storage.setStorageSync = () => {}
  globalThis.uni = storage
  const attempt = approvalContextKey.createAttempt('review', 'ctx', '1', 'APPROVE')
  assert.equal(approvalContextKey.persistAttempt('review', attempt), false)
})

test('a 5xx envelope with conflict code retains the pending command and sends decision version zero', async () => {
  globalThis.uni = makeStorage()
  let args
  const row = { changeId: 'S-5xx', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW', decisionVersion: 0 }
  const { instance } = createPage('./status-change-review.vue', {
    teacherApi: { reviewStatusChange: async (...input) => { args = input; throw { httpStatus: 503, code: '409001' } } }
  })
  instance.list = [row]
  instance._loadEpoch = 1
  instance._actionContext = instance.contextKey()
  instance.doAct(row, 'APPROVE')
  await settle(); await settle()
  assert.equal(args[3], 0)
  assert.equal(instance.reviewLocked(row), true)
  assert.equal(approvalContextKey.restoreAttempts('status-change-review', instance.contextKey()).attempts.length, 1)
})

test('persistent record is identity scoped and contains only command evidence', () => {
  const storage = makeStorage()
  globalThis.uni = storage
  const contextA = 'tenant|teacher|teacher|A'
  const contextB = 'tenant|teacher|teacher|B'
  const attempt = approvalContextKey.createAttempt('status-change-review', contextA, 'S1', 'APPROVE', {
    status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW', statusVersion: 0,
    studentName: '不应保存', reason: '不应保存', token: 'secret'
  })
  assert.equal(approvalContextKey.persistAttempt('status-change-review', attempt), true)
  assert.equal(approvalContextKey.persistReceipt('status-change-review', attempt, {
    commandId: 'CMD-1', receiptId: 'R-1', status: 'APPROVED', studentName: '不应保存', token: 'secret'
  }), true)
  const stored = parseOnlyStoredRecord(storage)
  assert.deepEqual(Object.keys(stored).sort(), [
    'attemptKey', 'action', 'beforeNode', 'beforeStatus', 'beforeStatusVersion', 'commandId', 'context', 'objectId', 'receiptId', 'scope', 'state'
  ].sort())
  assert.equal(stored.beforeStatusVersion, 0)
  assert.equal(approvalContextKey.restoreAttempts('status-change-review', contextA).attempts.length, 1)
  assert.equal(approvalContextKey.restoreAttempts('status-change-review', contextB).attempts.length, 0)
})

const variants = [
  {
    name: 'teaching task', file: '../academic-task/index.vue', id: 'T1', collection: 'tasks',
    row: { taskId: 'T1', courseName: 'PLC', status: 'ASSIGNED', statusVersion: 0 },
    api: 'actAcademicTask', read: 'getAcademicMyTasks', act(page, row) { page.doConfirm(row) }
  },
  {
    name: 'exam defer', file: '../exam-defer/index.vue', id: 'D1', collection: 'list',
    row: { deferId: 'D1', studentName: '甲', status: 'TEACHER_CONFIRM', decisionVersion: 0 },
    api: 'reviewAcademicDefer', read: 'getAcademicDeferPending', act(page, row) { page.doAct(row, 'APPROVE') }
  },
  {
    name: 'schedule change', file: './schedule-change-review.vue', id: 'C1', collection: 'list',
    row: { changeId: 'C1', courseName: 'PLC', status: 'SUBMITTED', currentNode: 'COLLEGE_REVIEW', version: 0 },
    api: 'reviewScheduleChange', read: 'getScheduleChangePending', act(page, row) { page.doAct(row, 'APPROVE') }
  },
  {
    name: 'status change', file: './status-change-review.vue', id: 'S1', collection: 'list',
    row: { changeId: 'S1', realName: '甲', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW', decisionVersion: 0 },
    api: 'reviewStatusChange', read: 'getStatusChangePending', act(page, row) { page.doAct(row, 'APPROVE') }
  }
]

for (const variant of variants) {
  test(`${variant.name} restores the exact unresolved object after page recreation without replay`, async () => {
    const storage = makeStorage()
    globalThis.uni = storage
    let posts = 0
    const api = {
      [variant.api]: async () => { posts += 1; return { requestId: `REQ-${variant.id}` } },
      [variant.read]: async () => ({ items: [] })
    }
    const first = createPage(variant.file, { teacherApi: api })
    first.instance[variant.collection] = [variant.row]
    first.instance._loadEpoch = 1
    first.instance._actionContext = first.instance.contextKey()
    variant.act(first.instance, variant.row)
    await settle(); await settle()
    assert.equal(posts, 1)

    const second = createPage(variant.file, { teacherApi: api })
    second.instance.restoreReviewAttempts()
    second.instance[variant.collection] = [variant.row]
    assert.equal(second.instance.reviewLocked(variant.row), true)
    assert.equal(second.instance.unresolvedCount, 1)
    variant.act(second.instance, variant.row)
    await settle()
    assert.equal(posts, 1)
    const stored = parseOnlyStoredRecord(storage)
    assert.equal(stored.objectId, variant.id)
    assert.equal(stored.requestId, `REQ-${variant.id}`)
    assert.equal('studentName' in stored || 'courseName' in stored || 'reason' in stored, false)
  })
}

test('a failed preflight persistence readback sends zero approval requests', async () => {
  const storage = makeStorage()
  storage.failSet = true
  globalThis.uni = storage
  let posts = 0
  const row = { taskId: 'T-storage', courseName: 'PLC', status: 'ASSIGNED' }
  const { instance, events } = createPage('../academic-task/index.vue', {
    teacherApi: { actAcademicTask: async () => { posts += 1; return {} } }
  })
  instance.tasks = [row]
  instance._loadEpoch = 1
  instance._actionContext = instance.contextKey()
  instance.doConfirm(row)
  await settle()
  assert.equal(posts, 0)
  assert.equal(instance.recoveryStorageBlocked, true)
  assert.equal(events.toasts.includes('本机无法保存待核对记录，本次命令未发送'), true)
})

test('queue disappearance is observation only and cannot clear a restored command', async () => {
  const storage = makeStorage()
  globalThis.uni = storage
  const context = JSON.stringify(['tenant', 'teacher', 'teacher', 'ctx'])
  const attempt = approvalContextKey.createAttempt('schedule-change-review', context, 'C-missing', 'APPROVE', { status: 'SUBMITTED', currentNode: 'COLLEGE_REVIEW' })
  assert.equal(approvalContextKey.persistAttempt('schedule-change-review', attempt), true)
  const { instance } = createPage('./schedule-change-review.vue', {
    teacherApi: { getScheduleChangePending: async () => ({ items: [] }) }
  })
  instance._actionContext = context
  instance.restoreReviewAttempts(context)
  await instance.load()
  assert.equal(instance.unresolvedCount, 1)
  assert.equal(approvalContextKey.restoreAttempts('schedule-change-review', context).attempts.length, 1)
})

test('403 clears private evidence but the persisted unresolved reference survives recreation', async () => {
  const storage = makeStorage()
  globalThis.uni = storage
  const row = { changeId: 'S-403', realName: '私密姓名', reason: '私密材料', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW' }
  const first = createPage('./status-change-review.vue', {
    teacherApi: { reviewStatusChange: async () => { throw { status: 403, requestId: 'REQ-403' } } }
  })
  first.instance.list = [row]
  first.instance.detailId = row.changeId
  first.instance._loadEpoch = 1
  first.instance._actionContext = first.instance.contextKey()
  first.instance.doAct(row, 'APPROVE')
  await settle(); await settle()
  assert.equal(first.instance.list.length, 0)
  assert.equal(first.instance.detailId, '')
  const second = createPage('./status-change-review.vue')
  second.instance.restoreReviewAttempts()
  assert.equal(second.instance.unresolvedCount, 1)
  const stored = parseOnlyStoredRecord(storage)
  assert.equal(stored.objectId, 'S-403')
  assert.equal(stored.requestId, 'REQ-403')
  assert.equal('realName' in stored || 'reason' in stored, false)
})

test('an exact ACK is not reported successful when persisted lock removal cannot be verified', async () => {
  const storage = makeStorage()
  globalThis.uni = storage
  const row = { deferId: 'D-clear', studentName: '甲', status: 'TEACHER_CONFIRM', decisionVersion: 0 }
  const { instance, events } = createPage('../exam-defer/index.vue', {
    teacherApi: { reviewAcademicDefer: async () => {
      storage.failRemove = true
      return { deferId: 'D-clear', status: 'APPROVED', decisionVersion: 1 }
    } }
  })
  instance.list = [row]
  instance._loadEpoch = 1
  instance._actionContext = instance.contextKey()
  instance.doAct(row, 'APPROVE')
  await settle(); await settle()
  assert.equal(instance.reviewLocked(row), true)
  assert.equal(instance.recoveryStorageBlocked, true)
  assert.equal(events.toasts.includes('已通过'), false)
  assert.equal(parseOnlyStoredRecord(storage).objectId, 'D-clear')
})

test('an exact changed ACK clears the durable reference before reporting success', async () => {
  const storage = makeStorage()
  globalThis.uni = storage
  const row = { taskId: 'T-done', courseName: 'PLC', status: 'ASSIGNED', statusVersion: 0 }
  const { instance, events } = createPage('../academic-task/index.vue', {
    teacherApi: {
      actAcademicTask: async () => ({ taskId: 'T-done', status: 'TEACHER_CONFIRMED', statusVersion: 1 }),
      getAcademicMyTasks: async () => ({ items: [] })
    }
  })
  instance.tasks = [row]
  instance._loadEpoch = 1
  instance._actionContext = instance.contextKey()
  instance.doConfirm(row)
  await settle(); await settle()
  assert.equal(storage.values.size, 0)
  assert.equal(instance.reviewLocked(row), false)
  assert.equal(events.toasts.includes('已确认'), true)
  const recreated = createPage('../academic-task/index.vue')
  recreated.instance.restoreReviewAttempts()
  assert.equal(recreated.instance.unresolvedCount, 0)
})
