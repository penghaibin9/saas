import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'
import { runAdminQuery, resetAdminQueryCoordinatorForTest } from '../src/services/performance/queryCoordinator.js'

function scheduleApi(read, identity = { userId: 'teacher-A', currentRoleCode: 'TEACHER' }) {
  resetAdminQueryCoordinatorForTest()
  const source = readFileSync(new URL('../src/modules/workbench/api/workbench.api.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/^export /gm, '')
  const sandbox = { request: read, runAdminQuery, getToken: () => 'test-token', currentUserFromToken: () => identity }
  vm.runInNewContext(source, sandbox)
  return sandbox.fetchMyScheduleToday
}

test('teacher home preserves an authoritative empty today instead of displaying the nonempty weekly schedule', async () => {
  const calls = []
  const fetch = scheduleApi(async path => {
    calls.push(path)
    return { items: [{ courseName: '跨周课程', weekday: 6 }], todayItems: [], calendarSource: 'HOLIDAY' }
  })
  assert.equal((await fetch('teacher-A')).items.length, 0)
  assert.deepEqual(calls, ['/academic-affairs/teacher/today'])
})

test('teacher home keeps formal swapped-day occurrences and large object identities without browser weekday filtering', async () => {
  const occurrence = { scheduleItemId: '90071992547409931', courseName: '正式调课课次', weekday: 2, slotNo: 3 }
  const fetch = scheduleApi(async () => ({ items: [{ courseName: '其他周课程' }], todayItems: [occurrence], calendarSource: 'SWAP' }))
  const result = await fetch('teacher-A')
  assert.deepEqual(result.items, [occurrence])
  assert.equal(result.items[0].scheduleItemId, '90071992547409931')
})

test('teacher home reports failed, incomplete and identity-less reads rather than claiming today is empty', async () => {
  const unavailable = new Error('正式课表读取失败')
  const failing = scheduleApi(async () => { throw unavailable })
  await assert.rejects(failing('teacher-A'), error => error === unavailable)
  const malformed = scheduleApi(async () => ({ items: [] }))
  await assert.rejects(malformed('teacher-A'), /今日课表数据不完整/)
  let calls = 0
  const anonymous = scheduleApi(async () => { calls++; return { todayItems: [] } })
  await assert.rejects(anonymous(''), /教师身份尚未就绪/)
  assert.equal(calls, 0)
})

test('the cached today projection remains isolated when the current teacher identity changes', async () => {
  const identity = { userId: 'teacher-A', currentRoleCode: 'TEACHER' }
  let calls = 0
  const fetch = scheduleApi(async () => { calls++; return { todayItems: [{ courseName: identity.userId }] } }, identity)
  assert.equal((await fetch('teacher-A')).items[0].courseName, 'teacher-A')
  identity.userId = 'teacher-B'
  assert.equal((await fetch('teacher-B')).items[0].courseName, 'teacher-B')
  assert.equal(calls, 2)
})

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function workbench(overrides = {}) {
  const source = readFileSync(new URL('../src/modules/workbench/views/WorkbenchView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const dependencies = {
    fetchTodoSummary: async () => ({ role: 'TEACHER', pending: 2 }),
    fetchTodoCount: async () => ({ total: 1 }),
    fetchTodoList: async () => ({ items: [{ todoId: '90071992547409931', typedRouteTarget: '/review/1' }], total: 1 }),
    fetchMessageCount: async () => ({ unread: 3 }),
    fetchSchoolStats: async () => ({ studentTotal: 20 }),
    approvalApi: { getTodos: async () => ({ code: 0, data: { list: [{ taskId: 'approval-1' }] } }) },
    loadPrefs: async () => ({}), parseJsonPref: (value, fallback) => value || fallback,
    tilesPrefKey: () => 'tiles', favoritesPrefKey: () => 'favorites',
    resolveRecipe: () => ({ showSchedule: true }),
    currentUserFromToken: () => ({ userId: 'teacher-1' }),
    fetchMyScheduleToday: async () => ({ items: [] }),
    ...overrides
  }
  const sandbox = { dependencies }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { ...component.data(), ...component.methods, $refs: {} }
  Object.defineProperty(state, 'recipe', { get: () => component.computed.recipe.call(state) })
  return { state, component }
}

test('ready business todos render while statistics, approvals, preferences and schedule are still pending', async () => {
  const stats = deferred(), approvals = deferred(), prefs = deferred(), schedule = deferred()
  const { state } = workbench({ fetchSchoolStats: () => stats.promise,
    approvalApi: { getTodos: () => approvals.promise }, loadPrefs: () => prefs.promise,
    fetchMyScheduleToday: () => schedule.promise })
  const loading = state.load()
  await setImmediate()
  assert.equal(state.loading, false)
  assert.equal(state.summary.pending, 2)
  assert.equal(state.todos[0].todoId, '90071992547409931')
  assert.equal(state.statsLoading, true)
  assert.equal(state.approvalsLoading, true)
  assert.equal(state.scheduleLoading, true)
  approvals.resolve({ code: 0, data: { list: [{ taskId: 'a1' }] } })
  await setImmediate()
  assert.equal(state.approvalsLoading, false)
  assert.equal(state.approvals[0].taskId, 'a1')
  stats.reject(new Error('statistics unavailable'))
  prefs.resolve({}); schedule.resolve({ items: [{ title: '课程' }] })
  await loading
  assert.equal(state.statsError, true)
  assert.equal(state.error, '')
  assert.equal(state.todoTotal, 1)
})

test('late statistics from the previous refresh cannot replace the latest result', async () => {
  const first = deferred()
  let calls = 0
  const { state } = workbench({ fetchSchoolStats: () => ++calls === 1 ? first.promise : Promise.resolve({ studentTotal: 42 }) })
  const old = state.load()
  await setImmediate()
  await state.load()
  first.resolve({ studentTotal: 99 })
  await old
  assert.equal(state.stats.studentTotal, 42)
})

test('unmount discards late core data and does not load preferences for a departed page', async () => {
  const summary = deferred()
  let prefReads = 0
  const { state, component } = workbench({ fetchTodoSummary: () => summary.promise, loadPrefs: async () => { prefReads++; return {} } })
  const loading = state.load()
  component.beforeUnmount.call(state)
  summary.resolve({ pending: 77 })
  await loading
  assert.equal(state.summary.pending, 0)
  assert.equal(prefReads, 0)
})

test('failed core and approval reads retain separate errors and release their loading states', async () => {
  const { state } = workbench({ fetchTodoSummary: async () => { throw new Error('待办连接失败') },
    approvalApi: { getTodos: async () => ({ code: 403, message: '没有审批权限' }) } })
  await state.load()
  assert.equal(state.loading, false)
  assert.equal(state.error, '待办连接失败')
  assert.equal(state.approvalsError, '没有审批权限')
  assert.equal(state.approvalsLoading, false)
})

test('context change clears the previous school data immediately and ignores its pending reads', async () => {
  const oldStats = deferred(), newSummary = deferred()
  let summaries = 0, statistics = 0
  const { state, component } = workbench({
    fetchTodoSummary: () => ++summaries === 1 ? Promise.resolve({ role: 'TEACHER', pending: 2 }) : newSummary.promise,
    fetchSchoolStats: () => ++statistics === 1 ? oldStats.promise : Promise.resolve({ studentTotal: 4 })
  })
  const old = state.load()
  await setImmediate()
  assert.equal(state.todos.length, 1)
  component.watch['ctx.ctxKey'].call(state)
  assert.equal(state.todos.length, 0)
  assert.equal(state.summary.pending, 0)
  assert.equal(state.unread, 0)
  newSummary.resolve({ role: 'TEACHER', pending: 7 })
  oldStats.resolve({ studentTotal: 99 })
  await old
  await setImmediate()
  assert.equal(state.summary.pending, 7)
  assert.equal(state.stats.studentTotal, 4)
})
