import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routeTarget } from '../src/modules/academicAffairs/components/leadershipWall/aa-wall-data.mjs'
import { academicReturnPath } from '../src/modules/academicAffairs/academicFlowContext.js'

function workspace(file, dependencies = {}, extra = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/components/${file}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding.replace(/\s+as\s+/g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const context = { dependencies: { currentUserFromToken: () => ({}), academicIdentity: (_, ctx) => ctx.key,
    safeBusinessMessage: message => message, ...dependencies } }
  vm.runInNewContext(script, context)
  const component = context.component
  const state = { ctx: { key: 'school-a' }, $route: { path: '/admin/academic-affairs', query: {} }, ...component.data(), ...extra }
  for (const [name, fn] of Object.entries(component.methods)) state[name] = fn.bind(state)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(state, name, { get: () => fn.call(state) })
  return { state, component }
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }

test('a late student search cannot replace the new page; denied requests clear old facts', async () => {
  const old = deferred(), fresh = deferred(); let n = 0
  const { state } = workspace('AaAcademicProgressWorkspace', { request: () => ++n === 1 ? old.promise : fresh.promise })
  const first = state.load(); state.$route.query = { keyword: 'new', page: '2' }; const second = state.load()
  fresh.resolve({ items: [{ id: 'new' }], total: 8 }); await second
  old.resolve({ items: [{ id: 'old' }], total: 12 }); await first
  assert.equal(state.rows[0].id, 'new'); assert.equal(state.page, 2)
  const denied = workspace('AaAcademicProgressWorkspace', { request: async () => { throw new Error('403') } }, { rows: [{ id: 'stale' }] }).state
  await denied.load(); assert.equal(denied.rows.length, 0); assert.equal(denied.error, '403')
})

test('unknown requirements and explicit zero differ; low risk remains a risk', () => {
  const { state } = workspace('AaAcademicProgressWorkspace')
  assert.equal(state.ratio({ obtainedCredits: 9, requiredCredits: null }), null)
  assert.equal(state.ratio({ obtainedCredits: 0, requiredCredits: 12 }), 0)
  assert.equal(state.ratio({ obtainedCredits: 9, requiredCredits: 12 }), 75)
  assert.equal(state.hasRisk({ warningLevel: 'LOW' }), true)
  assert.match(state.studentRoute({ id: 'ledger-1', studentId: 'master-2', name: 'Student' }), /studentId=master-2/)
  assert.equal(state.studentRoute({ id: 'legacy' }), '')
})

test('changing class rejects stale lesson responses and retains the selected week', async () => {
  const first = deferred(), second = deferred(); let n = 0
  const { state } = workspace('AaTodayTeachingWorkspace', { academicAffairsApi: { getClassSchedule: () => ++n === 1 ? first.promise : second.promise } }, { initialized: true, classId: '101', week: 2, term: { startDate: '2026-09-07 00:00:00', termId: '7' } })
  const old = state.load(); state.classId = '202'; const current = state.load()
  second.resolve({ code: 0, data: { className: 'Second', items: [{ itemId: '202-1' }] } }); await current
  first.resolve({ code: 0, data: { className: 'First', items: [{ itemId: '101-1' }] } }); await old
  assert.equal(state.items[0].itemId, '202-1'); assert.equal(state.className, 'Second')
  assert.equal(state.dayLabel(1), '周一 14')
  assert.match(academicReturnPath({ path: '/admin/academic-affairs', query: { panel: 'todayTeaching', classId: '202', week: '2' } }), /week=2/)
})

test('unmounted progress reads cannot publish data', async () => {
  const pending = deferred()
  const { state, component } = workspace('AaAcademicProgressWorkspace', { request: () => pending.promise })
  const loading = state.load(); component.beforeUnmount.call(state)
  pending.resolve({ items: [{ id: 'late' }], total: 1 }); await loading
  assert.equal(state.rows.length, 0)
})

test('the real router retains canonical todo object query and hash', () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/admin/academic-affairs/grade-entry', component: {} }] })
  const { state } = workspace('AaOverviewWorkspace', { routeTarget, sourceTimeLabel: value => value }, { $router: router })
  const resolved = router.resolve(state.target('/admin/academic-affairs/grade-entry?filter=pending&recordId=729#queue'))
  assert.equal(resolved.query.recordId, '729')
  assert.equal(resolved.query.filter, 'pending')
  assert.equal(resolved.hash, '#queue')
})

test('ambiguous class deep links fail before defaulting to another class', async () => {
  const { state } = workspace('AaTodayTeachingWorkspace', {}, { $route: { query: { classId: ['101', '202'], week: '2' } } })
  await state.initialize()
  assert.equal(state.classId, '')
  assert.match(state.error, /班级参数/)
  assert.equal(state.items.length, 0)
})
