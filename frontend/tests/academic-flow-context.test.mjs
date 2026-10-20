import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import * as flow from '../src/modules/academicAffairs/academicFlowContext.js'

const identity = { tenantId: 'school-a', userId: 'user-a', currentRoleCode: 'SCHOOL_ADMIN', activeContextId: 'role-a' }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function page(name, dependencies = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const context = { dependencies: { ...flow, toast: { error() {}, success() {}, info() {} }, ...dependencies }, setTimeout, clearTimeout }
  vm.runInNewContext(script, context)
  return context.component
}
function state(component, extra = {}) {
  return Object.assign(component.data(), component.methods, { $nextTick: async () => {} }, extra)
}

test('route parsing rejects repeated object/tab parameters and preserves zero-free pagination', () => {
  assert.match(flow.academicRouteState({ query: { taskId: ['1', '2'] } }).error, /参数无效/)
  assert.match(flow.academicRouteState({ query: { tab: ['result', 'adjust'] } }).error, /无法识别/)
  assert.equal(flow.academicRouteState({ query: { batchId: '42', page: '3' } }).batchId, '42')
  assert.equal(flow.academicRouteState({ query: { teacherKey: 'teacher.name@school.test' } }).error, '')
  assert.equal(flow.academicRouteState({ query: { page: '-1' } }).page, 1)
  assert.equal(flow.academicRouteState({ query: { tab: 'constraint' } }, { tabs: ['constraint'] }).tab, 'constraint')
})

test('late responses invalidate on object, tenant, role, context and permission changes', () => {
  let claims = { ...identity }, scope = { permissionPatterns: ['a', 'b'] }, object = 'task-a'
  const gate = flow.createAcademicRequestGate(() => JSON.stringify([flow.academicIdentity(claims, scope), object]))
  const old = gate.begin(); object = 'task-b'; assert.equal(old(), false)
  for (const [key, value] of [['tenantId', 'school-b'], ['currentRoleCode', 'TEACHER'], ['activeContextId', 'role-b']]) {
    const pending = gate.begin(); claims = { ...claims, [key]: value }; assert.equal(pending(), false)
  }
  const permissionRead = gate.begin(); scope.permissionPatterns = ['a']; assert.equal(permissionRead(), false)
  const first = gate.begin(), second = gate.begin(); assert.equal(first(), false); assert.equal(second(), true)
  gate.invalidate(); assert.equal(second(), false)
})

test('return references are bounded, expire, isolate identity and reject external or tampered destinations', () => {
  let raw = '', clock = 100, serial = 0
  const storage = { getItem: () => raw, setItem: (_, value) => { raw = value }, removeItem: () => { raw = '' } }
  const returns = flow.createAcademicReturnStore(storage, { now: () => clock, token: () => String(++serial) })
  const route = { path: '/admin/academic-affairs/scheduling', query: { tab: 'result', batchId: '9', page: '3', studentName: 'excluded', returnUrl: 'https://evil.test' } }
  const id = returns.remember(route, 'identity-a', 750)
  assert.equal(returns.resolve(id, 'identity-b'), null)
  assert.deepEqual(returns.resolve(id, 'identity-a'), { path: '/admin/academic-affairs/scheduling?tab=result&batchId=9&page=3', scrollTop: 750 })
  assert.equal(raw.includes('excluded'), false)
  const saved = JSON.parse(raw); saved.entries[0].path = 'https://evil.test/admin/academic-affairs'; raw = JSON.stringify(saved)
  assert.equal(returns.resolve(id, 'identity-a'), null)
  for (let i = 0; i < 35; i++) returns.remember(route, 'identity-a')
  assert.equal(JSON.parse(raw).entries.length, 30)
  clock += 30 * 60 * 1000; assert.equal(returns.resolve(String(serial), 'identity-a'), null)
  assert.equal(returns.remember({ path: '/admin/system' }, 'identity-a'), '')
})

test('same component query navigation loads exactly the requested grade task and hides archived commands by row status', async () => {
  const pendingA = deferred(), calls = []
  const component = page('AaGradePublishView', { academicAffairsApi: { getGradeTasks: query => {
    calls.push(query)
    return query.taskId === '11' ? pendingA.promise : Promise.resolve({ code: 0, data: { list: [{ gradeTaskId: '12', status: 'ARCHIVED' }], total: 1 } })
  } } })
  const s = state(component, { $route: { fullPath: '/grade?taskId=11', query: { taskId: '11' } }, academicFlow: { identity: () => 'school-role', restorePosition() {} } })
  s.readGate = flow.createAcademicRequestGate(() => s.contextKey())
  const a = s.syncRoute()
  s.$route = { fullPath: '/grade?taskId=12', query: { taskId: '12' } }
  await s.syncRoute()
  pendingA.resolve({ code: 0, data: { list: [{ gradeTaskId: '11', status: 'ACADEMIC_REVIEW' }], total: 1 } }); await a
  assert.equal(s.rows[0].gradeTaskId, '12'); assert.equal(s.rows[0].status, 'ARCHIVED')
  assert.equal(calls[1].status, undefined)
  assert.equal(s.loading, false)
})

test('schedule view cannot show a response after batch changes with unchanged class', async () => {
  const transport = deferred()
  const c = page('AaScheduleViewsView', { academicAffairsApi: { getScheduleClassView: () => transport.promise } })
  const s = state(c, { batchId: '1', query: 'class-a' })
  const pending = s.loadView(); s.batchId = '2'; s.resetView()
  transport.resolve({ code: 0, data: { items: [{ itemId: 'old' }] } }); await pending
  assert.equal(s.items.length, 0); assert.equal(s.loadedQuery, '')
})

test('moving a lesson never writes after the preflight object context changes', async () => {
  const transport = deferred(); let writes = 0
  const c = page('AaScheduleMaintainView', { academicAffairsApi: {
    preflightScheduleMove: () => transport.promise, moveScheduleItem: () => { writes++ }
  } })
  const s = state(c, { canEditBatch: true, batchId: '1', classId: 'class-a' })
  s.moveGate = flow.createAcademicRequestGate(() => s.contextKey())
  const pending = s.onItemMove({ item: { itemId: 'lesson-a' }, weekday: 2, slotNo: 3 })
  s.classId = 'class-b'
  transport.resolve({ code: 0, data: { allowed: true } }); await pending
  assert.equal(writes, 0)
})

test('changing a candidate invalidates allowed preflight immediately before debounce', () => {
  const c = page('AaScheduleMaintainView')
  const s = state(c)
  s.add = { visible: true, taskId: 'task-a' }
  s.preflight.result = { allowed: true }
  s.queuePreflight()
  assert.equal(s.preflight.result, null)
  assert.equal(s.preflight.requestSeq, 1)
  clearTimeout(s.preflight.timer)
})

test('scheduling rejects a confirmation opened for a different batch', async () => {
  const c = page('AaSchedulingConsoleView')
  const s = state(c, { ctx: {}, $route: { fullPath: '/scheduling' }, academicFlow: { identity: () => 'identity' } })
  let writes = 0
  s.workbenchBatchId = '1'; s.pendingContextKey = s.commandContextKey(); s.pendingAction = () => { writes++ }
  s.workbenchBatchId = '2'; await s.onConfirm()
  assert.equal(writes, 0); assert.equal(s.pendingAction, null)
})

test('switching the room view commits its route before mounting a child that synchronizes filters', async () => {
  const c = page('AaSchedulingConsoleView'); let destination
  const s = state(c, { tab: 'rules', $route: { path: '/scheduling', query: { tab: 'constraint', termId: '3' } }, $router: { push: async route => { destination = route } } })
  await s.switchTab('room')
  assert.equal(destination.query.tab, 'room'); assert.equal(destination.query.termId, '3')
  assert.equal(s.tab, 'rules')
})
