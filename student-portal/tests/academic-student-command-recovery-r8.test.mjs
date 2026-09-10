import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import * as uiHelpers from '../src/components/academic/studentAcademicUi.js'
import * as commandGuard from '../src/components/academic/studentAcademicCommandGuard.js'

class FakeStorage {
  constructor() { this.values = new Map(); this.failWrites = false; this.failRemoves = false }
  get length() { return this.values.size }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null }
  setItem(key, value) { if (this.failWrites) throw new Error('storage unavailable'); this.values.set(String(key), String(value)) }
  removeItem(key) { if (this.failWrites || this.failRemoves) throw new Error('storage unavailable'); this.values.delete(String(key)) }
}

const session = () => ({ activeContextId: 'ctx-student-A', user: { userId: 'student-A', studentNo: 'S001', roleCode: 'STUDENT', userType: 'STUDENT' } })

function mount(name, api = {}, currentSession = session()) {
  if (typeof api.profileEnrollment !== 'function') api.profileEnrollment = async () => ({})
  const source = readFileSync(new URL(`../src/views/academic/Student${name}View.vue`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  let script = compileScript(descriptor, { id: `r8-${name}` }).content
  const disposers = []
  const modules = {
    vue: { ...vue, onMounted: () => {}, onBeforeUnmount: (fn) => disposers.push(fn) },
    '../../services/portalApi': { portalApi: api },
    '../../stores/session': { useSessionStore: () => currentSession },
    '../../stores/ui': { useUiStore: () => ({ notify() {} }) },
    '../../services/systemDialog': { systemConfirm: async () => true, systemAlert: async () => true, systemPrompt: async () => null },
    '../../components/academic/studentAcademicUi': uiHelpers,
    '../../components/academic/studentAcademicCommandGuard': commandGuard
  }
  script = script.replace(/^import (.+?) from ['"](.+?)['"];?$/gm, (_, binding, path) => {
    if (binding.startsWith('{')) return `const ${binding.replace(/\bas\b/g, ':')} = modules[${JSON.stringify(path)}]`
    return `const ${binding} = {}`
  }).replace('export default', 'return')
  const component = new Function('modules', 'window', script)(modules, { confirm: () => true })
  return { ...component.setup({}, { expose() {} }), dispose: () => disposers.forEach((fn) => fn()) }
}

function seed(currentSession, context, action, objectId, ackId = '', parentId = '') {
  const guard = commandGuard.createStudentAcademicCommandGuard(() => commandGuard.studentAcademicIdentity(currentSession), context)
  const reference = guard.preparePersistentCommand({ action, objectId, parentId })
  assert.ok(reference)
  return ackId ? guard.rememberPersistentAck(reference, ackId) : reference
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('selection restores only the exact ACK record and never replays enroll', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); const id = '9007199254740993'; let posts = 0
  seed(currentSession, 'selection', 'ENROLL_SELECTION', id, '7001', '8001')
  const page = mount('Selection', {
    academicCourseSelection: async () => [{ batch: { batchId: '8001' }, courses: [{ selectionCourseId: id, courseName: '精确编号课程', allowedActions: [] }] }],
    academicSelectionRecords: async () => [{ recordId: '7001', selectionCourseId: id, batchId: '8001', courseName: '精确编号课程', status: 'LOCKED' }],
    academicEnroll: async () => { posts += 1 }
  }, currentSession)
  await page.load()
  assert.equal(page.receiptTone.value, 'success')
  assert.equal(page.receipt.value.status, '名单已锁定')
  assert.equal(page.pendingOperation.value, null)
  assert.equal(posts, 0)
  assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('selection without an ACK cannot attribute an old same-course record and query never replays POST', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); let reads = 0; let posts = 0
  seed(currentSession, 'selection', 'ENROLL_SELECTION', '101', '', '201')
  const page = mount('Selection', {
    academicCourseSelection: async () => [{ batch: { batchId: '201' }, courses: [{ selectionCourseId: '101', courseName: '旧课程', allowedActions: [] }] }],
    academicSelectionRecords: async () => { reads += 1; return [{ recordId: 'OLD', selectionCourseId: '101', batchId: '201', status: 'SELECTED' }] },
    academicEnroll: async () => { posts += 1 }
  }, currentSession)
  await page.load(); await page.confirmPending()
  assert.equal(page.receiptTone.value, 'waiting')
  assert.match(page.receipt.value.title, /待确认/)
  assert.ok(page.pendingOperation.value)
  assert.equal(posts, 0)
  assert.equal(reads, 2)
  assert.equal(storage.length, 1)
  delete globalThis.localStorage
})

test('live enroll and drop keep preflight, exact ACK, and formal GET order', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const calls = []; let state = 'DROPPED'; const currentSession = session()
  const course = { selectionCourseId: '101', recordId: '501', batchId: '201', courseName: '网络课程', allowedActions: ['ENROLL'] }
  const page = mount('Selection', {
    academicSelectionPreflight: async () => { calls.push('ENROLL_PREFLIGHT'); return { allowed: true } },
    academicEnroll: async () => { calls.push('ENROLL'); state = 'SELECTED'; return { recordId: '501', selectionCourseId: '101' } },
    academicSelectionDropPreflight: async () => { calls.push('DROP_PREFLIGHT'); return { allowed: true, action: 'DROP', selectionCourseId: '101', selectionRecordId: '501', batchId: '201' } },
    academicDrop: async () => { calls.push('DROP'); state = 'DROPPED'; return { recordId: '501', status: state } },
    academicSelectionRecords: async () => { calls.push('GET'); return [{ ...course, status: state }] },
    academicCourseSelection: async () => { calls.push('COURSES'); return [] }
  }, currentSession)
  page.activeBatchId.value = '201'
  await page.enroll(course)
  assert.deepEqual(calls.slice(0, 4), ['ENROLL_PREFLIGHT', 'ENROLL', 'GET', 'COURSES'])
  assert.equal(page.receiptTone.value, 'success')
  course.allowedActions = ['DROP']; calls.length = 0
  await page.drop(course)
  assert.deepEqual(calls.slice(0, 4), ['DROP_PREFLIGHT', 'DROP', 'GET', 'COURSES'])
  assert.equal(page.receipt.value.status, '已退')
  assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('textbook recovery needs its exact ACK and never turns signing into payment', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); let posts = 0
  seed(currentSession, 'textbook-sign', 'SIGN_TEXTBOOK', '301', '301')
  const page = mount('Textbook', {
    academicTextbook: async () => ({ distributions: [{ recordId: '301', textbookName: '前端工程化', status: 'RECEIVED', receivedAt: '2026-09-09' }], fees: { totalDue: 73, totalPaid: 0, unpaid: 73 } }),
    academicTextbookSign: async () => { posts += 1 }
  }, currentSession)
  await page.load()
  assert.equal(page.receiptTone.value, 'success')
  assert.match(page.receipt.value.next, /不代表缴费/)
  assert.equal(page.fees.value.totalPaid, 0)
  assert.equal(posts, 0)
  assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('live textbook signing stores its reference before POST and closes only after exact formal GET', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); const calls = []; let status = 'PENDING'
  const book = { recordId: '301', textbookName: '前端工程化', status: 'PENDING' }
  const page = mount('Textbook', {
    academicTextbookSign: async () => { calls.push('SIGN'); status = 'RECEIVED'; return { recordId: '301', status } },
    academicTextbook: async () => { calls.push('GET'); return { distributions: [{ ...book, status }], fees: { totalDue: 73, totalPaid: 0, unpaid: 73 } } }
  }, currentSession)
  await page.sign(book)
  assert.deepEqual(calls, ['SIGN', 'GET'])
  assert.equal(page.receiptTone.value, 'success')
  assert.match(page.receipt.value.next, /不代表缴费/)
  assert.equal(page.fees.value.totalPaid, 0)
  assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('textbook and level exam never close a restored command that has no ACK', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session()
  seed(currentSession, 'textbook-sign', 'SIGN_TEXTBOOK', '301')
  const textbook = mount('Textbook', { academicTextbook: async () => ({ distributions: [{ recordId: '301', textbookName: '旧教材记录', status: 'RECEIVED' }] }) }, currentSession)
  await textbook.load()
  assert.equal(textbook.receiptTone.value, 'waiting')
  assert.match(textbook.receipt.value.status, /未取得服务端回执编号/)

  seed(currentSession, 'level-exam', 'REGISTER_LEVEL_EXAM', '401')
  const level = mount('LevelExam', { academicLevelExam: async () => ({ openExams: [{ examId: '401', examName: '旧报名', status: 'OPEN' }], myRegs: [{ regId: 'OLD', examId: '401', status: 'REGISTERED' }] }) }, currentSession)
  await level.load()
  assert.equal(level.receiptTone.value, 'waiting')
  assert.match(level.receipt.value.status, /未取得服务端报名编号/)
  assert.equal(storage.length, 2)
  delete globalThis.localStorage
})

test('level exam register and cancel recover by exact regId without implying payment or a certificate', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); let posts = 0
  seed(currentSession, 'level-exam', 'REGISTER_LEVEL_EXAM', '401', '601')
  const registered = mount('LevelExam', {
    academicLevelExam: async () => ({ openExams: [{ examId: '401', examName: '普通话', status: 'OPEN' }], myRegs: [{ regId: '601', examId: '401', status: 'REGISTERED', feeStatus: 'UNPAID', score: 0, result: 'FAIL' }] }),
    academicLevelRegister: async () => { posts += 1 }
  }, currentSession)
  await registered.load()
  assert.equal(registered.receiptTone.value, 'success')
  assert.match(registered.personalResult(registered.exams.value[0]), /未缴费.*不合格.*成绩 0/)
  assert.equal(posts, 0)

  seed(currentSession, 'level-exam', 'CANCEL_LEVEL_EXAM', '402', '602')
  const cancelled = mount('LevelExam', {
    academicLevelExam: async () => ({ openExams: [], myRegs: [{ regId: '602', examId: '402', examName: '英语等级', status: 'CANCELLED', feeStatus: 'UNPAID' }] }),
    academicLevelCancel: async () => { posts += 1 }
  }, currentSession)
  await cancelled.load()
  assert.equal(cancelled.receiptTone.value, 'success')
  assert.equal(cancelled.receipt.value.status, '已取消')
  assert.equal(posts, 0)
  assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('storage failure prevents POST on selection, textbook, and level exam', async () => {
  const storage = new FakeStorage(); storage.failWrites = true; globalThis.localStorage = storage
  let posts = 0
  const selection = mount('Selection', { academicSelectionPreflight: async () => ({ allowed: true }), academicEnroll: async () => { posts += 1 } })
  await selection.enroll({ selectionCourseId: '101', courseName: '课程', allowedActions: ['ENROLL'] })
  const textbook = mount('Textbook', { academicTextbookSign: async () => { posts += 1 } })
  await textbook.sign({ recordId: '301', textbookName: '教材', status: 'PENDING' })
  const level = mount('LevelExam', { academicLevelRegister: async () => { posts += 1 } })
  await level.register({ examId: '401', examName: '考试', status: 'OPEN' })
  assert.equal(posts, 0)
  assert.match(selection.receipt.value.status, /无法保存/)
  assert.match(textbook.receipt.value.status, /无法保存/)
  assert.match(level.receipt.value.status, /无法保存/)
  delete globalThis.localStorage
})

test('unsafe numeric ids are rejected before preflight or POST on all three pages', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const unsafe = Number('9007199254740993'); let reads = 0; let posts = 0
  const selection = mount('Selection', { academicSelectionPreflight: async () => { reads += 1 }, academicEnroll: async () => { posts += 1 } })
  await selection.enroll({ selectionCourseId: unsafe, allowedActions: ['ENROLL'] })
  const textbook = mount('Textbook', { academicTextbookSign: async () => { posts += 1 } })
  await textbook.sign({ recordId: unsafe, status: 'PENDING' })
  const level = mount('LevelExam', { academicLevelRegister: async () => { posts += 1 } })
  await level.register({ examId: unsafe, status: 'OPEN' })
  assert.equal(reads, 0); assert.equal(posts, 0); assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('a late selection 403 from the old active context cannot clear the new student page', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); const courses = deferred(); const records = deferred()
  const page = mount('Selection', { academicCourseSelection: () => courses.promise, academicSelectionRecords: () => records.promise }, currentSession)
  const loading = page.load()
  currentSession.activeContextId = 'ctx-student-B'
  page.rawGroups.value = [{ batch: { batchId: 'NEW' }, courses: [] }]
  page.records.value = [{ recordId: 'NEW-RECORD' }]
  page.receipt.value = { title: '新身份页面' }
  courses.reject(Object.assign(new Error('旧身份禁止访问'), { status: 403 })); records.resolve([])
  await loading
  assert.equal(page.groups.value[0].batch.batchId, 'NEW')
  assert.equal(page.records.value[0].recordId, 'NEW-RECORD')
  assert.equal(page.receipt.value.title, '新身份页面')
  delete globalThis.localStorage
})

test('formal confirmation stays pending when its persistent reference cannot be safely deleted', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session()
  seed(currentSession, 'selection', 'ENROLL_SELECTION', '101', '501', '201')
  seed(currentSession, 'textbook-sign', 'SIGN_TEXTBOOK', '301', '301')
  seed(currentSession, 'level-exam', 'REGISTER_LEVEL_EXAM', '401', '601')
  storage.failRemoves = true
  const selection = mount('Selection', {
    academicCourseSelection: async () => [{ batch: { batchId: '201' }, courses: [{ selectionCourseId: '101', courseName: '课程', allowedActions: [] }] }],
    academicSelectionRecords: async () => [{ recordId: '501', selectionCourseId: '101', batchId: '201', status: 'SELECTED' }]
  }, currentSession)
  const textbook = mount('Textbook', { academicTextbook: async () => ({ distributions: [{ recordId: '301', textbookName: '教材', status: 'RECEIVED' }] }) }, currentSession)
  const level = mount('LevelExam', { academicLevelExam: async () => ({ openExams: [{ examId: '401', examName: '考试', status: 'OPEN' }], myRegs: [{ regId: '601', examId: '401', status: 'REGISTERED' }] }) }, currentSession)
  await selection.load(); await textbook.load(); await level.load()
  assert.equal(selection.receiptTone.value, 'waiting')
  assert.ok(selection.pendingOperation.value)
  assert.equal(textbook.receiptTone.value, 'waiting')
  assert.deepEqual(textbook.pendingRecordIds.value, ['301'])
  assert.equal(level.receiptTone.value, 'waiting')
  assert.deepEqual(level.pendingExamIds.value, ['401'])
  assert.equal(storage.length, 3)
  delete globalThis.localStorage
})

test('a stale selection command cannot release a later identity busy lock or write a late 403 receipt', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); const oldPreflight = deferred(); const newPreflight = deferred()
  let preflightCount = 0
  const page = mount('Selection', {
    academicSelectionPreflight: () => (++preflightCount === 1 ? oldPreflight.promise : newPreflight.promise),
    academicCourseSelection: async () => [], academicSelectionRecords: async () => []
  }, currentSession)
  const oldCommand = page.enroll({ selectionCourseId: '101', courseName: '旧身份课程', allowedActions: ['ENROLL'] })
  assert.equal(page.actingId.value, '101')
  currentSession.activeContextId = 'ctx-student-B'
  await page.load()
  assert.equal(page.actingId.value, '')
  const newCommand = page.enroll({ selectionCourseId: '101', courseName: '新身份课程', allowedActions: ['ENROLL'] })
  assert.equal(page.actingId.value, '101')
  oldPreflight.resolve({ allowed: true })
  await oldCommand
  assert.equal(page.actingId.value, '101')
  newPreflight.resolve({ allowed: false })
  await newCommand
  assert.equal(page.actingId.value, '')

  const delayedSession = session(); const coursesStarted = deferred(); const lateCourses = deferred()
  const delayedPage = mount('Selection', {
    academicSelectionPreflight: async () => ({ allowed: true }),
    academicEnroll: async () => ({ recordId: '501', selectionCourseId: '101' }),
    academicSelectionRecords: async () => [{ recordId: '501', selectionCourseId: '101', batchId: '201', status: 'SELECTED' }],
    academicCourseSelection: () => { coursesStarted.resolve(); return lateCourses.promise }
  }, delayedSession)
  const delayedCommand = delayedPage.enroll({ selectionCourseId: '101', courseName: '旧读取', allowedActions: ['ENROLL'] })
  await coursesStarted.promise
  delayedSession.activeContextId = 'ctx-student-B'
  delayedPage.receipt.value = { title: '新身份页面' }
  lateCourses.reject(Object.assign(new Error('旧身份禁止访问'), { status: 403 }))
  await delayedCommand
  assert.equal(delayedPage.receipt.value.title, '新身份页面')
  delete globalThis.localStorage
})

test('textbook and level-exam late 403 reads cannot clear a newer identity page', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const textbookSession = session(); const textbookRead = deferred()
  const textbook = mount('Textbook', { academicTextbook: () => textbookRead.promise }, textbookSession)
  const textbookLoad = textbook.load()
  textbookSession.activeContextId = 'ctx-student-B'
  textbook.records.value = [{ recordId: 'NEW-TEXTBOOK' }]; textbook.receipt.value = { title: '新身份教材页' }
  textbookRead.reject(Object.assign(new Error('旧身份禁止访问'), { status: 403 }))
  await textbookLoad
  assert.equal(textbook.records.value[0].recordId, 'NEW-TEXTBOOK')
  assert.equal(textbook.receipt.value.title, '新身份教材页')

  const levelSession = session(); const levelRead = deferred()
  const level = mount('LevelExam', { academicLevelExam: () => levelRead.promise }, levelSession)
  const levelLoad = level.load()
  levelSession.activeContextId = 'ctx-student-B'
  level.data.value = { openExams: [{ examId: 'NEW-EXAM' }] }; level.receipt.value = { title: '新身份等级考试页' }
  levelRead.reject(Object.assign(new Error('旧身份禁止访问'), { status: 403 }))
  await levelLoad
  assert.equal(level.data.value.openExams[0].examId, 'NEW-EXAM')
  assert.equal(level.receipt.value.title, '新身份等级考试页')
  delete globalThis.localStorage
})

test('403 clears private page state but retains all three minimal recovery references', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const currentSession = session(); const denied = Object.assign(new Error('禁止访问'), { status: 403 })
  seed(currentSession, 'selection', 'ENROLL_SELECTION', '101', '501')
  seed(currentSession, 'textbook-sign', 'SIGN_TEXTBOOK', '301', '301')
  seed(currentSession, 'level-exam', 'REGISTER_LEVEL_EXAM', '401', '601')
  const selection = mount('Selection', { academicCourseSelection: async () => { throw denied }, academicSelectionRecords: async () => [] }, currentSession)
  const textbook = mount('Textbook', { academicTextbook: async () => { throw denied } }, currentSession)
  const level = mount('LevelExam', { academicLevelExam: async () => { throw denied } }, currentSession)
  await selection.load(); await textbook.load(); await level.load()
  assert.deepEqual(selection.records.value, []); assert.deepEqual(textbook.records.value, []); assert.deepEqual(level.data.value, {})
  assert.equal(selection.receipt.value, null); assert.equal(textbook.receipt.value, null); assert.equal(level.receipt.value, null)
  assert.equal(storage.length, 3)
  delete globalThis.localStorage
})
