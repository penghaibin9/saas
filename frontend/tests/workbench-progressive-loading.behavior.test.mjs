import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { setImmediate } from 'node:timers/promises'

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
