import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { ACADEMIC_STUDENT_STATUS_LABELS, ACADEMIC_STATUS_CHANGE_LABELS } from '../src/modules/academicAffairs/config/academicStudentLabels.js'

function page(name, api = {}, extra = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { matchPermission, ACADEMIC_STUDENT_STATUS_LABELS, ACADEMIC_STATUS_CHANGE_LABELS, academicAffairsApi: api, toast: { success() {}, warning() {}, error() {} } } }
  vm.runInNewContext(script, sandbox)
  const component = sandbox.component
  const state = { $route: { params: { studentId: 'student-a' }, query: {} }, $router: { push() {} }, ctx: { permissionPatterns: ['academicAffairs.roster.*', 'academicAffairs.statusChange.*'] }, ...extra }
  Object.assign(state, component.data.call(state), component.methods)
  for (const [key, getter] of Object.entries(component.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return { state, component }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('preserved student status and retained student status have distinct names and entry titles', () => {
  const { state } = page('AaRosterListView')
  state.appliedStatus = 'PRESERVED'
  assert.equal(state.pageTitle, '保留学籍')
  assert.equal(state.statusLabel('PRESERVED'), '保留学籍')
  state.appliedStatus = 'RETAINED'
  assert.equal(state.pageTitle, '留级学生')
  assert.equal(state.statusLabel('RETAINED'), '留级')
  state.filters.status = 'WITHDRAWN'
  assert.equal(state.pageTitle, '留级学生', 'unsubmitted filters must not relabel the existing result set')
})

test('switching classification menus on the same component replaces filters and discards stale results', async () => {
  const old = deferred()
  const { state, component } = page('AaRosterListView', { getRoster: params => params.status === 'SUSPENDED' ? old.promise : Promise.resolve({ code: 0, data: { list: [{ studentId: 'preserved' }], total: 1 } }) })
  state.filters.status = 'SUSPENDED'
  const pending = state.load()
  state.$route.query = { status: 'PRESERVED' }
  component.watch['$route.query'].handler.call(state, state.$route.query)
  await Promise.resolve()
  old.resolve({ code: 0, data: { list: [{ studentId: 'suspended' }], total: 1 } })
  await pending
  assert.equal(state.pageTitle, '保留学籍')
  assert.equal(state.rows[0].studentId, 'preserved')
  state.reset()
  assert.equal(state.filters.status, 'PRESERVED')
})

test('the student entry opens the actual detail; suspended/preserved students use the resume form', () => {
  let target
  const { state } = page('AaRosterListView', {}, { $router: { push: route => { target = route } } })
  const student = { studentId: 'student-a', studentStatus: 'PRESERVED', enrolled: false }
  state.goDetail(student)
  assert.equal(target.name, 'aa-roster-detail')
  state.goChange(student)
  assert.equal(target.query.type, 'RESUME')
  assert.equal(target.query.studentId, 'student-a')
  target = null
  state.ctx.permissionPatterns = ['academicAffairs.roster.view']
  state.goChange(student)
  assert.equal(target, null)
})

test('a sensitive-field response from the previous student never appears in the next student file', async () => {
  const response = deferred()
  const { state } = page('AaRosterDetailView', {
    revealRosterSensitive: () => response.promise,
    getRosterDetail: async id => ({ code: 0, data: { studentId: id, statusHistory: [] } })
  })
  state.loading = false
  const pending = state.doReveal({ reason: '测试账号核对材料' })
  state.$route.params.studentId = 'student-b'
  await state.load()
  response.resolve({ code: 0, data: { idCard: 'previous-student-test-value' } })
  await pending
  assert.equal(state.detail.studentId, 'student-b')
  assert.equal(state.revealed, false)
  assert.equal(state.revealedIdCard, '')
})
