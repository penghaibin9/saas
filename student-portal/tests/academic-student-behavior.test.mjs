import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import * as uiHelpers from '../src/components/academic/studentAcademicUi.js'
import * as commandGuard from '../src/components/academic/studentAcademicCommandGuard.js'
import * as localization from '../src/services/visibleEnumLocalization.js'

// Execute the real Vue setup functions with controlled API outcomes; no source-text assertions.
function mount(name, api = {}, query = {}, meta = {}, browser = {}) {
  if (typeof api.profileEnrollment !== 'function') api.profileEnrollment = async () => ({ hasData: false })
  const source = readFileSync(new URL(`../src/views/academic/Student${name}View.vue`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  let script = compileScript(descriptor, { id: `test-${name}` }).content
  const disposers = []
  const navigations = []
  const session = browser.session || { user: { userId: 'test-student', studentNo: 'S001' }, token: 'test-token' }
  const modules = {
    vue: { ...vue, onMounted: () => {}, onBeforeUnmount: (fn) => disposers.push(fn) },
    'vue-router': { useRoute: () => ({ query, meta }), useRouter: () => ({ push: (to) => navigations.push(to) }) },
    '../../services/portalApi': { portalApi: api },
    '../../services/systemDialog': {
      systemConfirm: async (options) => browser.confirm ? browser.confirm(options) : true,
      systemAlert: async (options) => browser.alert ? browser.alert(options) : true,
      systemPrompt: async (options) => browser.prompt ? browser.prompt(options?.message, options?.defaultValue) : null
    },
    '../../services/printInApp': {
      createInAppPrintFrame: () => browser.open ? browser.open() : { document: {}, closed: false, close() {}, focus() {}, print() {} }
    },
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
  const component = new Function('modules', 'window', script)(modules, { confirm: () => true, ...browser })
  return { ...component.setup({}, { expose() {} }), dispose: () => disposers.forEach((fn) => fn()), navigations }
}
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const course = { selectionCourseId: 'C1', courseName: '测试课程', allowedActions: ['ENROLL'], mode: 'LOTTERY' }
const batch = (id) => [{ batch: { batchId: id, batchName: id }, courses: [course] }]
const forbidden = () => Object.assign(new Error('禁止访问'), { status: 403 })
const conflict = () => Object.assign(new Error('事实已变化'), { status: 409 })

for (const action of ['textbook', 'level-register', 'level-cancel', 'exam', 'recheck', 'evaluation']) {
  for (const invalidation of ['identity', 'unmount', 'cancel']) {
    test(`${action}: an in-app confirmation cannot write after ${invalidation}`, async () => {
      const confirmation = deferred()
      const session = { user: { userId: `dialog-${action}-${invalidation}` }, token: 'token-A' }
      let writes = 0, confirmations = 0
      const browser = { session, confirm: () => { confirmations++; return confirmation.promise } }
      const write = async () => { writes++; return {} }
      let page, invoke
      if (action === 'textbook') {
        page = mount('Textbook', { academicTextbookSign: write }, {}, {}, browser)
        invoke = () => page.sign({ recordId: '81', status: 'PENDING', textbookName: '教材' })
      } else if (action.startsWith('level')) {
        page = mount('LevelExam', { academicLevelRegister: write, academicLevelCancel: write }, {}, {}, browser)
        const exam = { examId: '82', status: 'OPEN' }
        if (action === 'level-cancel') exam.registration = { regId: '83', status: 'REGISTERED' }
        invoke = () => action === 'level-cancel' ? page.cancel(exam) : page.register(exam)
      } else if (action === 'exam') {
        page = mount('Exam', { academicExamDeferApply: write }, {}, {}, browser)
        const exam = { examCourseId: '84', courseName: '数学' }
        page.ensureDraft(exam)
        page.drafts[page.deferOptionKey(exam)].reason = '请核对本人的缓考申请'
        invoke = () => page.applyDefer(exam)
      } else if (action === 'recheck') {
        page = mount('Recheck', { academicGradeRecheckSubmit: write, academicGradeRecheck: async () => [], academicTranscript: async () => ({ items: [{ gradeId: '85', canRecheck: true }] }) }, {}, {}, browser)
        await page.load()
        page.selectedGradeId.value = '85'; page.reason.value = '请核对卷面分数'
        invoke = () => page.submit()
      } else {
        const task = { taskId: '86', canSubmit: true, submitted: false }
        page = mount('Evaluation', { academicEvaluationSubmit: write }, {}, {}, browser)
        page.ensureDraft(task); page.drafts['86'].score = 80
        invoke = () => page.submit(task)
      }
      const running = invoke()
      assert.equal(confirmations, 1, 'the action must actually reach confirmation')
      if (invalidation === 'identity') { session.user = { userId: 'new-user' }; session.token = 'token-B' }
      if (invalidation === 'unmount') page.dispose()
      confirmation.resolve(invalidation !== 'cancel')
      await running
      assert.equal(writes, 0)
      page.dispose()
    })
  }
}

test('registration treats an HTTP409 fact-baseline rejection as not accepted even with a generic 500001 envelope', async () => {
  let writes = 0
  const batch = { batchId: '40', batchName: '沙箱注册', canRegister: true, registrationStatus: 'PENDING_REGISTER' }
  const page = mount('Registration', {
    academicRegistrationRegister: async () => { writes++; throw Object.assign(new Error('学生当前学籍事实底座缺失'), { status: 409, code: 500001, bizCode: 'ACADEMIC_FACT_BASELINE_MISSING' }) },
    academicRegistration: async () => ({ batches: [batch] })
  })
  page.openRegisterConfirm(batch)
  await page.register(page.pendingRegistration.value)
  assert.equal(writes, 1)
  assert.equal(page.actionReceipt.value.result, '注册未完成')
  assert.match(page.actionReceipt.value.next, /事实底座缺失/)
  assert.equal(page.uncertainRegistrations.value['40'], undefined)
})

for (const formalId of ['901', '902']) {
  test(`registration freezes the confirmation batch and checks original registration ${formalId}`, async () => {
    let sent
    const original = { batchId: '101', batchName: '本学期注册', canRegister: true }
    const page = mount('Registration', {
      academicRegistrationRegister: async id => { sent = id; return { registrationId: '901', status: 'REGISTERED' } },
      academicRegistration: async () => ({ batches: [{ batchId: '101', registrationId: formalId, registrationStatus: 'REGISTERED' }] })
    })
    page.openRegisterConfirm(original)
    const confirmed = page.pendingRegistration.value
    original.batchId = '102'
    await page.register(confirmed)
    assert.equal(sent, '101')
    assert.equal(page.actionReceipt.value.result, formalId === '901' ? '本学期注册已完成' : '注册结果待确认')
    assert.equal(!!page.uncertainRegistrations.value['101'], formalId !== '901')
  })
}

test('registration confirmation or late POST from another identity cannot send or expose old receipts', async () => {
  const post = deferred()
  const session = { user: { userId: 'A' }, token: 'token-A' }
  let writes = 0, reads = 0
  const page = mount('Registration', {
    academicRegistrationRegister: () => { writes++; return post.promise },
    academicRegistration: async () => { reads++; return { batches: [] } }
  }, {}, {}, { session })
  const batch = { batchId: '101', canRegister: true }
  page.openRegisterConfirm(batch)
  session.user = { userId: 'B' }; session.token = 'token-B'
  await page.register(page.pendingRegistration.value)
  assert.equal(writes, 0)
  page.openRegisterConfirm(batch)
  const running = page.register(page.pendingRegistration.value)
  session.user = { userId: 'C' }; session.token = 'token-C'
  page.actionReceipt.value = { sentinel: 'C' }
  post.resolve({ registrationId: '901' }); await running
  assert.equal(reads, 0)
  assert.deepEqual(page.actionReceipt.value, { sentinel: 'C' })
})

test('recheck 5xx with a conflict-shaped envelope remains uncertain and blocks a repeated write', async () => {
  let writes = 0
  const page = mount('Recheck', {
    academicTranscript: async () => ({ items: [{ gradeId: '101', courseName: '数学' }] }),
    academicGradeRecheck: async () => [],
    academicGradeRecheckSubmit: async () => { writes++; throw Object.assign(new Error('internal server error'), { status: 500, bizCode: '409001' }) }
  })
  await page.load(); page.selectedGradeId.value = '101'; page.reason.value = '核对正式成绩'
  await page.submit(); await page.submit()
  assert.equal(writes, 1)
  assert.equal(page.uncertainGradeId.value, '101')
  assert.equal(page.receiptTone.value, 'waiting')
})

test('recognition main load cannot overwrite a newer candidate search', async () => {
  const oldCourses = deferred()
  let calls = 0
  const page = mount('Recognition', {
    academicRecognition: async () => [],
    academicRecognitionCourses: () => ++calls === 1 ? oldCourses.promise : Promise.resolve({ items: [{ courseId: '202', courseName: '最新课程' }], total: 1 })
  })
  const loading = page.load()
  page.courseKeyword.value = '最新'; await page.loadCourses(1)
  oldCourses.resolve({ items: [{ courseId: '101', courseName: '旧课程' }], total: 1 }); await loading
  assert.equal(page.courses.value[0].courseId, '202')
  assert.equal(page.loading.value, false)
})

test('major split reread preserves the active volunteer draft', async () => {
  const page = mount('MajorSplit', { academicMajorSplit: async () => ({ openBatches: [{ batchId: '101', options: [] }], myVolunteers: [] }) })
  page.picks.value = { '101': ['201', '202'] }
  await page.load()
  assert.deepEqual(page.picks.value['101'], ['201', '202'])
})

test('recheck keeps bigint grade identity and rejects ACK for another original grade', async () => {
  const id = '1000000000000063602'; let sent
  const page = mount('Recheck', {
    academicTranscript: async () => ({ items: [{ gradeId: id, courseName: '数学' }] }),
    academicGradeRecheck: async () => [{ recheckId: '901', acadGradeId: '999', status: 'UPHELD' }],
    academicGradeRecheckSubmit: async body => { sent = body; return { recheckId: '901' } }
  })
  await page.load(); page.selectedGradeId.value = id; page.reason.value = '申请核对实际成绩'
  await page.submit()
  assert.equal(sent.acadGradeId, id); assert.equal(typeof sent.acadGradeId, 'string')
  assert.equal(page.receiptTone.value, 'waiting'); assert.equal(page.reason.value, '申请核对实际成绩')
})

test('manual recheck refresh clears the old submit receipt and exposes the latest formal status', async () => {
  let status = 'SUBMITTED'
  const page = mount('Recheck', {
    academicTranscript: async () => ({ items: [{ gradeId: '101', courseName: '数学' }] }),
    academicGradeRecheck: async () => [{ recheckId: '901', acadGradeId: '101', status, reviewNote: status === 'UPHELD' ? '已核对并维持原成绩' : '' }]
  })
  await page.load()
  page.receipt.value = { title: '成绩复查申请已提交并核对', status: '复查中' }
  status = 'UPHELD'
  await page.load()
  assert.equal(page.receipt.value, null)
  assert.equal(page.records.value[0].status, 'UPHELD')
  assert.equal(page.statusText('UPHELD'), '维持原成绩')
})

test('post-write recheck GET403 cannot rebuild a receipt containing the old course', async () => {
  let wrote = false
  const page = mount('Recheck', {
    academicTranscript: async () => ({ items: [{ gradeId: '101', courseName: 'private-course' }] }),
    academicGradeRecheck: async () => { if (wrote) throw forbidden(); return [] },
    academicGradeRecheckSubmit: async () => { wrote = true; return { recheckId: '901' } }
  })
  await page.load(); page.selectedGradeId.value = '101'; page.reason.value = '申请核对实际成绩'
  await page.submit()
  assert.equal(page.receipt.value, null); assert.deepEqual(page.grades.value, []); assert.equal(page.reason.value, '')
})

test('post-write evaluation GET403 leaves all old task data and receipt cleared', async () => {
  const current = { taskId: '201', courseName: 'private-course', canSubmit: true, submitted: false }
  const page = mount('Evaluation', {
    academicEvaluationTasks: async () => { throw forbidden() },
    academicEvaluationSubmit: async () => ({ taskId: '201' })
  })
  page.ensureDraft(current); page.drafts['201'].score = 80
  await page.submit(current)
  assert.equal(page.receipt.value, null); assert.deepEqual(page.tasks.value, [])
})

test('truthy nonboolean DROP eligibility never sends a write', async () => {
  let writes = 0
  const page = mount('Selection', {
    academicSelectionDropPreflight: async () => ({ allowed: 'false', action: 'DROP', selectionCourseId: 'C1' }),
    academicDrop: async () => { writes++ }
  })
  await page.drop({ ...course, allowedActions: ['DROP'] })
  assert.equal(writes, 0); assert.ok(page.decisionError.value)
})

test('level registration and cancellation both read formal records after the command', async () => {
  const calls = []
  let state = ''
  const exam = { examId: '12', examName: '普通话', status: 'OPEN' }
  const page = mount('LevelExam', {
    academicLevelExam: async () => { calls.push('GET'); return { openExams: [exam], myRegs: state ? [{ regId: '51', examId: '12', status: state, feeStatus: 'UNPAID' }] : [] } },
    academicLevelRegister: async () => { calls.push('REGISTER'); state = 'REGISTERED'; return { regId: '51', examId: '12', status: state } },
    academicLevelCancel: async () => { calls.push('CANCEL'); state = 'CANCELLED'; return { regId: '51', examId: '12', status: state } }
  })
  page.confirmed.value = true
  await page.register(exam)
  assert.deepEqual(calls, ['REGISTER', 'GET'])
  assert.equal(page.receiptTone.value, 'success')
  assert.equal(page.registeredCount.value, 1)
  assert.equal(page.confirmed.value, false)
  await page.cancel(page.exams.value[0])
  assert.deepEqual(calls, ['REGISTER', 'GET', 'CANCEL', 'GET'])
  assert.equal(page.receipt.value.status, '已取消')
  assert.equal(page.registeredCount.value, 0)
})

test('level result shows actual fee, score and certificate and unknown windows cannot invite registration', () => {
  const page = mount('LevelExam')
  const exam = { registration: { feeStatus: 'PAID', score: 0, result: 'FAIL', certNo: 'CERT-1' } }
  assert.match(page.personalResult(exam), /已缴费.*不合格.*成绩 0.*CERT-1/)
  assert.equal(page.canRegister({ examId: '1' }), false)
})

test('successful writes with unchanged formal records never claim level or textbook completion', async () => {
  const exam = { examId: '1', status: 'OPEN' }
  const level = mount('LevelExam', { academicLevelRegister: async () => ({ status: 'REGISTERED' }), academicLevelExam: async () => ({ openExams: [exam], myRegs: [] }) })
  await level.register(exam)
  assert.equal(level.receiptTone.value, 'waiting')
  const book = { recordId: '1', textbookName: '教材', status: 'PENDING' }
  const textbook = mount('Textbook', { academicTextbookSign: async () => ({ status: 'RECEIVED' }), academicTextbook: async () => ({ distributions: [book] }) })
  await textbook.sign(book)
  assert.equal(textbook.receiptTone.value, 'waiting')
  assert.match(textbook.receipt.value.title, /待确认/)
})

test('recheck and evaluation receipts wait until their own formal records are read back', async () => {
  const grade = { gradeId: '101', courseName: '高等数学', canRecheck: true }
  const recheck = mount('Recheck', {
    academicGradeRecheck: async () => [],
    academicTranscript: async () => ({ items: [grade] }),
    academicGradeRecheckSubmit: async () => ({ recheckId: 'R1' })
  })
  await recheck.load()
  recheck.selectedGradeId.value = '101'; recheck.reason.value = '请核对卷面分数'
  await recheck.submit()
  assert.equal(recheck.receiptTone.value, 'waiting')
  assert.equal(recheck.reason.value, '请核对卷面分数')

  let submitted = false
  const task = { taskId: 'T1', courseName: '高等数学', canSubmit: true, submitted: false }
  const evaluation = mount('Evaluation', {
    academicEvaluationTasks: async () => ({ list: [{ ...task, submitted }] }),
    academicEvaluationSubmit: async () => { submitted = true; return { taskId: 'T1', status: 'SUBMITTED' } }
  })
  await evaluation.load()
  evaluation.activeTaskId.value = 'T1'; evaluation.ensureDraft(task); evaluation.drafts.T1.score = 80
  await evaluation.submit(task)
  assert.equal(evaluation.receiptTone.value, 'success')
  assert.equal(evaluation.activeTaskId.value, '')
})

test('recheck only attributes success to the returned recheckId, never an old matching reason', async () => {
  const grade = { gradeId: '101', courseName: '高等数学' }
  const oldRecord = { recheckId: 'OLD', acadGradeId: '101', reason: '请核对卷面分数', status: 'REJECTED' }
  const waiting = mount('Recheck', {
    academicGradeRecheck: async () => [oldRecord], academicTranscript: async () => ({ items: [grade] }), academicGradeRecheckSubmit: async () => ({})
  })
  await waiting.load(); waiting.selectedGradeId.value = '101'; waiting.reason.value = oldRecord.reason
  await waiting.submit()
  assert.equal(waiting.receiptTone.value, 'waiting')
  assert.equal(waiting.reason.value, oldRecord.reason)

  const formal = { ...oldRecord, recheckId: 'NEW', status: 'SUBMITTED' }
  const confirmed = mount('Recheck', {
    academicGradeRecheck: async () => [oldRecord, formal], academicTranscript: async () => ({ items: [grade] }), academicGradeRecheckSubmit: async () => ({ recheckId: 'NEW' })
  })
  await confirmed.load(); confirmed.selectedGradeId.value = '101'; confirmed.reason.value = oldRecord.reason
  await confirmed.submit()
  assert.equal(confirmed.receiptTone.value, 'success')
})

test('recheck formal GET failure keeps the command uncertain and never reuses the old matching row', async () => {
  const grade = { gradeId: '101', courseName: '高等数学' }
  const historical = { recheckId: 'ACK-1', acadGradeId: '101', status: 'REJECTED' }
  let reads = 0
  const page = mount('Recheck', {
    academicGradeRecheck: async () => {
      reads += 1
      if (reads === 1) return [historical]
      throw Object.assign(new Error('offline'), { network: true })
    },
    academicTranscript: async () => ({ items: [grade] }),
    academicGradeRecheckSubmit: async () => ({ recheckId: 'ACK-1' })
  })
  await page.load()
  page.selectedGradeId.value = '101'; page.reason.value = '请核对卷面分数'
  await page.submit()

  assert.equal(page.receiptTone.value, 'waiting')
  assert.equal(page.uncertainGradeId.value, '101')
  assert.equal(page.reason.value, '请核对卷面分数')
  assert.match(page.receipt.value.title, /待正式记录确认/)
})

test('late recheck GET and late 403 cannot overwrite the newly switched student page', async () => {
  const firstRecords = deferred()
  const firstGrades = deferred()
  let recordReads = 0
  let gradeReads = 0
  const session = { user: { userId: 'student-A', studentNo: 'A001' }, token: 'token-A' }
  const page = mount('Recheck', {
    academicGradeRecheck: async () => (++recordReads === 1 ? firstRecords.promise : [{ recheckId: 'B-1', acadGradeId: '202' }]),
    academicTranscript: async () => (++gradeReads === 1 ? firstGrades.promise : { items: [{ gradeId: '202', courseName: '学生B课程' }] })
  }, {}, {}, { session })

  const oldLoad = page.load()
  session.user = { userId: 'student-B', studentNo: 'B001' }; session.token = 'token-B'
  assert.equal(await page.load(), true)
  assert.equal(page.records.value[0].recheckId, 'B-1')

  firstRecords.reject(forbidden())
  firstGrades.resolve({ items: [{ gradeId: '101', courseName: '学生A课程' }] })
  assert.equal(await oldLoad, false)
  assert.equal(page.records.value[0].recheckId, 'B-1')
  assert.equal(page.error.value, '')
})

test('recheck rejects an unsafe numeric grade id before it can become a POST payload', async () => {
  let posts = 0
  const page = mount('Recheck', {
    academicGradeRecheck: async () => [],
    academicTranscript: async () => ({ items: [{ gradeId: 9007199254740993, courseName: '损坏编号课程' }] }),
    academicGradeRecheckSubmit: async () => { posts += 1; return {} }
  })
  await page.load()
  page.selectedGradeId.value = String(9007199254740993); page.reason.value = '请核对卷面分数'
  await page.submit()
  assert.equal(posts, 0)
  assert.deepEqual(page.grades.value, [])
})

test('registration deferral only attributes success to the returned deferralId', async () => {
  const batch = { batchId: 'B1', batchName: '秋季注册', canDefer: true }
  const oldDeferral = { deferralId: 'OLD', status: 'REJECTED', reason: '需要延后办理注册' }
  const waiting = mount('Registration', {
    academicRegistration: async () => ({ batches: [{ ...batch, deferral: oldDeferral }] }), academicRegistrationDefer: async () => ({})
  })
  await waiting.load(); waiting.deferReasons.B1 = oldDeferral.reason
  await waiting.submitDefer(batch)
  assert.match(waiting.actionReceipt.value.result, /待确认/)
  assert.equal(waiting.deferReasons.B1, oldDeferral.reason)

  const currentDeferral = { ...oldDeferral, deferralId: 'NEW', status: 'PENDING' }
  const confirmed = mount('Registration', {
    academicRegistration: async () => ({ batches: [{ ...batch, deferral: currentDeferral }] }), academicRegistrationDefer: async () => ({ deferralId: 'NEW' })
  })
  await confirmed.load(); confirmed.deferReasons.B1 = oldDeferral.reason
  await confirmed.submitDefer(batch)
  assert.match(confirmed.actionReceipt.value.result, /审核中/)
  assert.equal(confirmed.deferReasons.B1, '')
})

test('major split only attributes success to the returned volunteerId, not an old equal choice list', async () => {
  const batch = { batchId: 'B1', batchName: '专业分流', maxChoices: 2, options: [{ majorId: 'A' }, { majorId: 'B' }] }
  const oldVolunteer = { volunteerId: 'OLD', batchId: 'B1', choices: ['A', 'B'], status: 'PENDING' }
  const waiting = mount('MajorSplit', {
    academicMajorSplit: async () => ({ openBatches: [batch], myVolunteers: [oldVolunteer] }), academicMajorSplitSubmit: async () => ({ volunteerId: 'WRONG' })
  })
  await waiting.load(); await waiting.submit(batch)
  assert.equal(waiting.receiptTone.value, 'waiting')
  assert.deepEqual(waiting.choicesFor(batch), ['A', 'B'])

  const newVolunteer = { ...oldVolunteer, volunteerId: 'NEW' }
  const confirmed = mount('MajorSplit', {
    academicMajorSplit: async () => ({ openBatches: [batch], myVolunteers: [oldVolunteer, newVolunteer] }), academicMajorSplitSubmit: async () => ({ volunteerId: 'NEW' })
  })
  await confirmed.load(); await confirmed.submit(batch)
  assert.equal(confirmed.receiptTone.value, 'success')
})

test('evaluation only attributes a submitted task to an exact taskId acknowledgement', async () => {
  const submittedTask = { taskId: 'T1', courseName: '高等数学', canSubmit: false, submitted: true }
  const staleDraftTask = { ...submittedTask, canSubmit: true, submitted: false }
  const waiting = mount('Evaluation', {
    academicEvaluationTasks: async () => ({ list: [submittedTask] }), academicEvaluationSubmit: async () => ({})
  })
  waiting.ensureDraft(staleDraftTask); waiting.drafts.T1.score = 80; waiting.activeTaskId.value = 'T1'
  await waiting.submit(staleDraftTask)
  assert.equal(waiting.receiptTone.value, 'waiting')
  assert.equal(waiting.activeTaskId.value, 'T1')

  const confirmed = mount('Evaluation', {
    academicEvaluationTasks: async () => ({ list: [submittedTask] }), academicEvaluationSubmit: async () => ({ taskId: 'T1', submitted: true })
  })
  confirmed.ensureDraft(staleDraftTask); confirmed.drafts.T1.score = 80; confirmed.activeTaskId.value = 'T1'
  await confirmed.submit(staleDraftTask)
  assert.equal(confirmed.receiptTone.value, 'success')
  assert.equal(confirmed.activeTaskId.value, '')
})

test('status fills its identity card from the existing safe enrollment projection', async () => {
  const page = mount('Status', {
    academicStatus: async () => ({ studentStatus: 'REGISTERED', changes: [] }), academicTransferOptions: async () => ({}),
    profileEnrollment: async () => ({ name: '学生甲', studentNo: '001', collegeName: '智能制造', majorName: '机电', className: '机电一班', grade: '2024', idCardMasked: 'SHOULD_NOT_COPY' })
  })
  await page.load()
  assert.equal(page.status.value.realName, '学生甲')
  assert.equal(page.status.value.className, '机电一班')
  assert.equal(page.status.value.idCardMasked, undefined)
})

test('a denied safe profile clears all previous academic identity and application data', async () => {
  const page = mount('Status', { academicStatus: async () => ({ studentStatus: 'REGISTERED', changes: [{ changeId: '1' }] }), academicTransferOptions: async () => ({}), profileEnrollment: async () => { throw forbidden() } })
  page.status.value = { realName: 'old identity' }
  await page.load()
  assert.deepEqual(page.status.value, {})
  assert.deepEqual(page.records.value, [])
})

test('clearance conceals scored drafts and accepts a published zero without changing it', () => {
  const page = mount('AcademicReadOnly', {}, {}, { academicReadModel: 'clearance' })
  assert.equal(page.clearanceResult({ status: 'SCORED', score: 88 }), '结果尚未正式发布')
  assert.equal(page.clearanceResult({ status: 'FINISHED', score: 0 }), 0)
  assert.equal(page.clearanceResult({ status: 'FINISHED', score: null }), '正式结果待核对')
})

test('major history resolves names by formal identity and never renders a raw id as a major', () => {
  const page = mount('MajorSplit')
  page.data.value = { openBatches: [{ batchId: '1', options: [{ majorId: '23', majorName: '机电' }] }] }
  assert.equal(page.volunteerText({ batchId: '1', choices: ['23', '999'] }), '第1志愿：机电 / 第2志愿：专业名称待学校提供')
  assert.equal(page.allocationText({ batchId: '1', resultMajorId: '23' }), '机电')
  assert.equal(page.volunteerStatus({ status: 'CONFIRMED' }), '分流已正式生效')
})

test('DROP preflight network failure cannot create a pending submitted operation', async () => {
  let writes = 0, reads = 0
  const page = mount('Selection', { academicSelectionDropPreflight: async () => { throw new TypeError('Failed to fetch') }, academicDrop: async () => { writes++ }, academicSelectionRecords: async () => { reads++; return [] } })
  await page.drop({ ...course, allowedActions: ['DROP'] })
  assert.equal(writes, 0)
  assert.equal(reads, 0)
  assert.equal(page.pendingOperation.value, null)
  assert.match(page.decisionError.value.message, /网络/)
})

test('receipts never substitute browser clock time for an absent business timestamp', () => {
  assert.equal(uiHelpers.academicReceipt({ title: '已提交' }).operatedAt, '学校未提供办理时间')
  assert.equal(uiHelpers.academicReceipt({ operatedAt: '2026-09-08T01:02:03Z' }).operatedAt, '2026-09-08T01:02:03Z')
})

function printBrowser() {
  const doc = { createElement: (tag) => ({ tag, ownerDocument: doc, children: [], textContent: '', appendChild(node) { this.children.push(node) } }) }
  doc.head = doc.createElement('head'); doc.body = doc.createElement('body')
  const win = { document: doc, printed: false, closed: false, focus() {}, print() { this.printed = true }, close() { this.closed = true } }
  const text = node => [node.textContent, ...node.children.map(text)].join(' ')
  return { win, browser: { prompt: () => '复审正式查询件', open: () => win }, text: () => text(doc.body) }
}

test('transcript printing uses the audited document, never the previous page rows', async () => {
  const output = printBrowser()
  const page = mount('Grades', { academicTranscriptPrint: async () => ({ document: { items: [{ courseName: '新正式成绩', score: 88, passStatus: 'PASSED' }], earnedCredits: 3 } }) }, {}, {}, output.browser)
  page.loading.value = false; page.transcript.value = { items: [{ courseName: '旧缓存成绩', score: 40 }] }
  await page.printQueryCopy()
  assert.equal(output.win.printed, true)
  assert.match(output.text(), /新正式成绩/)
  assert.doesNotMatch(output.text(), /旧缓存成绩/)
})

test('schedule printing reads the newly published document including its time bands', async () => {
  const output = printBrowser()
  const page = mount('Schedule', { academicSchedulePrint: async () => ({ document: { items: [{ courseName: '新课表课程', weekday: 1, slotNo: 1, startWeek: 1, endWeek: 18 }], timeBands: [{ slotNo: 1, startTime: '09:00', endTime: '09:45' }] } }) }, {}, {}, output.browser)
  page.loading.value = false; page.schedule.value = { items: [{ courseName: '旧课表缓存', weekday: 1, slotNo: 1 }] }
  await page.printSchedule()
  assert.equal(output.win.printed, true)
  assert.match(output.text(), /新课表课程/)
  assert.match(output.text(), /09:00/)
  assert.doesNotMatch(output.text(), /旧课表缓存/)
})

test('print endpoints without a formal document cannot fall back to cached private rows', async () => {
  for (const [name, apiName, method] of [['Grades','academicTranscriptPrint','printQueryCopy'], ['Schedule','academicSchedulePrint','printSchedule']]) {
    const output = printBrowser(), page = mount(name, { [apiName]: async () => ({ loggedAt: 'now' }) }, {}, {}, output.browser)
    page.loading.value = false
    if (name === 'Grades') page.transcript.value = { items: [{ courseName: '旧成绩' }] }
    else page.schedule.value = { items: [{ courseName: '旧课表' }] }
    await page[method]()
    assert.equal(output.win.printed, false)
    assert.equal(output.win.closed, true)
  }
})

test('registration progress never marks an absent or pending eligibility check as complete', () => {
  const page = mount('Registration')
  assert.equal(page.registrationStep.value, 0)
  page.data.value = { batches: [{ eligibilityStatus: 'PENDING', canRegister: true }] }
  assert.equal(page.registrationStep.value, 1)
  page.data.value = { batches: [{ eligibilityStatus: 'ELIGIBLE' }] }
  assert.equal(page.registrationStep.value, 2)
  page.data.value = { batches: [{ registrationStatus: 'REGISTERED' }] }
  assert.equal(page.registrationStep.value, 3)
})

test('makeup uses stable grade/course identities and displays both formal record lists', async () => {
  const submitted = []
  const page = mount('Makeup', {
    academicMakeup: async () => ({ retakes: [{ retakeId: '1' }], exemptions: [{ exemptionId: '2' }] }),
    academicMakeupOptions: async () => ({ retakeOptions: [], exemptionOptions: [] }),
    academicRetakeApply: async (body) => { submitted.push(body); return { status: 'PENDING' } },
    academicExemptionApply: async (body) => { submitted.push(body); return { status: 'PENDING' } }
  })
  const option = { gradeId: '101', courseId: '21', courseName: '数学', termCode: '旧学期' }
  page.retakeReasons['101'] = '重修说明'
  await page.applyRetake(option)
  page.exemptionReasons['21'] = '免修理由'
  await page.applyExemption(option)
  assert.deepEqual(submitted, [{ gradeId: '101', reason: '重修说明' }, { courseId: '21', courseName: '数学', reason: '免修理由' }])
  assert.equal(page.overviewRows.value.length, 2)
  assert.equal(page.canApplyExemption({ courseName: '只有名称' }), false)
  page.retakeReasons['101'] = '重修说明'
  assert.equal(page.canApplyRetake({ ...option, identityDebt: true }), false)
})

test('status reads changes and submits a server-listed toMajorId only', async () => {
  let body
  const page = mount('Status', {
    academicStatus: async () => ({ studentStatus: 'NORMAL', changes: [{ changeId: '1', status: 'APPROVED' }] }),
    academicTransferOptions: async () => ({ majors: [{ majorId: '22', majorName: '软件' }] }),
    academicStatusChange: async (value) => { body = value; return { status: 'PENDING' } }
  })
  await page.load()
  assert.equal(page.records.value.length, 1)
  Object.assign(page.form, { changeType: 'TRANSFER_MAJOR', reason: '希望申请转专业', targetMajorId: '99' })
  assert.equal(page.canSubmit.value, false)
  page.form.targetMajorId = '22'; await page.submit()
  assert.deepEqual(body, { changeType: 'TRANSFER_MAJOR', reason: '希望申请转专业', toMajorId: '22' })
})

test('level exams join personal registrations, retain closed history and honor regEnd', async () => {
  const page = mount('LevelExam', { academicLevelExam: async () => ({
    openExams: [{ examId: '1', status: 'OPEN', regEnd: '2000-01-01' }],
    myRegs: [{ examId: '1', status: 'REGISTERED' }, { examId: '2', status: 'REGISTERED' }]
  }) })
  await page.load()
  assert.equal(page.exams.value.length, 2)
  assert.equal(page.registeredCount.value, 2)
  assert.equal(page.canCancel(page.exams.value[0]), false)
  assert.equal(page.canCancel(page.exams.value[1]), false)
  assert.equal(page.feeText(null), '以学校通知为准')
})

test('credits consume passedCourses and leave unknown requirements unresolved', async () => {
  const page = mount('AcademicReadOnly', { academicCredits: async () => ({ resolutionStatus: 'UNRESOLVED', earnedCredits: 4, requiredCredits: null, passedCourses: [{ courseName: '数学', passStatus: 'PASSED' }] }) }, {}, { academicReadModel: 'credits' })
  await page.load()
  assert.equal(page.rows.value.length, 1)
  assert.equal(page.creditProgress.value, null)
  assert.equal(page.statusText(page.rows.value[0]), '已通过')
  page.data.value = { resolutionStatus: 'RESOLVED', earnedCredits: 4, requiredCredits: 20 }
  assert.equal(page.creditProgress.value, 20)
})

test('textbook fees come from server ledger, and missing amounts remain unknown', async () => {
  const page = mount('Textbook', { academicTextbook: async () => ({ distributions: [{ recordId: '1', qty: 2, status: 'RECEIVED', receivedAt: '2026-09-08' }], fees: { totalDue: 98, totalPaid: 40, unpaid: 58 } }) })
  await page.load()
  assert.equal(page.fees.value.unpaid, 58)
  assert.equal(page.amountText(null), '待确认')
  assert.equal(page.canSign(page.records.value[0]), false)
})

test('recognition submits only a server-listed course identity and keeps its display name', async () => {
  let body
  const page = mount('Recognition', {
    academicRecognition: async () => [],
    academicRecognitionCourses: async () => ({ items: [{ courseId: 'C1', courseCode: 'MATH01', courseName: '高等数学', version: 3 }], total: 1 }),
    academicRecognitionSubmit: async (value) => { body = value; return { status: 'SUBMITTED' } }
  })
  await page.loadCourses(1)
  page.form.targetCourseId = 'C1'; page.onCoursePicked()
  Object.assign(page.form, { sourceCourseName: '校外数学', sourceScore: 80, reason: '申请认定为校内高等数学课程' })
  await page.submit()
  assert.equal(body.targetCourseId, 'C1')
  assert.equal(body.targetCourseName, '高等数学')
})

test('recognition returns to the formal record after exact readback, never from the POST response alone', async () => {
  let published = false
  const page = mount('Recognition', {
    academicRecognition: async () => published ? [{ recognitionId: 'R1', targetCourseId: 'C1', targetCourseName: '高等数学', status: 'SUBMITTED' }] : [],
    academicRecognitionCourses: async () => ({ items: [{ courseId: 'C1', courseCode: 'MATH01', courseName: '高等数学', version: 3 }], total: 1 }),
    academicRecognitionSubmit: async () => { published = true; return { recognitionId: 'R1' } }
  })
  await page.loadCourses(1)
  page.applying.value = true; page.form.targetCourseId = 'C1'; page.onCoursePicked()
  Object.assign(page.form, { sourceCourseName: '校外数学', sourceScore: 80, reason: '申请认定为校内高等数学课程' })
  await page.submit()
  assert.equal(page.receiptTone.value, 'success')
  assert.equal(page.applying.value, false)
  assert.equal(page.records.value[0].recognitionId, 'R1')
})

test('selection ignores an older batch response even when it finishes last', async () => {
  const a = deferred(), b = deferred()
  const page = mount('Selection', { academicCourseSelection: (id) => id === 'A' ? a.promise : b.promise, academicSelectionRecords: async () => [] })
  page.activeBatchId.value = 'A'; const first = page.load('A')
  page.activeBatchId.value = 'B'; const second = page.load('B')
  b.resolve(batch('B')); await second
  a.resolve(batch('A')); await first
  assert.equal(page.groups.value[0].batch.batchId, 'B')
})

test('selection requires a fresh formal record, blocks repeat writes, and can reconcile by GET', async () => {
  let writes = 0, failRead = true
  const order = []
  const page = mount('Selection', {
    academicSelectionPreflight: async () => { order.push('preflight'); return { allowed: true } },
    academicEnroll: async () => { writes++; order.push('enroll'); return { recordId: 'R1', selectionCourseId: 'C1' } },
    academicSelectionRecords: async () => { order.push('records'); if (failRead) throw new TypeError('Failed to fetch'); return [{ ...course, recordId: 'R1', status: 'PENDING_LOTTERY' }] },
    academicCourseSelection: async () => batch('A')
  })
  page.records.value = [{ ...course, status: 'SELECTED' }]
  await page.enroll(course)
  assert.deepEqual(order, ['preflight', 'enroll', 'records'])
  assert.equal(page.receiptTone.value, 'waiting')
  assert.match(page.receipt.value.title, /结果待确认/)
  assert.equal(page.records.value.length, 0)
  await page.enroll(course); assert.equal(writes, 1)
  failRead = false; await page.confirmPending()
  assert.equal(writes, 1)
  assert.match(page.receipt.value.status, /已报名等待抽签/)
  assert.equal(page.pendingOperation.value, null)
})

test('enroll timeout reads the formal result once and never retries the POST', async () => {
  let writes = 0
  const page = mount('Selection', {
    academicSelectionPreflight: async () => ({ allowed: true }),
    academicEnroll: async () => { writes++; throw new TypeError('Failed to fetch') },
    academicSelectionRecords: async () => [{ ...course, status: 'SELECTED' }],
    academicCourseSelection: async () => batch('A')
  })
  await page.enroll(course)
  assert.equal(writes, 1)
  assert.equal(page.receipt.value.status, '已取得名额')
})

test('a drop still showing SELECTED remains pending rather than reporting success', async () => {
  const page = mount('Selection', { academicSelectionDropPreflight: async () => ({ allowed: true, action: 'DROP', selectionCourseId: 'C1' }), academicDrop: async () => {}, academicSelectionRecords: async () => [{ ...course, status: 'SELECTED' }] })
  await page.drop({ ...course, allowedActions: ['DROP'] })
  assert.match(page.receipt.value.title, /结果待确认/)
  assert.equal(page.receiptTone.value, 'waiting')
})

test('DROP preflight must attest to the exact current course, record, and batch before the write', async () => {
  let writes = 0
  const candidate = { ...course, recordId: 'R1', batchId: 'B1', allowedActions: ['DROP'] }
  const page = mount('Selection', { academicSelectionDropPreflight: async () => ({ allowed: true, action: 'DROP', selectionCourseId: 'C1', selectionRecordId: 'R1', batchId: 'B2' }), academicDrop: async () => writes++ })
  page.activeBatchId.value = 'B1'
  await page.drop(candidate)
  assert.equal(writes, 0)
  assert.match(page.decisionError.value.message, /对象不一致/)
})

test('a late DROP preflight cannot write after the student switches batches', async () => {
  let writes = 0
  const preflight = deferred()
  const page = mount('Selection', {
    academicSelectionDropPreflight: () => preflight.promise,
    academicDrop: async () => { writes++ },
    academicCourseSelection: async () => batch('B2'),
    academicSelectionRecords: async () => []
  })
  page.activeBatchId.value = 'B1'
  const command = page.drop({ ...course, batchId: 'B1', allowedActions: ['DROP'] })
  page.activeBatchId.value = 'B2'; page.changeBatch()
  preflight.resolve({ allowed: true, action: 'DROP', selectionCourseId: 'C1', batchId: 'B1' })
  await command
  assert.equal(writes, 0)
})

test('DROP conflict re-reads the formal record and explains the changed fact without a second write', async () => {
  let writes = 0
  const page = mount('Selection', {
    academicSelectionDropPreflight: async () => ({ allowed: true, action: 'DROP', selectionCourseId: 'C1' }),
    academicDrop: async () => { writes++; throw conflict() },
    academicSelectionRecords: async () => [{ ...course, status: 'SELECTED' }]
  })
  await page.drop({ ...course, allowedActions: ['DROP'] })
  assert.equal(writes, 1)
  assert.equal(page.receiptTone.value, 'waiting')
  assert.match(page.decisionError.value.message, /事实已变化/)
})

test('preflight rejection sends no enroll; unknown capacity stays unknown', async () => {
  let writes = 0
  const page = mount('Selection', { academicSelectionPreflight: async () => ({ allowed: false, message: '课程时间冲突' }), academicEnroll: async () => writes++ })
  await page.enroll(course)
  assert.equal(writes, 0)
  assert.match(page.decisionError.value.message, /冲突/)
  assert.equal(page.remain({ remain: null, capacity: 30 }), null)
})

test('drop cannot write without a DROP-specific preflight or when that preflight denies', async () => {
  let writes = 0
  const candidate = { ...course, allowedActions: ['DROP'] }
  const missing = mount('Selection', { academicDrop: async () => writes++ })
  await missing.drop(candidate)
  assert.equal(writes, 0)
  assert.match(missing.decisionError.value.message, /核验暂不可用/)
  const denied = mount('Selection', { academicSelectionDropPreflight: async () => ({ allowed: false, reason: '名单已锁定' }), academicDrop: async () => writes++ })
  await denied.drop(candidate)
  assert.equal(writes, 0)
  assert.match(denied.decisionError.value.message, /名单已锁定/)
})

test('calendar renders actual month dates and preserves server teaching-week labels', async () => {
  const page = mount('AcademicReadOnly', { academicCalendar: async () => ({ hasTerm: true, weeks: [{ weekNo: 2, startDate: '2026-09-07' }], events: [{ eventId: 'E1', startDate: '2026-09-12', endDate: '2026-09-12', remark: '注册截止' }] }) }, {}, { academicReadModel: 'calendar' })
  await page.load()
  page.calendarMonth.value = '2026-09'
  assert.equal(page.calendarCells.value.length, 35)
  assert.equal(page.calendarCells.value[0].day, null)
  assert.equal(page.calendarCells.value[1].day, 1)
  assert.equal(page.calendarCells.value.find(cell => cell.day === 7).week, 2)
  assert.equal(page.calendarCells.value.find(cell => cell.day === 12).events[0].eventId, 'E1')
  page.shiftMonth(1)
  assert.equal(page.calendarMonth.value, '2026-10')
  assert.equal(page.monthEvents.value.length, 0)
})

test('major choices retain rank and reject duplicates or non-candidate identities', async () => {
  const writes = []
  const b = { batchId: 'B1', maxChoices: 3, options: [{ majorId: 'A' }, { majorId: 'B' }, { majorId: 'C' }] }
  const page = mount('MajorSplit', { academicMajorSplit: async () => ({ openBatches: [b], myVolunteers: [] }), academicMajorSplitSubmit: async body => { writes.push(body); return { status: 'SUBMITTED' } } })
  await page.load()
  page.setChoice(b, 1, 'C'); page.setChoice(b, 2, 'A'); page.setChoice(b, 3, 'B')
  await page.submit(b)
  assert.deepEqual(writes[0].choices, ['C', 'A', 'B'])
  page.setChoice(b, 1, 'A'); page.setChoice(b, 2, 'A')
  await page.submit(b)
  page.setChoice(b, 2, 'OUTSIDE')
  await page.submit(b)
  assert.equal(writes.length, 1)
})

test('registration deferral sends the requested date and preserves the draft after 409', async () => {
  const writes = []
  const b = { batchId: 'B1', canDefer: true }
  const page = mount('Registration', { academicRegistration: async () => ({ batches: [b] }), academicRegistrationDefer: async (_, body) => { writes.push(body); throw conflict() } })
  await page.load()
  page.deferReasons.B1 = '需要延后办理注册'
  page.deferUntil.B1 = '2026-09-20'
  await page.submitDefer(b)
  assert.deepEqual(writes[0], { reason: '需要延后办理注册', requestedUntil: '2026-09-20' })
  assert.equal(page.deferReasons.B1, '需要延后办理注册')
  assert.equal(page.deferUntil.B1, '2026-09-20')
})

test('unmount while preflight is in flight stops the later write', async () => {
  let writes = 0; const response = deferred()
  const page = mount('Selection', { academicSelectionPreflight: () => response.promise, academicEnroll: async () => writes++ })
  const action = page.enroll(course); page.dispose(); response.resolve({ allowed: true }); await action
  assert.equal(writes, 0)
})

test('403 on selection command clears rows, receipts, and detail', async () => {
  const page = mount('Selection', { academicSelectionPreflight: async () => { throw forbidden() } })
  page.rawGroups.value = batch('A'); page.records.value = [course]; page.detailId.value = 'C1'; page.receipt.value = { object: '旧课程' }
  await page.enroll(course)
  assert.equal(page.records.value.length, 0); assert.equal(page.groups.value.length, 0)
  assert.equal(page.receipt.value, null); assert.equal(page.detailId.value, '')
})

test('evaluation requires an explicit score and preserves separate drafts on 409', async () => {
  const task = { taskId: 'T1', canSubmit: true, courseName: '测试课' }
  const page = mount('Evaluation', { academicEvaluationSubmit: async () => { throw conflict() }, academicEvaluationTasks: async () => ({ list: [task] }) })
  page.ensureDraft(task); assert.equal(page.canSubmit(task), false)
  page.drafts.T1.score = 0; assert.equal(page.canSubmit(task), true)
  page.drafts.T1.comment = '保留本任务意见'; page.ensureDraft({ taskId: 'T2' })
  await page.submit(task)
  assert.equal(page.error.value, '')
  assert.equal(page.drafts.T1.comment, '保留本任务意见'); assert.equal(page.drafts.T2.score, '')
})

test('403 after evaluation submit clears drafts and the previous receipt', async () => {
  const task = { taskId: 'T1', canSubmit: true }
  const page = mount('Evaluation', { academicEvaluationSubmit: async () => { throw forbidden() } })
  page.ensureDraft(task); page.drafts.T1.score = 80; page.worklist.value = { list: [task] }; page.receipt.value = { object: '旧任务' }
  await page.submit(task)
  assert.equal(page.worklist.value.list.length, 0); assert.deepEqual(Object.keys(page.drafts), []); assert.equal(page.receipt.value, null)
})

test('grades filters combine and special outcomes never become a numeric zero', () => {
  const page = mount('Grades')
  page.transcript.value = { items: [
    { courseName: '数学', courseCode: 'M1', term: '2026春', courseType: '必修', passStatus: 'PASSED' },
    { courseName: '英语', courseCode: 'E1', term: '2026秋', courseType: '选修', passStatus: 'DEFERRED', score: 0 }
  ] }
  page.termFilter.value = '2026秋'; page.search.value = 'E1'
  assert.equal(page.filteredRows.value.length, 1)
  assert.equal(page.scoreText(page.filteredRows.value[0]), '缓考')
  assert.equal(page.resultTone({ passStatus: 'UNKNOWN' }), 'default')
  page.typeFilter.value = '必修'; assert.equal(page.filteredRows.value.length, 0)
})

test('generic business codes never hide numeric 403 or 409 codes', () => {
  assert.equal(uiHelpers.academicErrorKind({ code: 403001, bizCode: 'ACADEMIC_SCOPE' }), 'forbidden')
  assert.equal(uiHelpers.academicErrorKind({ code: 409001, bizCode: 'ACADEMIC_STATE' }), 'conflict')
})

test('shared readonly academic component rejects late results from a previous route', async () => {
  const warning = deferred()
  const meta = vue.reactive({ academicReadModel: 'warning' })
  const page = mount('AcademicReadOnly', { academicWarning: () => warning.promise, academicCredits: async () => ({ items: [{ courseName: '新的学分事实' }] }) }, {}, meta)
  const oldRead = page.load()
  meta.academicReadModel = 'credits'; await vue.nextTick(); await page.load()
  warning.resolve({ items: [{ reason: '旧预警内容' }] }); await oldRead
  assert.equal(page.rows.value[0].courseName, '新的学分事实')
  page.dispose()
})

const homeApi = () => Object.fromEntries(['academicRegistration', 'academicEvaluationTasks', 'academicWarning', 'academicExamDefer', 'academicMakeupOptions', 'academicSchedule', 'academicSelectionRecords', 'academicTranscript', 'academicExam', 'academicStatus', 'academicTextbook', 'academicGraduationAudit'].map((name) => [name, async () => ({ items: [] })]))

test('home shows real today lessons and distinct lottery progress without claiming no work after network failure', async () => {
  const api = homeApi()
  api.academicSchedule = async () => ({ todayDate: '2026-09-08', todayItems: [{ courseName: '今日正式课' }] })
  api.academicSelectionRecords = async () => [{ status: 'PENDING_LOTTERY' }]
  api.academicWarning = async () => { throw new TypeError('Failed to fetch') }
  const page = mount('AcademicHome', api)
  await page.load()
  assert.equal(page.todayLessons.value[0].courseName, '今日正式课')
  assert.match(page.overview.value.find((item) => item.title === '选课进度').value, /等待抽签/)
  assert.match(page.headline.value, /读取失败/)
  assert.equal(page.overview.value.find((item) => item.title === '学业预警').value, '读取失败')
})

test('home permission revocation clears the previous dashboard', async () => {
  const api = homeApi(); const page = mount('AcademicHome', api)
  await page.load()
  page.todaySchedule.value = { todayItems: [{ courseName: '旧课程' }] }
  api.academicStatus = async () => { throw forbidden() }
  await page.load()
  assert.equal(page.todayLessons.value.length, 0); assert.equal(page.overview.value.length, 0)
  assert.match(page.accessError.value, /清除/)
})

for (const name of ['Evaluation', 'Exam', 'LevelExam', 'MajorSplit', 'Makeup', 'Recheck', 'Registration', 'Status', 'Textbook', 'Recognition']) {
  test(`${name}: denied reload clears the previous business receipt and prevents stale content`, async () => {
    const api = new Proxy({}, { get: () => async () => { throw forbidden() } })
    const page = mount(name, api)
    const receipt = page.receipt || page.actionReceipt
    receipt.value = { object: '旧的敏感业务对象' }
    await page.load()
    assert.equal(receipt.value, null)
    assert.match(page.error.value, /页面已清除/)
    assert.equal(page.loading.value, false)
  })
}
