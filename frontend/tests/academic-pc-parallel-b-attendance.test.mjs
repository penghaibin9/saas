import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function setup(api) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaAttendanceStatsView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { academicAffairsApi: api, currentUserFromToken: () => ({ userId: 'a' }), matchPermission: () => false } }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  const state = { ctx: { currentRole: {}, dataScope: {}, permissionPatterns: [] }, $route: { query: {} } }
  Object.assign(state, definition.data.call(state), definition.methods)
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return state
}

test('attendance sessions use the selected server page and preserve total', async () => {
  let params
  const state = setup({ getAttendanceSessions: async query => { params = query; return { code: 0, data: { list: [], total: 65 } } } })
  state.panel = 'sessions'; state.page = 2
  await state.load()
  assert.equal(params.page, 2)
  assert.equal(state.sessionTotal, 65)
})

test('attendance student summary requests the selected server page and preserves global totals', async () => {
  let params
  const state = setup({ getAttendanceStats: async query => { params = query; return { code: 0, data: { students: [{ studentId: 's21' }], studentTotal: 13000, absentStudentCount: 46 } } } })
  state.panel = 'stats'; state.studentPage = 21
  await state.load()
  assert.equal(params.page, 21)
  assert.equal(params.pageSize, 20)
  assert.equal(state.studentTotal, 13000)
  assert.equal(state.absentStudentCount, 46)
  assert.equal(state.visibleStudents.length, 1)
})

test('late attendance response does not overwrite a different class', async () => {
  let resolve
  const state = setup({ getAttendanceStats: () => new Promise(done => { resolve = done }) })
  state.classId = 'a'
  const pending = state.load()
  state.classId = 'b'
  state.data = { sessionCount: 2, students: [] }
  resolve({ code: 0, data: { sessionCount: 99, students: [] } })
  await pending
  assert.equal(state.data.sessionCount, 2)
})

test('attendance network failure renders a recoverable error and releases loading', async () => {
  const state = setup({ getAttendanceStats: async () => { throw Error('连接中断') } })
  await state.load()
  assert.equal(state.error, '连接中断')
  assert.equal(state.loading, false)
})
