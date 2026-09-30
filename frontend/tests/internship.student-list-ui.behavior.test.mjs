import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import * as constants from '../src/modules/internship/constants/internship-student.constants.js'

const file = new URL('../src/modules/internship/views/InternshipStudentListView.vue', import.meta.url)
const { descriptor } = parse(fs.readFileSync(file, 'utf8'))
const script = descriptor.script.content.replace(/^import[\s\S]*?from\s*['"][^'"]+['"]\s*$/gm, '').replace(/components:\s*\{[^}]*\},/, 'components: {},').replace('export default', 'return')
const ok = data => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function setup(api = {}) {
  const store = { selectedBatchId: '23', canWriteStudents: true, withBatchQuery(q) { return { ...q, batchId: this.selectedBatchId } } }
  const feedback = [], routes = []
  const bindings = { ...constants, internStudentApi: api, useInternshipBatchStore: () => store, canCode: (ctx, code) => ctx.permissionPatterns?.includes(code), toast: { success: x => feedback.push(x), error: x => feedback.push(x) } }
  const def = new Function(...Object.keys(bindings), script)(...Object.values(bindings))
  const vm = { ...def.data(), ctx: { permissionPatterns: ['internship.student.view', 'internship.student.manage', 'internship.student.export', 'internship.student.eligibility.review'] },
    $route: { path: '/admin/internship/students', fullPath: '/admin/internship/students?batchId=23&panel=roster&page=3', query: { batchId: '23', panel: 'roster', page: '3' } },
    $router: { resolve: t => ({ fullPath: t.path + '?' + new URLSearchParams(t.query).toString() }), push: t => routes.push(t), replace: t => routes.push(t) } }
  for (const [key, method] of Object.entries(def.methods)) vm[key] = method.bind(vm)
  for (const [key, method] of Object.entries(def.computed)) Object.defineProperty(vm, key, { get: () => method.call(vm) })
  return { vm, def, store, routes, feedback }
}

test('student list template compiles with accessible filter labels and preserved form workspaces', () => {
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: String(file), id: 'student-list' }).errors, [])
})

test('route restoration overrides queue presets and keeps exact batch and student IDs', () => {
  const { vm, store } = setup(); vm.load = () => {}
  store.selectedBatchId = '9007199254740999'
  vm.$route.query = { panel: 'eligibility', eligibility: '', keyword: '测试', page: '3' }; vm.applyRouteFilters()
  assert.equal(vm.appliedFilters.eligibility, ''); assert.equal(vm.page, 3); assert.equal(vm.pageTitle, '实习资格审核')
  const target = vm.studentLocation({ id: '9007199254740998', batchId: store.selectedBatchId })
  assert.equal(target.path, '/admin/internship/students/9007199254740998'); assert.equal(target.query.batchId, store.selectedBatchId)
  assert.equal(target.query.returnTo, vm.$route.fullPath)
})

test('unsubmitted filters cannot silently change pagination, list refresh or export', async () => {
  let read, exported
  const { vm, routes } = setup({ getStudents: async p => { read = p; return ok({ list: [], total: 0 }) }, exportStudents: async p => { exported = p; return ok({}) } })
  vm.appliedFilters = { keyword: '已查询', status: '', eligibility: 'PENDING', destination: '', hasPosition: 'false' }
  vm.filters = { ...vm.appliedFilters, keyword: '尚未查询', hasPosition: 'true' }
  vm.turnPage(2); assert.equal(routes[0].query.keyword, '已查询')
  await vm.load(); await vm.exportFn(); assert.equal(read.keyword, '已查询'); assert.equal(read.hasPosition, false); assert.equal(exported.hasPosition, false)
  vm.search(); assert.equal(routes[1].query.keyword, '尚未查询'); assert.equal(routes[1].query.page, '1')
})

test('mentor view explains its scope and name while read-only roles keep viewing without write actions', () => {
  const { vm } = setup(); vm.activePanel = 'mentor'
  assert.equal(vm.pageTitle, '导师分配'); assert.match(vm.pageSubtitle, /指导关系/)
  vm.ctx.permissionPatterns = ['internship.student.view']
  assert.deepEqual(vm.rowActions({ status: 'PREPARING' }), [{ key: 'detail', label: '档案' }])
  assert.equal(vm.canExport, false)
})

test('read guards do not query without batch or view permission and failures clear stale records', async () => {
  let calls = 0
  const { vm, store } = setup({ getStudents: async () => { calls++; throw new Error('网络暂不可用') } })
  store.selectedBatchId = ''; await vm.load(); assert.equal(calls, 0)
  store.selectedBatchId = '23'; vm.ctx.permissionPatterns = []; await vm.load(); assert.equal(calls, 0); assert.match(vm.error, /权限/)
  vm.ctx.permissionPatterns = ['internship.student.view']; vm.rows = [{ id: 'old' }]; vm.total = 8; await vm.load()
  assert.equal(vm.error, '网络暂不可用'); assert.deepEqual(vm.rows, []); assert.equal(vm.total, 0); assert.equal(vm.loading, false)
})

test('late reads and exports cannot reappear after a scope reset', async () => {
  const pending = deferred(), exportResult = deferred()
  const { vm } = setup({ getStudents: () => pending.promise, exportStudents: () => exportResult.promise })
  const read = vm.load(), exporting = vm.exportFn(); vm.resetScope()
  pending.resolve(ok({ list: [{ id: 'old' }], total: 1 })); exportResult.resolve(ok({ filename: 'old.xlsx' }))
  await read; assert.deepEqual(vm.rows, []); assert.notEqual((await exporting).code, 0)
})

test('student creation submits once, uses the current batch and opens qualification only after success', async () => {
  const pending = deferred(); let calls = 0, body
  const { vm, routes } = setup({ createStudent: p => { body = p; calls++; return pending.promise } })
  vm.cform = { studentId: '9007199254740998', advisorUserId: '', remark: '测试草稿' }
  const first = vm.submitCreate(); await vm.submitCreate(); assert.equal(calls, 1); assert.equal(body.batchId, '23'); assert.equal(body.advisorUserId, null)
  pending.resolve(ok({ id: '31', batchId: '23' })); await first
  assert.equal(routes[0].query.section, 'eligibility'); assert.equal(routes[0].path, '/admin/internship/students/31'); assert.equal(vm.submitting, false)
})

test('creation failure preserves fields and a late success cannot navigate to an old scope', async () => {
  const { vm } = setup({ createStudent: async () => ({ code: 409, message: '已建档' }) })
  vm.cform.studentId = '9'; vm.cform.remark = '保留'; await vm.submitCreate(); assert.equal(vm.cform.remark, '保留'); assert.equal(vm.cError, '已建档')
  const pending = deferred(), next = setup({ createStudent: () => pending.promise })
  next.vm.cform.studentId = '9'; const create = next.vm.submitCreate(); next.vm.resetScope(); pending.resolve(ok({ id: '31', batchId: '23' })); await create
  assert.deepEqual(next.routes, []); assert.equal(next.vm.cform.studentId, '')
})

test('advisor reassignment snapshots version and preserves the draft on conflict without replay', async () => {
  let sent, calls = 0
  const { vm } = setup({ assignAdvisor: async (...args) => { sent = args; calls++; return { code: 'DATA_CONFLICT', message: '版本已更新' } } })
  const row = { id: '31', name: '虚构学生', status: 'PREPARING', advisorName: '原导师', version: 4 }
  await vm.openAssignAdvisor(row); row.version = 5
  vm.advisorAssignmentUserId = '9007199254740998'; vm.advisorAssignmentReason = '交接说明'
  await vm.submitAssignAdvisor(); await vm.submitAssignAdvisor()
  assert.equal(calls, 1); assert.equal(sent[1].expectedVersion, 4); assert.equal(sent[1].advisorUserId, '9007199254740998')
  assert.equal(vm.advisorConflict, true); assert.equal(vm.advisorAssignmentReason, '交接说明'); assert.equal(vm.advisorVisible, true)
})

test('advisor write refuses lost rights and archived records; late success cannot close a new workspace', async () => {
  const pending = deferred(); let calls = 0
  const { vm } = setup({ assignAdvisor: () => { calls++; return pending.promise } })
  vm.advisorRow = { id: '31', status: 'ARCHIVED', version: 4 }; vm.advisorAssignmentUserId = '8'; await vm.submitAssignAdvisor(); assert.equal(calls, 0)
  vm.advisorRow.status = 'PREPARING'; vm.ctx.permissionPatterns = []; await vm.submitAssignAdvisor(); assert.equal(calls, 0)
  vm.ctx.permissionPatterns = ['internship.student.manage']; const write = vm.submitAssignAdvisor(); vm.resetScope(); vm.advisorVisible = true
  pending.resolve(ok({})); await write; assert.equal(vm.advisorVisible, true)
})

test('keeping the same advisor avoids a needless conflict request', async () => {
  const { vm } = setup({ assignAdvisor: () => assert.fail('unchanged assignment must not submit') })
  await vm.openAssignAdvisor({ id: '31', status: 'PREPARING', advisorUserId: '9007199254740999', version: 4 })
  assert.equal(vm.advisorUnchanged, true); await vm.submitAssignAdvisor()
  assert.equal(vm.submitting, false); assert.equal(vm.advisorError, '')
})

test('mentor default includes students without a position and puts assignment first', () => {
  const { vm } = setup(); vm.load = () => {}
  vm.$route.query = { panel: 'mentor' }; vm.applyRouteFilters()
  assert.equal(vm.appliedFilters.hasPosition, ''); assert.equal('hasPosition' in vm.queryParams(), false)
  assert.deepEqual(vm.rowActions({ id: '31', status: 'PREPARING' }), [{ key: 'assignAdvisor', label: '分配导师' }, { key: 'detail', label: '档案' }])
  assert.deepEqual(vm.toolbarActions.map(x => x.key), ['roster'])
  vm.$route.query.hasPosition = 'true'; vm.applyRouteFilters(); assert.equal(vm.queryParams().hasPosition, true)
})

test('advisor deep links restore the exact student and return without losing the list query', async () => {
  const row = { id: '9007199254740998', batchId: '23', name: '虚构学生', status: 'PREPARING', advisorUserId: '9', version: 7 }
  const { vm, routes } = setup({ getStudentDetail: async id => { assert.equal(id, row.id); return ok(row) } })
  vm.$route.query = { batchId: '23', panel: 'mentor', keyword: '虚构', page: '3' }
  vm.onRowAction('assignAdvisor', row)
  assert.deepEqual(routes[0].query, { ...vm.$route.query, advisorId: row.id })
  vm.$route.query = routes[0].query; await vm.restoreAdvisor()
  assert.equal(vm.advisorRow.version, 7); assert.equal(vm.advisorAssignmentUserId, '9'); assert.equal(vm.advisorVisible, true)
  vm.closeAdvisor(); assert.equal(vm.advisorVisible, false)
  assert.deepEqual(routes.at(-1).query, { batchId: '23', panel: 'mentor', keyword: '虚构', page: '3' })
})

test('advisor deep links reject another batch, archived records, and insufficient permissions', async () => {
  let data = { id: '31', batchId: '24', status: 'PREPARING' }, calls = 0
  const { vm } = setup({ getStudentDetail: async () => { calls++; return ok(data) } })
  vm.$route.query.advisorId = '31'; await vm.restoreAdvisor(); assert.match(vm.advisorLoadError, /不属于当前批次/); assert.equal(vm.advisorRow, null)
  data = { ...data, batchId: '23', status: 'ARCHIVED' }; await vm.restoreAdvisor(); assert.match(vm.advisorLoadError, /已归档/)
  vm.ctx.permissionPatterns = ['internship.student.view']; await vm.restoreAdvisor(); assert.equal(calls, 2); assert.match(vm.advisorLoadError, /无权/)
})

test('failed advisor detail retries and late responses cannot replace a new student', async () => {
  const old = deferred(); let fail = true
  const { vm } = setup({ getStudentDetail: async id => {
    if (id === '31') return old.promise
    if (fail) throw new Error('连接暂不可用')
    return ok({ id, batchId: '23', status: 'PREPARING', version: 3 })
  } })
  vm.$route.query.advisorId = '31'; const pending = vm.restoreAdvisor()
  vm.$route.query.advisorId = '32'; await vm.restoreAdvisor(); assert.equal(vm.advisorLoadError, '连接暂不可用'); assert.equal(vm.advisorLoading, false)
  fail = false; await vm.restoreAdvisor()
  old.resolve(ok({ id: '31', batchId: '23', status: 'PREPARING', version: 1 })); await pending
  assert.equal(vm.advisorRow.id, '32'); assert.equal(vm.advisorLoadError, '')
})

test('successful advisor assignment closes the deep link and refreshes the original filtered list', async () => {
  let refreshed = 0
  const { vm, routes } = setup({ assignAdvisor: async () => ok({ id: '31', advisorUserId: '8', version: 5 }) })
  vm.$route.query = { batchId: '23', panel: 'mentor', keyword: '虚构', page: '3', advisorId: '31' }
  await vm.openAssignAdvisor({ id: '31', status: 'PREPARING', advisorUserId: '9', version: 4 })
  vm.advisorAssignmentUserId = '8'; vm.load = () => { refreshed++ }
  await vm.submitAssignAdvisor()
  assert.equal(vm.submitting, false); assert.equal(vm.advisorVisible, false); assert.equal(refreshed, 1)
  assert.deepEqual(routes.at(-1).query, { batchId: '23', panel: 'mentor', keyword: '虚构', page: '3' })
})

test('browser return during an advisor write releases the old busy state and ignores its late result', async () => {
  const pending = deferred(), { vm, routes } = setup({ assignAdvisor: () => pending.promise })
  vm.$route.query.advisorId = '31'
  await vm.openAssignAdvisor({ id: '31', status: 'PREPARING', advisorUserId: '9', version: 4 })
  vm.advisorAssignmentUserId = '8'; const write = vm.submitAssignAdvisor()
  assert.equal(vm.submitting, true)
  delete vm.$route.query.advisorId; await vm.restoreAdvisor()
  assert.equal(vm.submitting, false); assert.equal(vm.advisorVisible, false)
  pending.resolve(ok({ id: '31' })); await write
  assert.equal(vm.advisorVisible, false); assert.deepEqual(routes, [])
})
