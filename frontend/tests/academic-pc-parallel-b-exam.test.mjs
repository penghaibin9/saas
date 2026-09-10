import test from 'node:test'
import assert from 'node:assert/strict'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'

function exam(api, convenienceApi) {
  const result = page('AaExamConsoleView', { academicAffairsExamApi: api, academicAffairsExamConvenienceApi: convenienceApi })
  result.state.current = { batchId: 'a' }
  result.state.autoPlan = { dates: ['2026-10-01'], sessions: [{ start: '08:00', end: '09:00' }], maxPerDayPerClass: 1 }
  result.state.refresh = async () => {}
  return result.state
}

test('exam batch switch between writes does not arrange the newly selected batch', async () => {
  const old = deferred(); let arranged = 0
  const state = exam({ autoArrange: async () => { arranged++; return { code: 1 } } }, { autoTimes: () => old.promise })
  const pending = state.runAutoArrange()
  state.current = { batchId: 'b' }
  old.resolve({ code: 0, data: { assigned: 2 } })
  await pending
  assert.equal(arranged, 0)
})

test('retry after successful time assignment repeats only failed room arrangement', async () => {
  let timeCalls = 0, arrangeCalls = 0
  const state = exam({ autoArrange: async () => ++arrangeCalls === 1 ? { code: 1, message: '考场容量不足' } : { code: 0, data: { arrangedCourses: 2, missedCourses: 0 } } }, { autoTimes: async () => { timeCalls++; return { code: 0, data: { assigned: 2 } } } })
  await state.runAutoArrange()
  assert.match(state.autoPlanError, /考场容量不足/)
  await state.runAutoArrange()
  assert.equal(timeCalls, 1)
  assert.equal(arrangeCalls, 2)
})

test('incremental arrangement cannot report no gaps when full readiness still has gaps', async () => {
  const state = exam({ autoArrange: async () => ({ code: 0, data: { batchId: 'a', arrangedCourses: 0, skippedCourses: 1, missedCourses: 0, misses: [], invigilatorGaps: [] } }) }, { autoTimes: async () => ({ code: 0, data: { assigned: 1, misses: [] } }) })
  state.refresh = async () => { state.readiness = { canPublish: false, invigilatorGapCount: 1, missedCourseCount: 0, roomShortageCount: 0 } }
  await state.runAutoArrange()
  assert.equal(state.autoArrangeComplete, false)
  state.readiness = null
  assert.equal(state.autoArrangeComplete, false)
  state.readiness = { canPublish: true, invigilatorGapCount: 0, missedCourseCount: 0, roomShortageCount: 0 }
  assert.equal(state.autoArrangeComplete, true)
})

test('selection watcher does not invalidate the new batch detail request', async () => {
  const old = deferred()
  const { state, definition } = page('AaExamConsoleView', {
    academicAffairsExamApi: { listCourses: () => old.promise, batchStats: async () => ({ code: 0, data: {} }) },
    academicAffairsExamConvenienceApi: { getReadiness: async () => ({ code: 0, data: { invigilatorGapCount: 1 } }) }
  })
  const pending = state.select({ batchId: 'b' })
  definition.watch['current.batchId'].call(state)
  old.resolve({ code: 0, data: { list: [{ examCourseId: 'b-course' }] } })
  await pending
  assert.equal(state.courses[0]?.examCourseId, 'b-course')
})

test('exam lifecycle confirmation cannot follow a changed batch', async () => {
  let writes = 0
  const state = exam({ publishBatch: async () => { writes++; return { code: 1 } } }, {})
  state.lc('publishBatch', '发布')
  state.current = { batchId: 'b' }
  await state.onConfirm()
  assert.equal(writes, 0)
})
