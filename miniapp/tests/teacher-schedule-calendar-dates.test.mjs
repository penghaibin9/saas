import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const source = readFileSync(new URL('../src/pages/teacher/my-schedule/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
const context = {}
vm.runInNewContext(script, context)
function page(termStartDate, selectedWeek) {
  const state = { ...context.component.data(), termStartDate, selectedWeek }
  for (const [name, getter] of Object.entries(context.component.computed)) Object.defineProperty(state, name, { get: () => getter.call(state) })
  return state
}

test('Tuesday-start teaching week matches the school calendar, not a guessed Monday', () => {
  const state = page('2026-09-01', 2)
  assert.equal(state.weekDateLabel, '9月8日—14日')
  assert.equal(state.weekDays.find(day => day.weekday === 1).dateNumber, 14)
  assert.equal(state.weekDays.find(day => day.weekday === 4).dateNumber, 10)
  state.selectedWeek = 3
  assert.equal(state.weekDateLabel, '9月15日—21日')
  assert.equal(state.weekDays.find(day => day.weekday === 5).dateNumber, 18)
})

test('Monday starts and year boundaries retain real weekday dates', () => {
  const state = page('2026-12-28', 1)
  assert.equal(state.weekDateLabel, '12月28日—1月3日')
  assert.equal(state.weekDays.find(day => day.weekday === 7).dateNumber, 3)
})

test('missing/invalid authority or all-weeks view never invent dates', () => {
  for (const [start, week] of [['', 2], ['2026-02-30', 1], ['2026-09-01', 0]]) {
    const state = page(start, week)
    assert.equal(state.weekDateLabel, '')
    assert.ok(state.weekDays.every(day => day.dateNumber === undefined))
  }
})
