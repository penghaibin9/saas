import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../src/pages/student/academic-affairs/schedule.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '')
  .replace('export default', 'module.exports =')

function mount(getMySchedule) {
  const context = {
    module: { exports: {} },
    AcademicPageNav: {}, AcademicPageState: {},
    currentSessionGeneration: () => 1,
    studentApi: { getMySchedule }, safeToast() {}, go() {},
  }
  vm.runInNewContext(script, context)
  const options = context.module.exports
  const page = { ...options.data() }
  for (const [name, method] of Object.entries(options.methods)) page[name] = method.bind(page)
  for (const [name, getter] of Object.entries(options.computed)) {
    Object.defineProperty(page, name, { get: () => getter.call(page) })
  }
  return page
}

test('网页周次与上课日使用页面内底部选择面板，微信保留原生选择器', async () => {
  const pickerTags = [...source.matchAll(/<picker\b[^>]*>/g)].map(match => match[0])
  assert.equal(pickerTags.length, 2)
  for (const tag of pickerTags) {
    assert.match(tag, /mode="selector"/)
  }
  assert.match(source, /<!-- #ifdef H5 -->[\s\S]*?pickerOpen = 'week'/)
  assert.match(source, /<!-- #ifdef H5 -->[\s\S]*?pickerOpen = 'day'/)
  assert.match(source, /class="sc__picker-mask"/)
  assert.match(source, /\.sc__picker-mask \{ position: fixed; inset: 0;/)
  assert.match(source, /\.sc__picker-sheet \{ width: 100%; max-width: 440px;/)
  assert.match(source, /class="sc__picker-option"[\s\S]*?chooseWeek\(index \+ 1\) : chooseDay\(index\)/)

  const calls = []
  const page = mount(async params => {
    calls.push(params)
    return {
      termCode: '2026-1', currentWeek: 5, teachingWeeks: 18,
      week: Number(params.week) || 5, todayItems: [], items: [],
    }
  })
  await page.load()
  page.pickerOpen = 'day'
  page.chooseDay(4)
  assert.equal(page.pickerOpen, '')
  assert.equal(page.selectedDay, 4)
  assert.equal(page.dayLabels[page.selectedDay], '周四')
  page.pickerOpen = 'week'
  await page.chooseWeek(6)
  assert.equal(page.pickerOpen, '')
  assert.equal(Number(calls.at(-1).week), 6)
  assert.equal(page.selectedWeek, 6)
  assert.equal(page.weekPickerIndex, 5)
})

test('微信原生选择器事件仍按第6周请求正式目标周', async () => {
  const calls = []
  const page = mount(async params => {
    calls.push(params)
    return {
      termCode: '2026-1', currentWeek: 5, teachingWeeks: 18,
      week: Number(params.week) || 5, todayItems: [], items: [],
    }
  })
  await page.load()
  assert.equal(page.selectedWeek, 5)
  await page.onWeekChange({ detail: { value: '5' } })
  assert.equal(Number(calls.at(-1).week), 6)
  assert.equal(page.selectedWeek, 6)
  assert.equal(page.weekPickerIndex, 5)
})
