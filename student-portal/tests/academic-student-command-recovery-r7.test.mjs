import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import * as uiHelpers from '../src/components/academic/studentAcademicUi.js'
import * as commandGuard from '../src/components/academic/studentAcademicCommandGuard.js'
import * as localization from '../src/services/visibleEnumLocalization.js'

class FakeStorage {
  constructor() { this.values = new Map() }
  get length() { return this.values.size }
  key(index) { return [...this.values.keys()][index] ?? null }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null }
  setItem(key, value) { if (!this.ignoreSet) this.values.set(String(key), String(value)) }
  removeItem(key) { if (!this.ignoreRemove) this.values.delete(String(key)) }
  clear() { this.values.clear() }
}

const defaultSession = () => ({ activeContextId: 'ctx-student-A', user: { userId: 'student-A', studentNo: 'S001', roleCode: 'STUDENT', userType: 'STUDENT' }, token: 'rotating-token-A' })

function mount(name, api = {}, query = {}, browser = {}, session = defaultSession()) {
  if (typeof api.profileEnrollment !== 'function') api.profileEnrollment = async () => ({})
  const source = readFileSync(new URL(`../src/views/academic/Student${name}View.vue`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  let script = compileScript(descriptor, { id: `r7-${name}` }).content
  const disposers = []
  const modules = {
    vue: { ...vue, onMounted: () => {}, onBeforeUnmount: (fn) => disposers.push(fn) },
    'vue-router': { useRoute: () => ({ query, meta: {} }), useRouter: () => ({ push() {} }) },
    '../../services/portalApi': { portalApi: api },
    '../../services/systemDialog': { systemConfirm: async () => true, systemAlert: async () => true, systemPrompt: async () => null },
    '../../services/printInApp': { createInAppPrintFrame: () => browser.open ? browser.open() : { document: {}, closed: false, close() {}, focus() {}, print() {} } },
    '../../services/visibleEnumLocalization': localization,
    '../../stores/session': { useSessionStore: () => session },
    '../../stores/ui': { useUiStore: () => ({ notify() {} }) },
    '../../components/academic/studentAcademicUi': uiHelpers,
    '../../components/academic/studentAcademicCommandGuard': commandGuard
  }
  script = script.replace(/^import (.+?) from ['"](.+?)['"];?$/gm, (_, binding, path) => {
    if (binding.startsWith('{')) return `const ${binding.replace(/\bas\b/g, ':')} = modules[${JSON.stringify(path)}]`
    return `const ${binding} = {}`
  }).replace('export default', 'return')
  const component = new Function('modules', 'window', script)(modules, { confirm: () => true, prompt: () => null, ...browser })
  return { ...component.setup({}, { expose() {} }), dispose: () => disposers.forEach((fn) => fn()) }
}

function seed(session, context, action, objectId, ackId = '') {
  const guard = commandGuard.createStudentAcademicCommandGuard(() => commandGuard.studentAcademicIdentity(session), context)
  const reference = guard.preparePersistentCommand({ action, objectId, reason: '不得保存', body: { secret: true }, answers: { score: 99 } })
  assert.ok(reference)
  return ackId ? guard.rememberPersistentAck(reference, ackId) : reference
}

test('persistent identity is stable across token rotation and separates users and roles', () => {
  const session = defaultSession()
  const before = commandGuard.studentAcademicIdentity(session)
  session.token = 'rotating-token-B'
  assert.equal(commandGuard.studentAcademicIdentity(session), before)
  session.user.roleCode = 'OTHER'
  assert.notEqual(commandGuard.studentAcademicIdentity(session), before)
  session.user.roleCode = 'STUDENT'; session.activeContextId = 'ctx-student-B'
  assert.notEqual(commandGuard.studentAcademicIdentity(session), before)
  assert.doesNotMatch(before, /rotating-token/)
  assert.equal(commandGuard.studentAcademicIdentity({ user: { roleCode: 'STUDENT', userType: 'STUDENT' } }), '')
})

test('guard stores only the versioned minimal reference and restores it across instances', () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const session = defaultSession()
  const reference = seed(session, 'recheck', 'SUBMIT_RECHECK', '101', '501')
  assert.equal(reference.ackId, '501')
  const raw = [...storage.values.values()].join('')
  assert.doesNotMatch(raw, /不得保存|secret|answers|score|rotating-token/)
  assert.deepEqual(Object.keys(JSON.parse(raw)[0]).sort(), ['ackId', 'action', 'commandKey', 'context', 'identity', 'objectId', 'parentId', 'version'])
  assert.equal(JSON.parse(raw)[0].version, 2)
  const reopened = commandGuard.createStudentAcademicCommandGuard(() => commandGuard.studentAcademicIdentity(session), 'recheck')
  assert.equal(reopened.pendingCommands()[0].ackId, '501')
  const otherSession = { user: { userId: 'student-B', studentNo: 'S002', roleCode: 'STUDENT', userType: 'STUDENT' } }
  const otherStudent = commandGuard.createStudentAcademicCommandGuard(() => commandGuard.studentAcademicIdentity(otherSession), 'recheck')
  assert.deepEqual(otherStudent.pendingCommands(), [])
  assert.equal(reopened.pendingCommands().length, 1)
  delete globalThis.localStorage
})

test('corrupt, unavailable, over-capacity, or unverified storage fails closed without losing old references', () => {
  const session = defaultSession()
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const guard = commandGuard.createStudentAcademicCommandGuard(() => commandGuard.studentAcademicIdentity(session), 'capacity')
  const first = guard.preparePersistentCommand({ action: 'WRITE', objectId: '1' })
  assert.ok(first)
  assert.equal(guard.preparePersistentCommand({ action: 'WRITE', objectId: '1' }), null)
  assert.equal(guard.pendingCommands()[0].commandKey, first.commandKey)
  for (let index = 2; index <= 16; index += 1) assert.ok(guard.preparePersistentCommand({ action: 'WRITE', objectId: String(index) }))
  assert.equal(guard.preparePersistentCommand({ action: 'WRITE', objectId: '17' }), null)
  assert.equal(guard.pendingCommands().length, 16)
  assert.equal(guard.pendingCommands()[0].commandKey, first.commandKey)

  const key = storage.key(0)
  storage.values.set(key, '{broken')
  const corrupted = guard.pendingCommands()
  assert.equal(corrupted.persistenceError, 'STORAGE_CORRUPTED')
  assert.equal(guard.persistenceState().ok, false)
  assert.equal(guard.preparePersistentCommand({ action: 'WRITE', objectId: '18' }), null)
  assert.equal(storage.getItem(key), '{broken')

  const silent = new FakeStorage(); silent.ignoreSet = true; globalThis.localStorage = silent
  const silentGuard = commandGuard.createStudentAcademicCommandGuard(() => commandGuard.studentAcademicIdentity(session), 'silent')
  assert.equal(silentGuard.preparePersistentCommand({ action: 'WRITE', objectId: '1' }), null)
  assert.equal(silentGuard.persistenceState().count, 0)
  delete globalThis.localStorage
})

test('original identity and commandKey prevent stale handles from changing or deleting a later command', () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const session = defaultSession()
  const guard = commandGuard.createStudentAcademicCommandGuard(() => commandGuard.studentAcademicIdentity(session), 'stale-handle')
  const old = guard.preparePersistentCommand({ action: 'WRITE', objectId: '1' })
  assert.ok(old)
  assert.equal(guard.completePersistentCommand(old), true)
  const current = guard.preparePersistentCommand({ action: 'WRITE', objectId: '1' })
  assert.ok(current); assert.notEqual(current.commandKey, old.commandKey)
  assert.equal(guard.rememberPersistentAck(old, '101'), null)
  assert.equal(guard.completePersistentCommand(old), false)
  assert.equal(guard.pendingCommands()[0].commandKey, current.commandKey)

  session.activeContextId = 'ctx-student-B'
  assert.equal(guard.rememberPersistentAck(current, '102'), null)
  assert.equal(guard.completePersistentCommand(current), false)
  assert.equal(guard.pendingCommands().length, 0)
  session.activeContextId = 'ctx-student-A'
  assert.equal(guard.pendingCommands()[0].commandKey, current.commandKey)

  storage.ignoreRemove = true
  assert.equal(guard.completePersistentCommand(current), false)
  assert.equal(guard.pendingCommands()[0].commandKey, current.commandKey)
  delete globalThis.localStorage
})

test('seven application pages recover exact ACK records by GET without replaying POST', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const session = defaultSession()
  let posts = 0

  seed(session, 'recheck', 'SUBMIT_RECHECK', '101', '501')
  const recheck = mount('Recheck', { academicGradeRecheck: async () => [{ recheckId: '501', acadGradeId: '101', status: 'SUBMITTED' }], academicTranscript: async () => ({ items: [{ gradeId: '101', courseName: '数学' }] }), academicGradeRecheckSubmit: async () => { posts += 1 } }, {}, {}, session)
  await recheck.load(); assert.equal(recheck.receiptTone.value, 'success')

  seed(session, 'recognition', 'SUBMIT_RECOGNITION', '201', '601')
  const recognition = mount('Recognition', { academicRecognition: async () => [{ recognitionId: '601', targetCourseId: '201', targetCourseName: '物理', status: 'SUBMITTED' }], academicRecognitionCourses: async () => ({ items: [] }), academicRecognitionSubmit: async () => { posts += 1 } }, {}, {}, session)
  await recognition.load(); assert.equal(recognition.receiptTone.value, 'success')

  seed(session, 'makeup', 'APPLY_RETAKE', '301', '701')
  seed(session, 'makeup', 'APPLY_EXEMPTION', '302', '702')
  const makeup = mount('Makeup', { academicMakeup: async () => ({ retakes: [{ retakeId: '701', originGradeId: '301', courseName: '语文', status: 'SUBMITTED' }], exemptions: [{ exemptionId: '702', courseId: '302', courseName: '英语', status: 'SUBMITTED' }] }), academicMakeupOptions: async () => ({}), academicRetakeApply: async () => { posts += 1 }, academicExemptionApply: async () => { posts += 1 } }, {}, {}, session)
  await makeup.load(); assert.deepEqual(makeup.uncertainKeys.value, [])

  seed(session, 'exam-defer', 'APPLY_DEFER', '401', '801')
  seed(session, 'exam-defer', 'RESUBMIT_DEFER', '802', '802')
  const exam = mount('Exam', { academicExam: async () => [], academicExamDeferOptions: async () => [], academicExamDefer: async () => [{ deferId: '801', examCourseId: '401', status: 'SUBMITTED' }, { deferId: '802', examCourseId: '402', status: 'SUBMITTED' }], academicExamDeferApply: async () => { posts += 1 }, academicExamDeferResubmit: async () => { posts += 1 } }, {}, {}, session)
  await exam.load(); assert.deepEqual(exam.uncertainKeys.value, [])

  seed(session, 'evaluation', 'SUBMIT_EVALUATION', '901', '901')
  const evaluation = mount('Evaluation', { academicEvaluationTasks: async () => ({ list: [{ taskId: '901', submitted: true, courseName: '化学' }] }), academicEvaluationSubmit: async () => { posts += 1 } }, {}, {}, session)
  await evaluation.load(); assert.equal(evaluation.receiptTone.value, 'success')

  seed(session, 'registration', 'REGISTER_TERM', '1001', '1101')
  seed(session, 'registration', 'DEFER_REGISTRATION', '1002', '1102')
  const registration = mount('Registration', { academicRegistration: async () => ({ batches: [{ batchId: '1001', registrationId: '1101', registrationStatus: 'REGISTERED' }, { batchId: '1002', deferral: { deferralId: '1102', status: 'PENDING' } }] }), academicRegistrationRegister: async () => { posts += 1 }, academicRegistrationDefer: async () => { posts += 1 } }, {}, {}, session)
  await registration.load(); assert.deepEqual(registration.uncertainRegistrations.value, {}); assert.deepEqual(registration.uncertainDeferralKeys.value, [])

  seed(session, 'major-split', 'SUBMIT_MAJOR_SPLIT', '1201', '1301')
  const major = mount('MajorSplit', { academicMajorSplit: async () => ({ openBatches: [], myVolunteers: [{ volunteerId: '1301', batchId: '1201', status: 'SUBMITTED' }] }), academicMajorSplitSubmit: async () => { posts += 1 } }, {}, {}, session)
  await major.load(); assert.equal(major.receiptTone.value, 'success')

  assert.equal(posts, 0)
  assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('a command without an ACK survives reload and cannot claim an old similar record', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const session = defaultSession()
  seed(session, 'recheck', 'SUBMIT_RECHECK', '101')
  const page = mount('Recheck', { academicGradeRecheck: async () => [{ recheckId: 'OLD', acadGradeId: '101', status: 'SUBMITTED' }], academicTranscript: async () => ({ items: [{ gradeId: '101', courseName: '数学' }] }) }, {}, {}, session)
  await page.load()
  assert.equal(page.receiptTone.value, 'waiting')
  assert.match(page.receipt.value.status, /未取得服务端回执编号/)
  assert.equal(page.uncertainGradeId.value, '101')
  assert.equal(storage.length, 1)
  delete globalThis.localStorage
})

test('403 clears page privacy but retains the minimal reference for a later exact GET', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  const session = defaultSession(); seed(session, 'recheck', 'SUBMIT_RECHECK', '101', '501')
  const denied = Object.assign(new Error('禁止访问'), { status: 403 })
  const first = mount('Recheck', { academicGradeRecheck: async () => { throw denied }, academicTranscript: async () => ({ items: [] }) }, {}, {}, session)
  await first.load(); assert.deepEqual(first.records.value, []); assert.equal(storage.length, 1)
  const reopened = mount('Recheck', { academicGradeRecheck: async () => [{ recheckId: '501', acadGradeId: '101', status: 'SUBMITTED' }], academicTranscript: async () => ({ items: [{ gradeId: '101', courseName: '数学' }] }) }, {}, {}, session)
  await reopened.load(); assert.equal(reopened.receiptTone.value, 'success'); assert.equal(storage.length, 0)
  delete globalThis.localStorage
})

test('a 503 carrying a misleading 409 business code remains pending and is never retried', async () => {
  const storage = new FakeStorage(); globalThis.localStorage = storage
  let posts = 0
  const uncertain = Object.assign(new Error('upstream timeout'), { status: 503, bizCode: 409001 })
  const page = mount('Recheck', {
    academicGradeRecheck: async () => [],
    academicTranscript: async () => ({ items: [{ gradeId: '101', courseName: '数学' }] }),
    academicGradeRecheckSubmit: async () => { posts += 1; throw uncertain }
  })
  page.grades.value = [{ gradeId: '101', courseName: '数学' }]
  page.selectedGradeId.value = '101'; page.reason.value = '请核对本人正式成绩'
  await page.submit()
  assert.equal(posts, 1)
  assert.equal(page.receiptTone.value, 'waiting')
  assert.equal(page.uncertainGradeId.value, '101')
  assert.equal(storage.length, 1)
  assert.equal(JSON.parse([...storage.values.values()][0])[0].ackId, '')
  delete globalThis.localStorage
})

test('storage failure prevents the write and all seven pages gate POST behind persistence', async () => {
  globalThis.localStorage = { getItem() { return null }, setItem() { throw new Error('quota') }, removeItem() {} }
  let posts = 0
  const page = mount('Recheck', { academicGradeRecheckSubmit: async () => { posts += 1 } })
  page.grades.value = [{ gradeId: '101', courseName: '数学' }]
  page.selectedGradeId.value = '101'; page.reason.value = '请核对本人正式成绩'
  await page.submit()
  assert.equal(posts, 0)
  assert.match(page.receipt.value.status, /无法保存/)

  const files = ['Recheck', 'Recognition', 'Makeup', 'Exam', 'Evaluation', 'Registration', 'MajorSplit']
  for (const name of files) {
    const source = readFileSync(new URL(`../src/views/academic/Student${name}View.vue`, import.meta.url), 'utf8')
    assert.match(source, /preparePersistentCommand/)
  }
  delete globalThis.localStorage
})
