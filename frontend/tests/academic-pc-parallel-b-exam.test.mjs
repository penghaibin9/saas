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

test('teacher exam entry reads only own assignment and discards a late identity response', async () => {
  const pending = deferred()
  let calls = 0
  const { state } = page('AaExamConsoleView', {
    academicAffairsExamApi: { getMyInvigilation: () => { calls++; return pending.promise } }
  })
  state.ctx.currentRole = { roleCode: 'ACADEMIC_TEACHER' }
  const loading = state.load()
  assert.equal(calls, 1)
  state.ctx.currentRole = { roleCode: 'COLLEGE_ADMIN' }
  pending.resolve({ code: 0, data: { items: [{ invigilatorId: 'old' }] } })
  await loading
  assert.equal(state.myInvigilations.length, 0)
})

test('teacher assignment failure clears old schedule and is not an empty success', async () => {
  const { state } = page('AaExamConsoleView', {
    academicAffairsExamApi: { getMyInvigilation: async () => ({ code: 503, message: '监考安排读取失败' }) }
  })
  state.ctx.currentRole = { roleCode: 'ACADEMIC_TEACHER' }
  state.myInvigilations = [{ invigilatorId: 'old' }]
  await state.load()
  assert.equal(state.myInvigilations.length, 0)
  assert.equal(state.error, '监考安排读取失败')
  assert.equal(state.loading, false)
})

test('college confirmation reads its courses without requesting school-only readiness', async () => {
  let readinessCalls = 0
  const { state } = page('AaExamConsoleView', {
    academicAffairsExamApi: { listCourses: async () => ({ code: 0, data: { list: [{ examCourseId: '1' }] } }), batchStats: async () => ({ code: 0, data: {} }) },
    academicAffairsExamConvenienceApi: { getReadiness: async () => { readinessCalls++; return { code: 403 } } }
  })
  state.ctx.dataScope = { scope: 'COLLEGE' }
  await state.select({ batchId: 'a' })
  assert.equal(readinessCalls, 0)
  assert.equal(state.courses.length, 1)
  assert.equal(state.readinessError, '')
})

test('manual seating submits only frozen IDs, blocks insufficient capacity and completed seating', async () => {
  const writes = []
  const state = exam({ assignSeats: async (id, ids) => { writes.push([id, Array.from(ids)]); return { code: 0 } } }, {})
  state.current.status = 'COURSE_CONFIRMED'; state.arrangeVisible = true
  state.arrangeCourse = { examCourseId: 'c', rosterIdentity: { studentIds: ['9007199254740993', '2'] } }
  const room = { examRoomId: 'r', capacity: 1, plannedCount: 0 }
  state.arrangeRooms = [room]; state.readArrangeRooms = async () => {}
  await state.assignFrozenSeats(room)
  assert.equal(writes.length, 0)
  room.capacity = 2
  await state.assignFrozenSeats(room)
  assert.deepEqual(writes, [['r', ['9007199254740993', '2']]])
  room.plannedCount = 2
  await state.assignFrozenSeats(room)
  assert.equal(writes.length, 1)
})

test('room commands keep rejection visible and do not write after publication', async () => {
  let calls = 0
  const state = exam({ addInvigilator: async () => { calls++; return { code: 409, message: '教师时段冲突' } } }, {})
  state.current.status = 'COURSE_CONFIRMED'; state.arrangeVisible = true
  state.arrangeCourse = { examCourseId: 'c' }; state.invigilatorForm = { teacherKey: 'teacher-a', teacherName: '虚构教师' }
  await state.assignRoomInvigilator({ examRoomId: 'r' })
  assert.equal(state.arrangeError, '教师时段冲突')
  assert.equal(state.saving, false)
  state.current.status = 'PUBLISHED'
  await state.assignRoomInvigilator({ examRoomId: 'r' })
  assert.equal(calls, 1)
})

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
