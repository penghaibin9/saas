import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import * as uiHelpers from '../src/components/academic/studentAcademicUi.js'
import * as commandGuard from '../src/components/academic/studentAcademicCommandGuard.js'
import * as localization from '../src/services/visibleEnumLocalization.js'

function mount(name, api = {}, query = {}, meta = {}, browser = {}) {
  if (typeof api.profileEnrollment !== 'function') api.profileEnrollment = async () => ({})
  const source = readFileSync(new URL(`../src/views/academic/Student${name}View.vue`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  let script = compileScript(descriptor, { id: `r6-${name}` }).content
  const disposers = []
  const session = browser.session || { user: { userId: 'student-A', studentNo: 'A001' }, token: 'token-A' }
  const modules = {
    vue: { ...vue, onMounted: () => {}, onBeforeUnmount: (fn) => disposers.push(fn) },
    'vue-router': { useRoute: () => ({ query, meta }), useRouter: () => ({ push() {} }) },
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
  const component = new Function('modules', 'window', script)(modules, { confirm: () => true, ...browser })
  return { ...component.setup({}, { expose() {} }), dispose: () => disposers.forEach((fn) => fn()) }
}

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

const forbidden = () => Object.assign(new Error('禁止访问'), { status: 403 })
const conflict = () => Object.assign(new Error('事实已变化'), { status: 409 })
const homeApi = () => Object.fromEntries(['academicRegistration', 'academicEvaluationTasks', 'academicWarning', 'academicExamDefer', 'academicMakeupOptions', 'academicSchedule', 'academicSelectionRecords', 'academicTranscript', 'academicExam', 'academicStatus', 'academicTextbook', 'academicGraduationAudit'].map((name) => [name, async () => ({ items: [] })]))

test('status original ACK survives a failed read and later manual refresh resolves only that ID', async () => {
  let reads = 0, posts = 0
  const page = mount('Status', {
    academicStatus: async () => {
      reads += 1
      if (reads === 2) throw new TypeError('Failed to fetch')
      return { changes: reads >= 3 ? [{ changeId: '55', changeType: 'SUSPEND', status: 'SUBMITTED' }] : [] }
    },
    academicTransferOptions: async () => ({}),
    academicStatusChange: async () => { posts += 1; return { changeId: '55' } }
  })
  await page.load()
  Object.assign(page.form, { changeType: 'SUSPEND', reason: '本人申请办理休学' })
  await page.submit()
  assert.equal(page.pendingStatusReference.value.changeId, '55')
  assert.equal(page.receiptTone.value, 'waiting')
  await page.load()
  assert.equal(page.receiptTone.value, 'success')
  assert.equal(page.pendingStatusReference.value, null)
  assert.equal(page.uncertainCommandKey.value, '')
  assert.equal(posts, 1)
})

test('status 5xx with a 409 business code retains uncertainty and forbids repeated POST', async () => {
  let posts = 0
  const page = mount('Status', {
    academicStatus: async () => ({ changes: [] }), academicTransferOptions: async () => ({}),
    academicStatusChange: async () => { posts += 1; throw Object.assign(new Error('response unavailable'), { status: 503, code: 409 }) }
  })
  await page.load()
  Object.assign(page.form, { changeType: 'SUSPEND', reason: '本人申请办理休学' })
  await page.submit()
  await page.submit()
  assert.equal(posts, 1)
  assert.equal(page.pendingStatusReference.value.changeId, '')
  assert.equal(page.canSubmit.value, false)
  assert.match(page.receipt.value.title, /待确认/)
})

test('status late success preserves a draft edited while the original command was in flight', async () => {
  const ack = deferred()
  let reads = 0
  const page = mount('Status', {
    academicStatus: async () => ({ changes: ++reads === 1 ? [] : [{ changeId: '55', changeType: 'SUSPEND', status: 'SUBMITTED' }] }),
    academicTransferOptions: async () => ({}), academicStatusChange: async () => ack.promise
  })
  await page.load()
  Object.assign(page.form, { changeType: 'SUSPEND', reason: '本人申请办理休学' })
  const work = page.submit()
  page.form.reason = '提交期间重新填写的补充说明'
  ack.resolve({ changeId: '55' })
  await work
  assert.equal(page.receiptTone.value, 'success')
  assert.equal(page.form.reason, '提交期间重新填写的补充说明')
})

function printBrowser() {
  const doc = { createElement: (tag) => ({ tag, ownerDocument: doc, children: [], textContent: '', appendChild(node) { this.children.push(node) } }) }
  doc.head = doc.createElement('head'); doc.body = doc.createElement('body')
  const win = { document: doc, printed: false, closed: false, focus() {}, print() { this.printed = true }, close() { this.closed = true } }
  const text = (node) => [node.textContent, ...node.children.map(text)].join(' ')
  return { win, browser: { prompt: () => '复核正式查询件', open: () => win }, text: () => text(doc.body) }
}

test('home ignores a completed dashboard read after the student identity changed', async () => {
  const oldSchedule = deferred()
  const api = homeApi()
  let scheduleReads = 0
  api.academicSchedule = async () => ++scheduleReads === 1 ? oldSchedule.promise : { todayItems: [{ courseName: '学生B课程' }] }
  const session = { user: { userId: 'A', studentNo: 'A001' }, token: 'token-A' }
  const page = mount('AcademicHome', api, {}, {}, { session })
  const oldLoad = page.load()
  session.user = { userId: 'B', studentNo: 'B001' }; session.token = 'token-B'
  assert.equal(await page.load(), undefined)
  assert.equal(page.todayLessons.value[0].courseName, '学生B课程')
  oldSchedule.resolve({ todayItems: [{ courseName: '学生A课程' }] })
  await oldLoad
  assert.equal(page.todayLessons.value[0].courseName, '学生B课程')
})

test('warning page discloses the returned slice and keeps the server total', async () => {
  const page = mount('AcademicReadOnly', { academicWarning: async () => ({ items: [{ warningId: '1' }, { warningId: '2' }], total: 57 }) }, {}, { academicReadModel: 'warning' })
  await page.load()
  assert.equal(page.rows.value.length, 2)
  assert.equal(page.warningTotal.value, 57)
  assert.equal(page.warningIsPartial.value, true)
  assert.equal(page.metrics.value.find((item) => item.label === '预警记录').value, 57)
})

test('readonly failures remain errors and clearance only reveals finished scores', async () => {
  let fail = false
  const page = mount('AcademicReadOnly', { academicClearance: async () => {
    if (fail) throw new TypeError('Failed to fetch')
    return { items: [{ status: 'finished', score: 0 }] }
  } }, {}, { academicReadModel: 'clearance' })
  await page.load()
  assert.equal(page.clearanceResult(page.rows.value[0]), 0)
  assert.equal(page.clearanceResult({ status: 'SCORED', score: 99 }), '结果尚未正式发布')
  fail = true
  await page.load()
  assert.match(page.error.value, /网络|读取失败/)
  assert.equal(page.rows.value.length, 0)
})

test('schedule query resets exactly and printing never replaces the live schedule', async () => {
  const output = printBrowser()
  const query = vue.reactive({ lesson: 'lesson-1' })
  const page = mount('Schedule', { academicSchedulePrint: async () => ({ document: { teachingWeeks: 18, items: [{ itemId: 'new', courseName: '查询件课程', weekday: 1, slotNo: 1, startWeek: 1, endWeek: 18 }], timeBands: [{ slotNo: 1, startTime: '08:00', endTime: '08:45' }] } }) }, query, {}, output.browser)
  assert.equal(page.selectedLessonId.value, 'lesson-1')
  query.lesson = ''; await vue.nextTick()
  assert.equal(page.selectedLessonId.value, '')
  page.loading.value = false
  page.schedule.value = { items: [{ itemId: 'old', courseName: '页面正式课表', weekday: 1, slotNo: 1 }] }
  await page.printSchedule()
  assert.equal(output.win.printed, true)
  assert.match(output.text(), /查询件课程/)
  assert.equal(page.schedule.value.items[0].courseName, '页面正式课表')
})

test('grades reject an already rounded numeric id and ignore a late 403 from another student', async () => {
  const first = deferred()
  let reads = 0
  const session = { user: { userId: 'A', studentNo: 'A001' }, token: 'token-A' }
  const page = mount('Grades', { academicTranscript: async () => ++reads === 1 ? first.promise : { items: [{ gradeId: '22', courseName: '学生B成绩' }] } }, {}, {}, { session })
  assert.equal(page.safeGradeId({ gradeId: 9007199254740993 }), '')
  assert.equal(page.safeGradeId({ gradeId: '9007199254740993' }), '9007199254740993')
  const oldLoad = page.load()
  session.user = { userId: 'B', studentNo: 'B001' }; session.token = 'token-B'
  await page.load()
  first.reject(forbidden())
  await oldLoad
  assert.equal(page.rows.value[0].courseName, '学生B成绩')
  assert.equal(page.error.value, '')
})

test('graduation shows eleven business items without leaking technical evidence or inventing zero credits', async () => {
  const itemCodes = ['STATUS', 'CREDIT', 'COURSE_REQUIRED', 'COURSE_ELECTIVE', 'PRACTICE', 'INTERNSHIP', 'GRADUATION_DESIGN', 'DISCIPLINE', 'EMPLOYMENT', 'ARCHIVE', 'FEE']
  const page = mount('GraduationAudit', { academicGraduationAudit: async () => ({
    progress: { items: itemCodes.map((item) => ({ item, result: 'UNKNOWN', evidence: item === 'ARCHIVE' ? '学工归档包处理中 status=PENDING_SUPPLEMENT' : item === 'FEE' ? '教材费台账有未结清 2 笔约 73.00 元（refId=8）' : item === 'STATUS' ? 'student_status=NORMAL' : item === 'CREDIT' ? 'OperationalError refId=7' : '业务事实待核验' })), decisionText: { title: '毕业资格存在待处理项', reason: '总学分尚未达到要求', nextStep: '核对缺失学分', ruleCode: 'TOTAL_CREDITS_INSUFFICIENT' } },
    credits: { obtainedCredits: null, requiredCredits: 120 }, warnings: { items: [], total: 51 }
  }) })
  await page.load()
  assert.equal(page.progressItems.value.length, 11)
  assert.equal(page.obtainedCredits.value, null)
  assert.equal(page.obtainedCreditsText.value, '待核验')
  assert.equal(page.creditPct.value, null)
  assert.equal(page.warningCount.value, 51)
  assert.match(page.safeDecisionText.value, /总学分尚未达到要求.*核对缺失学分/)
  assert.doesNotMatch(page.safeDecisionText.value, /TOTAL_CREDITS/)
  const texts = page.progressItems.value.map(page.itemEvidenceText).join(' ')
  assert.doesNotMatch(texts, /refId|OperationalError|status=PENDING/)
  assert.match(texts, /73\.00 元|费用结清/)
})

test('status network uncertainty never turns an old similar record into success', async () => {
  const historical = { changeId: '9', changeType: 'SUSPEND', status: 'REJECTED' }
  const page = mount('Status', {
    academicStatus: async () => ({ studentStatus: 'NORMAL', changes: [historical] }),
    academicTransferOptions: async () => ({}),
    academicStatusChange: async () => { throw new TypeError('Failed to fetch') }
  })
  await page.load()
  Object.assign(page.form, { changeType: 'SUSPEND', reason: '本人申请办理休学' })
  await page.submit()
  assert.equal(page.receiptTone.value, 'waiting')
  assert.match(page.receipt.value.title, /待确认/)
  assert.equal(page.form.reason, '本人申请办理休学')
  assert.equal(page.uncertainCommandKey.value, 'SUSPEND::')
  assert.equal(page.canSubmit.value, false)
})

test('status success requires the exact acknowledged change id and 409 preserves input', async () => {
  let reads = 0
  const page = mount('Status', {
    academicStatus: async () => ++reads === 1 ? ({ studentStatus: 'NORMAL', changes: [] }) : ({ studentStatus: 'NORMAL', changes: [{ changeId: '22', changeType: 'PRESERVE', status: 'SUBMITTED' }] }),
    academicTransferOptions: async () => ({}),
    academicStatusChange: async () => ({ changeId: '22' })
  })
  await page.load()
  Object.assign(page.form, { changeType: 'PRESERVE', reason: '本人申请保留学籍' })
  await page.submit()
  assert.equal(page.receiptTone.value, 'success')
  assert.equal(page.form.reason, '')

  const conflictPage = mount('Status', {
    academicStatus: async () => ({ studentStatus: 'NORMAL', changes: [] }),
    academicTransferOptions: async () => ({}),
    academicStatusChange: async () => { throw conflict() }
  })
  await conflictPage.load()
  Object.assign(conflictPage.form, { changeType: 'RETAIN', reason: '本人申请办理留级' })
  await conflictPage.submit()
  assert.equal(conflictPage.form.reason, '本人申请办理留级')
  assert.match(conflictPage.receipt.value.title, /事实已变化/)
})
