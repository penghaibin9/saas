import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
const source = fs.readFileSync(new URL('../src/pages/teacher/affairs-review/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
function make(api) {
  const component = new Function('teacherApi', 'affairsContractApi', 'affairsAppealApi', 'normalizeError', 'toast', script)({}, {}, api, () => ({}), () => {})
  const vm = { ...component.data(), ...component.methods, kind: 'AID_OBJECTION_REVIEW' }
  for (const [key, get] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => get.call(vm) })
  return vm
}
test('objection queue sends page parameters and exposes only server-authorized actions', async () => {
  const calls = []
  const vm = make({ getPending: async (kind, params) => { calls.push([kind, params]); return { total: 21, items: [{ objectionId: String(params.page), allowedActions: params.page === 1 ? ['REVIEW'] : [] }] } } })
  await vm.load(); await vm.loadMore()
  assert.deepEqual(calls.map(x => x[1].page), [1, 2])
  assert.equal(calls[0][0], 'AID_OBJECTION')
  assert.equal(vm.visibleAppealActions(vm.list[0]).length, 2)
  assert.equal(vm.visibleAppealActions(vm.list[1]).length, 0)
})
test('notification reads its exact objection, including a closed result, without loading an unrelated queue', async () => {
  const vm = make({ getPending: () => assert.fail('must not replace exact record'), getAidObjectionDetail: async id => ({ objectionId: id, status: 'CLOSED', resultLabel: '异议不成立', allowedActions: [] }) })
  vm.focusId = '201'; await vm.load()
  assert.equal(vm.list[0].objectionId, '201'); assert.equal(vm.expandedId, '201')
  assert.equal(vm.visibleAppealActions(vm.list[0]).length, 0)
})

test('school review roles have explicit teacher identities while unknown roles remain unsupported', async () => {
  const source = fs.readFileSync(new URL('../src/config/roles.config.js', import.meta.url), 'utf8')
  const { roleKeyFromBackendRole, roleConfigs } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
  for (const role of ['SCHOOL_ADMIN', 'STUDENT_AFFAIRS_ADMIN', 'STUDENT_AFFAIRS', 'SA_ADMIN']) {
    const key = roleKeyFromBackendRole(role)
    assert.ok(key); assert.equal(roleConfigs[key].side, 'teacher')
    assert.equal(roleConfigs[key].homeRoute, '/pages/teacher/workbench/index')
    assert.ok(roleConfigs[key].quickActions.some(x => x.key === 'affairs'))
  }
  assert.equal(roleKeyFromBackendRole('UNKNOWN_SCHOOL_ROLE'), '')
})

test('installed workbench adapter translates the real role without replacing server totals or actions', async () => {
  const configSource = fs.readFileSync(new URL('../src/config/roles.config.js', import.meta.url), 'utf8')
  const { roleConfigs, roleKeyFromBackendRole } = await import('data:text/javascript;base64,' + Buffer.from(configSource).toString('base64'))
  const installer = fs.readFileSync(new URL('../src/services/mobilePerformanceInstaller.teacher.js', import.meta.url), 'utf8')
    .replace(/^import .+$/gm, '').replace('export function', 'function').replace('export default ensureTeacherPerformanceApi', 'return ensureTeacherPerformanceApi')
  const api = {}; const action = { kind: 'navigate', recordId: '201' }
  const data = { _role: 'SCHOOL_ADMIN', contextTitle: 'SCHOOL_ADMIN', pendingTotal: 53, metrics: [{ key: 'pending', value: 53 }], dueSoon: [{ id: 201, action }] }
  const install = new Function('teacherApi', 'mockRequest', 'realFirstStrict', 'realRequest', 'M', 'roleConfigs', 'roleKeyFromBackendRole', installer)(api, () => assert.fail('no mock'), (_key, real) => real(), async () => data, {}, roleConfigs, roleKeyFromBackendRole)
  install(); const result = await api.getWorkbench('school_admin')
  assert.equal(result.contextTitle, '学校管理员'); assert.equal(result.pendingTotal, 53)
  assert.equal(result.dueSoon, data.dueSoon); assert.equal(result.metrics, data.metrics)
  data._role = 'UNSUPPORTED'; data.contextTitle = 'UNSUPPORTED'
  assert.equal((await api.getWorkbench('school_admin')).contextTitle, '教师')
})

test('workbench badge uses canonical pending count, including zero', () => {
  const page = fs.readFileSync(new URL('../src/pages/teacher/workbench/index.vue', import.meta.url), 'utf8')
  const body = page.match(/todoBadge\(\) \{([\s\S]*?)\n    \},/)[1]
  const badge = new Function(body)
  assert.equal(badge.call({ wb: { metrics: [{ key: 'pending', value: 53 }] } }), 53)
  assert.equal(badge.call({ wb: { metrics: [{ key: 'pending', value: 0 }] } }), 0)
})
