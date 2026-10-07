import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import { setImmediate } from 'node:timers/promises'
import * as uiHelpers from '../src/components/academic/studentAcademicUi.js'
import * as commandGuard from '../src/components/academic/studentAcademicCommandGuard.js'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function mount(api, query = {}, session = { user: { userId: 'A', studentNo: 'S001' }, token: 'A' }, printFrame) {
  session = vue.reactive(session)
  const source = readFileSync(new URL('../src/views/academic/StudentScheduleView.vue', import.meta.url), 'utf8')
  let script = compileScript(parse(source).descriptor, { id: 'schedule-week' }).content
  const route = { query: vue.reactive(query) }
  const modules = {
    vue: { ...vue, onMounted() {}, onBeforeUnmount() {} },
    'vue-router': { useRoute: () => route, useRouter: () => ({ replace: async ({ query: next }) => {
      for (const key of Object.keys(route.query)) if (!(key in next) || next[key] === undefined) delete route.query[key]
      for (const [key, value] of Object.entries(next)) if (value !== undefined) route.query[key] = value
    } }) },
    '../../services/portalApi': { portalApi: api },
    '../../services/printInApp': { createInAppPrintFrame: () => printFrame || ({ document: {}, closed: false, close() {}, focus() {}, print() {} }) },
    '../../stores/session': { useSessionStore: () => session },
    '../../stores/ui': { useUiStore: () => ({ notify() {} }) },
    '../../components/academic/studentAcademicCommandGuard': commandGuard,
    '../../components/academic/studentAcademicUi': uiHelpers
  }
  script = script.replace(/^import (.+?) from ['"](.+?)['"];?$/gm, (_, binding, path) => {
    if (binding.startsWith('{')) return `const ${binding.replace(/\bas\b/g, ':')} = modules[${JSON.stringify(path)}]`
    return `const ${binding} = {}`
  }).replace('export default', 'return')
  const component = new Function('modules', 'window', script)(modules, {})
  return { page: component.setup({}, { expose() {} }), route, session }
}

const lesson = (id, week) => ({ itemId: id, courseName: `第${week}周课程`, weekday: 4, slotNo: 4, startWeek: week, endWeek: week, weekParity: 'ALL' })
const schedule = (week) => ({ week, currentWeek: 5, teachingWeeks: 18, termCode: '2026-1', items: [lesson(String(week), week)], todayItems: [] })

const source = (sessionId = '6171', scheduleItemId = '33072') => ({
  verified: true, reason: '', sessionId, scheduleItemId, batchId: '41', termId: '52',
  termCode: '2026-2027-1', courseName: '历史实践课', sessionDate: '2026-09-14',
  weekNo: 2, weekday: 1, slotNo: 1, scopeHeadVersion: 1, publishedAt: '2026-09-01T00:00:00Z',
  teacherName: '历史任课教师', className: '历史教学班', classroom: '历史实训室'
})
const sourcePayload = detail => ({ items: [{ sessionId: detail.sessionId, sourceDetail: detail }] })
const sourceQuery = (sessionId = '6171', lesson = '33072') => ({ attendanceSessionId: sessionId, lesson, from: 'attendance', week: '2' })

test('timetable columns follow a Tuesday-start teaching week without moving lessons to another weekday', async () => {
  const monday = { ...lesson('90071992547409931', 6), weekday: 1, startWeek: 5, endWeek: 6 }
  const thursday = { ...lesson('thu', 6), startWeek: 5, endWeek: 6 }
  const { page } = mount({
    academicSchedule: async week => ({ ...schedule(week), items: [monday, thursday] }),
    academicCalendar: async () => ({ weeks: [
      { weekNo: 5, startDate: '2026-09-29', endDate: '2026-10-05' },
      { weekNo: 6, startDate: '2026-10-06', endDate: '2026-10-12' }
    ] })
  })
  await page.load(6)
  assert.deepEqual(page.visibleDays.value.map(day => day.value), [2, 3, 4, 5, 1])
  assert.deepEqual(page.visibleDays.value.map(day => page.dayDate(day.value)), ['10/06', '10/07', '10/08', '10/09', '10/12'])
  assert.equal(page.cellItems(1, 4)[0].itemId, monday.itemId)
  assert.equal(page.cellItems(4, 4)[0].itemId, 'thu')
  assert.equal(page.cellItems(2, 4).length, 0)
  page.schedule.value.items.push({ ...monday, itemId: 'sat', weekday: 6 })
  assert.deepEqual(page.visibleDays.value.map(day => day.value), [2, 3, 4, 5, 6, 7, 1])
  assert.equal(page.cellItems(6, 4)[0].itemId, 'sat')
  await page.load(5)
  assert.equal(page.weekRange.value, '09/29—10/05')
  assert.equal(page.dayDate(1), '10/05')
  assert.equal(page.cellItems(1, 4)[0].itemId, monday.itemId)
})

test('Monday-start and unavailable authoritative weeks preserve the ordinary timetable order', async () => {
  const { page } = mount({ academicSchedule: async () => schedule(6), academicCalendar: async () => ({ weeks: [
    { weekNo: 6, startDate: '2026-10-05', endDate: '2026-10-11' }
  ] }) })
  await page.load(6)
  assert.deepEqual(page.visibleDays.value.map(day => day.value), [1, 2, 3, 4, 5])
  assert.equal(page.dayDate(1), '10/05')
  page.weekCalendar.value = []
  assert.deepEqual(page.visibleDays.value.map(day => day.value), [1, 2, 3, 4, 5])
  assert.equal(page.dayDate(1), '')
})

test('historical attendance detail uses the exact authorized session and its saved date, independent of the current timetable', async () => {
  const calls = []
  const api = {
    academicAttendance: async params => { calls.push(params); return sourcePayload(source()) },
    academicSchedule: async () => { throw new Error('Current timetable is unavailable') },
    academicCalendar: async () => { throw new Error('Current calendar is unavailable') }
  }
  const { page, route } = mount(api, sourceQuery())
  await page.load(page.routeWeek())
  assert.equal(page.historyDetail?.value?.sessionDate, '2026-09-14')
  assert.equal(page.historyDetail.value.scheduleItemId, '33072')
  assert.equal(page.historyDetail.value.classroom, '历史实训室')
  await page.refresh()
  assert.deepEqual(calls, [{ session_id: '6171' }, { session_id: '6171' }])
  const remounted = mount(api, { ...route.query }).page
  await remounted.load(remounted.routeWeek())
  assert.equal(remounted.historyDetail.value.sessionDate, '2026-09-14')
  assert.equal(remounted.historyActualWeekday?.value, '周一')
})

test('a swapped lesson displays the actual calendar weekday separately from the frozen timetable weekday', async () => {
  const detail = { ...source(), sessionDate: '2026-09-15', weekday: 1 }
  const { page } = mount({ academicAttendance: async () => sourcePayload(detail) }, sourceQuery())
  await page.load(page.routeWeek())
  assert.equal(page.historyDetail.value.sessionDate, '2026-09-15')
  assert.equal(page.historyActualWeekday?.value, '周二')
  assert.equal(page.historyDetail.value.weekday, 1, 'the frozen logical weekday is retained as timetable evidence')
})

test('historical source mismatches, empty or unverified sources never reveal a current lesson as historical evidence', async () => {
  for (const payload of [
    { items: [] }, sourcePayload({ ...source(), scheduleItemId: '33078' }),
    sourcePayload({ ...source(), sessionId: '6172' }),
    { items: [{ sessionId: '6172', sourceDetail: source() }] },
    { items: [sourcePayload(source()).items[0], sourcePayload(source()).items[0]] },
    sourcePayload({ ...source(), sessionDate: '2026-02-31' }),
    sourcePayload({ ...source(), weekday: '1' }),
    { items: [{ sessionId: '6171', sourceDetail: null }] },
    { items: [{ sessionId: '6171', sourceDetail: { verified: false, reason: 'INTERNAL_CODE' } }] }
  ]) {
    const { page } = mount({ academicAttendance: async () => payload, academicSchedule: async () => schedule(2), academicCalendar: async () => ({ weeks: [] }) }, sourceQuery())
    await page.load(page.routeWeek())
    assert.equal(page.historyDetail?.value, null)
    assert.match(page.historyError.value, /无法核验/)
    assert.doesNotMatch(page.historyError.value, /INTERNAL_CODE/)
    assert.equal(page.selectedLesson.value, undefined)
  }
})

test('historical read failures clear evidence, report permission refusal, and retry the same exact large ids', async () => {
  const id = '9007199254740993123', lessonId = '9007199254740993124'
  let failure
  const calls = []
  const { page } = mount({
    academicAttendance: async params => { calls.push(params); if (failure) throw failure; return sourcePayload(source(id, lessonId)) },
    academicSchedule: async () => schedule(2), academicCalendar: async () => ({ weeks: [] })
  }, sourceQuery(id, lessonId))
  await page.load(page.routeWeek())
  assert.equal(page.historyDetail?.value?.sessionId, id)
  failure = { httpStatus: 403, message: 'PRIVATE_CODE' }
  await page.refresh()
  assert.equal(page.historyDetail.value, null)
  assert.match(page.historyError.value, /无权/)
  assert.doesNotMatch(page.historyError.value, /PRIVATE_CODE/)
  failure = new TypeError('Failed to fetch')
  await page.refresh()
  assert.equal(page.historyDetail.value, null)
  assert.match(page.historyError.value, /网络|读取失败/)
  failure = null
  await page.refresh()
  assert.equal(page.historyDetail.value.scheduleItemId, lessonId)
  assert.ok(calls.every(params => params.session_id === id))
})

test('returning to the current timetable removes historical context and ignores a slow old source read', async () => {
  const old = deferred()
  const { page, route } = mount({
    academicAttendance: async () => old.promise,
    academicSchedule: async week => schedule(week), academicCalendar: async () => ({ weeks: [] })
  }, sourceQuery())
  const pending = page.load(page.routeWeek())
  await page.closeLesson()
  await vue.nextTick(); await setImmediate()
  old.resolve(sourcePayload(source()))
  await pending
  assert.equal(route.query.attendanceSessionId, undefined)
  assert.equal(route.query.lesson, undefined)
  assert.equal(route.query.week, '2')
  assert.equal(page.historyDetail?.value, null)
  assert.equal(page.items.value[0].itemId, '2')
})

test('old historical responses cannot overwrite another routed session or identity', async () => {
  const old = deferred()
  const { page, route, session } = mount({
    academicAttendance: async params => params.session_id === '6171' ? old.promise : sourcePayload(source('6172', '33079')),
    academicSchedule: async () => schedule(2), academicCalendar: async () => ({ weeks: [] })
  }, sourceQuery())
  const pending = page.load(page.routeWeek())
  route.query.attendanceSessionId = '6172'; route.query.lesson = '33079'
  await vue.nextTick(); await setImmediate()
  assert.equal(page.historyDetail?.value?.sessionId, '6172')
  session.user = { userId: 'B', studentNo: 'S002' }
  await vue.nextTick()
  assert.equal(page.historyDetail.value, null, 'identity changes immediately clear the previous student source')
  assert.match(page.historyError.value, /身份已变化/)
  await page.load(page.routeWeek())
  old.resolve(sourcePayload(source()))
  await pending
  assert.equal(page.historyDetail.value.sessionId, '6172')
  assert.equal(page.historyDetail.value.scheduleItemId, '33079')
})

test('invalid or repeated session query values are never used to request historical attendance', async () => {
  let calls = 0
  for (const id of ['', '0', '6171x', ['6171', '6172']]) {
    const { page, route } = mount({
      academicAttendance: async () => { calls++; return sourcePayload(source()) },
      academicSchedule: async week => schedule(week || 5), academicCalendar: async () => ({ weeks: [] })
    }, sourceQuery(id))
    await page.load(page.routeWeek())
    assert.equal(page.historyDetail.value, null)
    assert.equal(page.loading.value, false)
    assert.match(page.historyError.value, /无法核验/)
    await page.closeLesson()
    await vue.nextTick(); await setImmediate()
    assert.equal(route.query.attendanceSessionId, undefined)
    assert.equal(page.historyMode.value, false)
  }
  assert.equal(calls, 0)
})

test('an identity change during a pending historical read clears evidence and discards the old result without another request', async () => {
  const pendingSource = deferred()
  const { page, session } = mount({ academicAttendance: async () => pendingSource.promise }, sourceQuery())
  const pending = page.load(page.routeWeek())
  session.user = { userId: 'B', studentNo: 'S002' }
  await vue.nextTick()
  pendingSource.resolve(sourcePayload(source()))
  await pending
  assert.equal(page.historyDetail.value, null)
  assert.equal(page.loading.value, false)
  assert.match(page.historyError.value, /身份已变化/)
})

test('an attendance backlink missing from the authorized week shows a notice without substituting another lesson', async () => {
  const { page, route } = mount({
    academicSchedule: async () => ({ ...schedule(2), items: ['33078', '33079', '33082', '33101'].map(id => lesson(id, 2)) }),
    academicCalendar: async () => ({ weeks: [] })
  }, { week: '2', lesson: '33072', from: 'attendance' })
  await page.load(page.routeWeek())
  assert.equal(page.selectedLesson.value, undefined)
  assert.match(page.lessonNotice?.value || '', /不在当前本人正式课表|无法核验/)
  assert.equal(page.items.value.length, 4, 'the authorized week remains available')
  assert.equal(page.returnedFromAttendance.value, true)
  assert.equal(route.query.lesson, '33072', 'the requested historical id is never replaced by the first lesson')
  await page.closeLesson()
  await vue.nextTick()
  assert.equal(page.lessonNotice.value, '')
  assert.equal(route.query.week, '2')
})

test('a successful retry restores the exact linked decimal id after a failed read, including remount and closing detail', async () => {
  const id = '9007199254740993123'
  let fail = true
  const api = {
    academicSchedule: async () => {
      if (fail) throw new TypeError('Failed to fetch')
      return { ...schedule(2), items: [lesson('9007199254740993124', 2), lesson(id, 2)] }
    },
    academicCalendar: async () => ({ weeks: [] })
  }
  const { page, route } = mount(api, { week: '2', lesson: id, from: 'attendance' })
  await page.load(page.routeWeek())
  assert.equal(page.selectedLesson.value, undefined)
  assert.match(page.error.value, /网络|读取失败/)
  fail = false
  await page.refresh()
  assert.equal(page.selectedLesson.value?.itemId, id)
  assert.equal(page.lessonNotice.value, '')
  const reloaded = mount(api, { ...route.query }).page
  await reloaded.load(reloaded.routeWeek())
  assert.equal(reloaded.selectedLesson.value?.itemId, id)
  await page.closeLesson()
  await vue.nextTick()
  await page.refresh()
  assert.equal(page.selectedLesson.value, undefined, 'refresh cannot reopen a deliberately closed detail')
})

test('refresh keeps a lesson explicitly opened from the week grid instead of restoring the old missing backlink', async () => {
  const { page, route } = mount({
    academicSchedule: async () => ({ ...schedule(2), items: [lesson('33078', 2), lesson('33079', 2)] }),
    academicCalendar: async () => ({ weeks: [] })
  }, { week: '2', lesson: '33072', from: 'attendance' })
  await page.load(page.routeWeek())
  assert.equal(page.selectedLesson.value, undefined)
  // The grid button assigns this same item key to the component's selected lesson.
  page.selectedLessonId.value = page.itemKey(page.items.value[1])
  assert.equal(page.selectedLesson.value.itemId, '33079')
  await page.refresh()
  assert.equal(page.selectedLesson.value?.itemId, '33079')
  assert.equal(page.lessonNotice.value, '')
  assert.equal(route.query.lesson, '33072', 'refresh must not treat the old URL as a new selection')
})

test('a late week response cannot revive an older attendance backlink or hide the current missing-link notice', async () => {
  const old = deferred()
  const { page, route } = mount({
    academicSchedule: async week => week === 2 ? old.promise : schedule(3),
    academicCalendar: async () => ({ weeks: [] })
  }, { week: '2', lesson: '33072', from: 'attendance' })
  const pending = page.load(2)
  route.query.week = '3'
  route.query.lesson = '33073'
  await vue.nextTick(); await setImmediate()
  old.resolve({ ...schedule(2), items: [lesson('33072', 2)] })
  await pending
  assert.equal(page.selectedWeek.value, 3)
  assert.equal(page.selectedLesson.value, undefined)
  assert.match(page.lessonNotice?.value || '', /不在当前本人正式课表|无法核验/)
  assert.equal(route.query.lesson, '33073')
})

test('configured teaching weeks above thirty remain navigable within the formal ninety-nine-week limit', async () => {
  const weeks = []
  const { page, route } = mount({
    academicSchedule: async (week) => { weeks.push(week); return { ...schedule(week), teachingWeeks: 100 } },
    academicCalendar: async () => ({ weeks: [] })
  }, { week: '31' })
  await page.load(page.routeWeek())
  await page.moveWeek(1)
  await vue.nextTick(); await setImmediate()
  assert.equal(route.query.week, '32')
  assert.equal(page.selectedWeek.value, 32)
  assert.deepEqual(weeks, [31, 32])
  await page.changeWeek(99)
  await vue.nextTick(); await setImmediate()
  assert.equal(page.maxWeek.value, 99)
  assert.equal(page.selectedWeek.value, 99)
  await page.moveWeek(1)
  assert.deepEqual(weeks, [31, 32, 99])
})

test('student schedule asks the server for week six, keeps it on refresh, and returns to the current week', async () => {
  const weeks = []
  const api = {
    academicSchedule: async (week) => { weeks.push(week); return schedule(week || 5) },
    academicCalendar: async () => ({ weeks: [] })
  }
  const { page, route } = mount(api)
  await page.load(null)
  assert.equal(page.selectedWeek.value, 5)
  await page.moveWeek(1)
  await vue.nextTick(); await setImmediate()
  assert.equal(page.selectedWeek.value, 6)
  assert.equal(route.query.week, '6')
  assert.equal(page.dayItems(4)[0].itemId, '6')
  await page.refresh()
  assert.equal(page.selectedWeek.value, 6)
  const reloaded = mount(api, { ...route.query }).page
  await reloaded.load(reloaded.routeWeek())
  assert.equal(reloaded.selectedWeek.value, 6, 'a full page remount reads the week persisted in the URL')
  await page.changeWeek(page.currentWeekInRange.value)
  await vue.nextTick(); await setImmediate()
  assert.equal(page.selectedWeek.value, 5)
  assert.equal(route.query.week, '5')
  assert.deepEqual(weeks, [null, 6, 6, 6, 5])
})

test('deep link requests its week and failed week read clears old facts but retries the same week', async () => {
  const weeks = []
  let fail = false
  const { page, route } = mount({
    academicSchedule: async (week) => { weeks.push(week); if (fail) throw new TypeError('Failed to fetch'); return schedule(week || 5) },
    academicCalendar: async () => ({ weeks: [] })
  }, { week: '6', lesson: '6' })
  await page.load(page.routeWeek())
  assert.equal(page.selectedWeek.value, 6)
  assert.equal(page.selectedLesson.value.itemId, '6')
  await page.closeLesson()
  assert.equal(route.query.lesson, undefined)
  await page.refresh()
  assert.equal(page.selectedLessonId.value, '', 'refresh must not reopen a detail the student already closed')
  fail = true
  await page.load(7)
  assert.equal(page.selectedWeek.value, null)
  assert.equal(page.items.value.length, 0)
  assert.match(page.error.value, /网络|读取失败/)
  fail = false
  await page.refresh()
  assert.equal(page.selectedWeek.value, 7)
  assert.deepEqual(weeks, [6, 6, 7, 7])
  route.query.week = '5'
  await vue.nextTick(); await setImmediate()
  assert.equal(page.selectedWeek.value, 5)
  assert.equal(weeks.at(-1), 5)
})

test('late old-week and old-identity responses cannot overwrite the latest student schedule', async () => {
  const old = deferred()
  const session = { user: { userId: 'A', studentNo: 'S001' }, token: 'A' }
  const { page } = mount({
    academicSchedule: async (week) => week === 5 ? old.promise : schedule(6),
    academicCalendar: async () => ({ weeks: [] })
  }, {}, session)
  const first = page.load(5)
  session.user = { userId: 'B', studentNo: 'S002' }; session.token = 'B'
  await page.load(6)
  old.resolve(schedule(5))
  await first
  assert.equal(page.selectedWeek.value, 6)
  assert.equal(page.items.value[0].itemId, '6')
})

test('printing week six requests the same formal week in the audited document', async () => {
  const doc = { createElement(tag) { return { tag, ownerDocument: doc, textContent: '', children: [], appendChild(node) { this.children.push(node) } } } }
  doc.head = doc.createElement('head'); doc.body = doc.createElement('body')
  const frame = { document: doc, printed: false, closed: false, focus() {}, print() { this.printed = true }, close() { this.closed = true } }
  const bodies = []
  const { page } = mount({
    academicSchedule: async (week) => schedule(week),
    academicCalendar: async () => ({ weeks: [] }),
    academicSchedulePrint: async (body) => { bodies.push(body); return { document: schedule(body.week), watermark: '本人', loggedAt: '现在' } }
  }, {}, undefined, frame)
  await page.load(6)
  await page.printSchedule()
  assert.equal(bodies[0].week, 6)
  assert.equal(frame.printed, true)
})
