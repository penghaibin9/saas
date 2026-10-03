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
