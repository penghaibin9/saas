import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

const directory = new URL('../src/pages/student/academic-affairs/', import.meta.url)

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

function mount(name, studentApi) {
  const session = { generation: 1 }
  const routes = []
  const context = vm.createContext({
    studentApi,
    currentSessionGeneration: () => session.generation,
    go: route => routes.push(route),
    safeToast() {},
    getStatusBarHeight: () => 20,
    clampPercent: value => Math.max(0, Math.min(100, value)),
    academicIcons: {},
    AcademicPageNav: {}, AcademicPageState: {}, MobileAcademicDecisionCard: {}, MobileStatusTag: {}, MobileProgress: {}, MobileTabBar: {},
    uni: { setClipboardData() {} }
  })
  const helper = readFileSync(new URL('read-page.js', directory), 'utf8')
    .replace(/^import .*$/gm, '').replace(/export (const|function) /g, '$1 ')
  vm.runInContext(helper, context)
  const source = readFileSync(new URL(`${name}.vue`, directory), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(script, context)
  const definition = context.component
  const layers = []
  const collect = component => { for (const mixin of component.mixins || []) collect(mixin); layers.push(component) }
  collect(definition)
  const page = {}
  for (const layer of layers) Object.assign(page, layer.data?.call(page) || {})
  for (const layer of layers) for (const [key, fn] of Object.entries(layer.methods || {})) page[key] = fn.bind(page)
  for (const layer of layers) for (const [key, getter] of Object.entries(layer.computed || {})) Object.defineProperty(page, key, { get: () => getter.call(page) })
  const hook = hookName => layers.forEach(layer => layer[hookName]?.call(page))
  return { page, session, routes, definition, hook, source }
}

const emptyPriority = {
  getMyExamSchedule: async () => ({ items: [] }),
  getMyWarnings: async () => ({ items: [] }),
  getMyRegistration: async () => ({ batches: [] }),
  getSelectionBatches: async () => ({ items: [] })
}

test('read pages clear same-session private data on 403 and ignore a late result after unload', async () => {
  const transcript = mount('transcript', { getMyTranscript: async () => { throw { httpStatus: 403, code: '403001' } } })
  transcript.page.data = { items: [{ courseName: '旧成绩' }] }
  await transcript.page.load()
  assert.equal(transcript.page.state, 'forbidden')
  assert.equal(transcript.page.data, null)

  const late = deferred()
  const attendance = mount('attendance', { getMyAttendance: () => late.promise })
  const pending = attendance.page.load()
  attendance.hook('onUnload')
  late.resolve({ items: [{ courseName: '迟到的旧考勤' }], summary: {} })
  await pending
  assert.equal(attendance.page.d, null)
  assert.notEqual(attendance.page.state, 'ready')
})

test('home treats malformed successful reads as pending and carries exact lesson context into schedule', async () => {
  const home = mount('index', {
    getMyAcadStatus: async () => ({ studentStatus: 'NORMAL' }),
    getMySchedule: async () => ({ items: [], todayItems: null }),
    ...emptyPriority
  })
  await home.page.load()
  assert.equal(home.page.state, 'ready')
  assert.equal(home.page.scheduleLoaded, false)
  assert.ok(home.page.failedSources.includes('课表'))
  assert.equal(home.page.todayEmptyText, '今日课表暂时无法核对')
  home.page.currentWeek = 6
  home.page.goScheduleDetail({ itemId: 'lesson-001', weekday: 3 })
  assert.equal(home.routes.at(-1), '/pages/student/academic-affairs/schedule?id=lesson-001&day=3&week=6')

  const partial = mount('index', {
    getMyExamSchedule: async () => ({ items: null }),
    getMyWarnings: async () => ({ items: [] }),
    getMyRegistration: async () => ({ batches: [] }),
    getSelectionBatches: async () => ({ items: null })
  })
  await partial.page.loadPriority(0)
  assert.ok(partial.page.failedSources.includes('考试'))
  assert.ok(partial.page.failedSources.includes('网上选课'))
  assert.equal(partial.page.selectionSummary, '暂时无法核对')
})

test('schedule keeps a deep-linked lesson visible by selecting its valid week and day, and clears it on 403', async () => {
  let forbidden = false
  const scheduleCalls = []
  const schedule = mount('schedule', {
    getMySchedule: async params => {
      scheduleCalls.push(params)
      if (forbidden) throw { httpStatus: 403, code: '403001' }
      const requestedWeek = Number(params?.week)
      return {
        termCode: '2026-1', currentWeek: 6, teachingWeeks: 18,
        // The server owns recurrence filtering. A stale deep link to even week 4
        // is safely normalized to the first real occurrence in week 3.
        week: requestedWeek === 4 ? 3 : (requestedWeek || 3), todayItems: [],
        items: [{ itemId: 'lesson-001', courseName: '嵌入式系统', weekday: 3, slotNo: 2, startWeek: 3, endWeek: 5, weekParity: 'ODD' }]
      }
    }
  })
  schedule.definition.onLoad.call(schedule.page, { id: 'lesson-001', week: '4', day: '3' })
  await schedule.page.load()
  assert.equal(schedule.page.selectedWeek, 3)
  assert.equal(schedule.page.selectedDay, 3)
  assert.equal(schedule.page.filteredItems[0].itemId, 'lesson-001')
  assert.equal(scheduleCalls[0].week, 4)
  await schedule.page.onWeekChange({ detail: { value: 4 } })
  schedule.page.onDayChange({ detail: { value: 4 } })
  assert.equal(schedule.page.selectedWeek, 5)
  assert.equal(schedule.page.selectedDay, 4)
  forbidden = true
  await schedule.page.load()
  assert.equal(schedule.page.state, 'forbidden')
  assert.equal(schedule.page.items, null)

  const late = deferred()
  const unloading = mount('schedule', { getMySchedule: () => late.promise })
  const pending = unloading.page.load()
  unloading.hook('onUnload')
  late.resolve({ items: [], todayItems: [] })
  await pending
  assert.equal(unloading.page.items, null)
})

test('schedule never offers a wall-clock week beyond the configured teaching weeks', async () => {
  const schedule = mount('schedule', {
    getMySchedule: async () => ({
      termCode: '2026-1', currentWeek: 19, teachingWeeks: 18,
      week: 1, items: [], todayItems: [], calendarSource: 'OUT_OF_TERM'
    })
  })
  await schedule.page.load()
  assert.equal(schedule.page.maxWeek, 18)
  assert.equal(schedule.page.weekLabels.length, 18)
  assert.equal(schedule.page.weekLabels.at(-1), '第18周')
})

test('published grades and clearance preserve zero, and list coverage reports the server page', async () => {
  const transcript = mount('transcript', { getMyTranscript: async () => ({
    page: 1, pageSize: 20, total: 3, hasMore: false, term: null, terms: ['2026-1'],
    items: [{ gradeId: '0007', courseName: '数学', term: '2026-1', score: 0, credit: 2 }]
  }) })
  await transcript.page.load()
  assert.equal(transcript.page.scoreText(transcript.page.data.items[0]), 0)
  assert.match(transcript.page.gradeCoverageText, /本页 1 条，共 3 条/)
  assert.match(transcript.source, /encodeURIComponent\(g\.gradeId\)/)

  const clearance = mount('clearance', { getMyClearance: async () => ({ page: 1, pageSize: 20, total: 2, hasMore: false, items: [{ recordId: 'c-1', status: 'FINISHED', score: '0' }] }) })
  await clearance.page.load()
  assert.equal(clearance.page.hasPublishedScore(clearance.page.d.items[0]), true)
  assert.equal(clearance.page.publishedScore(clearance.page.d.items[0]), '0')
  assert.equal(clearance.page.hasPublishedScore({ status: 'FINISHED', score: false }), false)
  assert.equal(clearance.page.hasPublishedScore({ status: 'FINISHED', score: ' ' }), false)
  assert.match(clearance.page.clearanceCoverageText, /本页 1 条，共 2 条/)

  const warning = mount('warning', { getMyWarnings: async () => ({ total: 51, page: 1, pageSize: 20, hasMore: true, items: [{ warningId: 'w-1' }] }) })
  await warning.page.load()
  assert.match(warning.page.warningCoverageText, /本页 1 条，共 51 条/)
  assert.equal(warning.page.hasNext, true)
})

test('transcript and credits request bounded server pages instead of growing a local list', async () => {
  const transcriptCalls = []
  const transcript = mount('transcript', {
    getMyTranscript: async params => {
      transcriptCalls.push(params)
      const page = params.page
      return {
        page, pageSize: 20, total: 21, hasMore: page === 1, term: params.term || null,
        terms: ['2026-2', '2026-1'], items: [{ gradeId: `g-${page}`, courseName: '课程', term: '2026-2', credit: 2, passStatus: 'PASSED' }]
      }
    }
  })
  await transcript.page.load()
  assert.equal(transcriptCalls[0].pageSize, 20)
  assert.equal(transcript.page.hasNext, true)
  await transcript.page.nextPage()
  assert.equal(transcriptCalls[1].page, 2)
  assert.equal(transcript.page.data.items[0].gradeId, 'g-2')

  const creditCalls = []
  const credits = mount('credits', {
    getMyCredits: async params => {
      creditCalls.push(params)
      const page = params.page
      return {
        obtainedCredits: 42, requiredCredits: 80, gpa: 3.5, failCount: 0,
        page, pageSize: 20, passedCoursesTotal: 21, hasMore: page === 1,
        passedCourses: [{ gradeId: `c-${page}`, courseName: '已通过课程', credit: 2, passStatus: 'PASSED' }]
      }
    }
  })
  await credits.page.load()
  assert.equal(creditCalls[0].pageSize, 20)
  assert.equal(credits.page.hasNext, true)
  await credits.page.nextPage()
  assert.equal(creditCalls[1].page, 2)
  assert.equal(credits.page.d.passedCourses[0].gradeId, 'c-2')
})

test('calendar distinguishes malformed data from a valid partial calendar and validates attendance summary', async () => {
  const malformedCalendar = mount('calendar', { getMyCalendar: async () => ({ hasTerm: true, events: null, weeks: [] }) })
  await malformedCalendar.page.load()
  assert.equal(malformedCalendar.page.state, 'error')
  assert.equal(malformedCalendar.page.d, null)

  const partialCalendar = mount('calendar', { getMyCalendar: async () => ({ hasTerm: true, termLabel: '2026-1', events: [{ eventId: 'e-1', startDate: '2026-09-01', endDate: '2026-09-01' }], weeks: [], note: '教学周信息暂时无法提供' }) })
  await partialCalendar.page.load()
  assert.equal(partialCalendar.page.state, 'ready')
  assert.match(partialCalendar.page.calendarCoverageText, /1 条已发布校历事项和 0 个教学周/)

  const malformedAttendance = mount('attendance', { getMyAttendance: async () => ({ items: [], summary: [] }) })
  await malformedAttendance.page.load()
  assert.equal(malformedAttendance.page.state, 'error')
})

test('graduation projects all 11 student evidence items and excludes internal trace fields', async () => {
  const codes = ['STATUS', 'CREDIT', 'COURSE_REQUIRED', 'COURSE_ELECTIVE', 'PRACTICE', 'INTERNSHIP', 'GRADUATION_DESIGN', 'DISCIPLINE', 'EMPLOYMENT', 'ARCHIVE', 'FEE']
  let forbidden = false
  const graduation = mount('graduation', {
    getMyGraduation: async () => {
      if (forbidden) throw { httpStatus: 403, code: '403001' }
      return {
        hasAudit: false, overall: 'SYSTEM_PASSED',
        items: [...codes.map(item => ({ item, result: 'PASS', evidence: item === 'STATUS' ? 'student_status=NORMAL' : '学校已记录有效事实' })), { item: 'INTERNAL_ONLY', result: 'PASS', evidence: 'tenantId=1' }],
        decisionTrace: { raw: 'SELECT * FROM internal' },
        decisionText: { title: 'provider exception', reason: 'tenantId=1', nextStep: '关注学校通知' }
      }
    }
  })
  await graduation.page.load()
  assert.equal(graduation.page.items.length, 11)
  assert.equal(graduation.page.ITEM.FEE, '费用提醒')
  assert.equal(graduation.page.formalText, '尚未纳入正式预审')
  assert.doesNotMatch(JSON.stringify(graduation.page.data) + JSON.stringify(graduation.page.safeDecisionText) + graduation.page.studentEvidence(graduation.page.items[0]), /SELECT|tenantId|provider|student_status/i)
  forbidden = true
  await graduation.page.load()
  assert.equal(graduation.page.state, 'forbidden')
  assert.equal(graduation.page.data, null)
})
