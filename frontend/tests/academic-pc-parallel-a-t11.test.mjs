import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const ok = data => ({ code: 0, data })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const allowedPreflight = (selectionCourseId, action = 'ENROLL') => ok({ selectionCourseId, action, allowed: true, allowedActions: ['VIEW', action === 'DROP' ? 'DROP' : 'ENROLL'] })

function mount(api, preflightStudentSelection) {
  const file = fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaSelectionStudentView.vue', import.meta.url), 'utf8')
  const script = file.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'return')
  const placeholders = ['ModulePageShell', 'DataTable', 'StatusTag', 'LoadingState', 'ErrorState', 'EmptyState', 'AppButton', 'AppConfirmDialog', 'AppInlineAlert', 'AppSectionCard']
  const factory = new Function('api', 'preflightStudentSelection', 'isDeniedResult', 'isConflictResult', ...placeholders, script)(
    api,
    preflightStudentSelection,
    result => String(result?.code || '').startsWith('403'),
    result => String(result?.code || '').startsWith('409'),
    ...placeholders.map(() => ({}))
  )
  const vm = { ...factory.data() }
  Object.entries(factory.methods).forEach(([name, fn]) => { vm[name] = fn.bind(vm) })
  Object.entries(factory.computed || {}).forEach(([name, fn]) => Object.defineProperty(vm, name, { get: () => fn.call(vm) }))
  return vm
}

const course = { selectionCourseId: 'C1', batchId: 'B1', courseCode: 'PLC01', courseName: 'PLC应用基础', status: 'OPEN', allowedActions: ['VIEW', 'ENROLL'] }

test('T11 action availability consumes server allowedActions and never guesses from remaining seats', () => {
  const vm = mount({}, async () => ok({}))
  assert.equal(vm.allows({ ...course, remain: 0 }, 'ENROLL'), true)
  assert.equal(vm.allows({ ...course, remain: 99, allowedActions: ['VIEW'] }, 'ENROLL'), false)
})

test('T11 enroll runs fresh preflight, one command and formal record reread', async () => {
  const calls = []
  const vm = mount({
    enroll: async id => { calls.push('POST:' + id); return ok({}) },
    mySelections: async id => { calls.push('RECORDS:' + id); return ok({ items: [{ ...course, recordId: 'R1', status: 'PENDING_LOTTERY' }] }) },
    studentCourses: async id => { calls.push('COURSES:' + id); return ok({ items: [{ batch: { batchId: id }, courses: [{ ...course, status: 'PENDING_LOTTERY', allowedActions: ['VIEW', 'DROP'] }] }] }) }
  }, async id => { calls.push('PREFLIGHT:' + id); return allowedPreflight(id) })
  await vm.prepare(course, 'ENROLL', 'B1')
  await vm.submitConfirmed()
  assert.deepEqual(calls, ['PREFLIGHT:C1', 'PREFLIGHT:C1', 'POST:C1', 'RECORDS:B1', 'COURSES:B1'])
  assert.equal(vm.receipt.status, 'PENDING_LOTTERY')
  assert.equal(vm.receipt.confirmed, true)
})

test('T11 uncertain enroll is never replayed and remains pending when formal record is unchanged', async () => {
  let writes = 0
  const vm = mount({
    enroll: async () => { writes += 1; return { code: 503001, message: '超时' } },
    mySelections: async () => ok({ items: [] }),
    studentCourses: async () => ok({ items: [{ batch: { batchId: 'B1' }, courses: [course] }] })
  }, async id => allowedPreflight(id))
  await vm.prepare(course, 'ENROLL', 'B1')
  await vm.submitConfirmed()
  await vm.prepare(course, 'ENROLL', 'B1')
  await vm.submitConfirmed()
  assert.equal(writes, 1)
  assert.equal(vm.pendingCommand.selectionCourseId, 'C1')
  assert.equal(vm.receipt.confirmed, false)
  assert.match(vm.notice.title, /待确认/)
})

test('T11 old preflight cannot replace the currently selected course', async () => {
  const first = deferred()
  const vm = mount({}, id => id === 'C1' ? first.promise : Promise.resolve(allowedPreflight(id)))
  const old = vm.prepare(course, 'ENROLL', 'B1')
  await vm.prepare({ ...course, selectionCourseId: 'C2', courseName: '工业机器人编程' }, 'ENROLL', 'B1')
  first.resolve(ok({ selectionCourseId: 'C1', action: 'ENROLL', allowed: false, allowedActions: ['VIEW'], reason: '旧课程阻断' })); await old
  assert.equal(vm.confirm.row.selectionCourseId, 'C2')
  assert.equal(vm.confirm.preflight.ready, true)
})

test('T11 denied reload clears stale courses, records and receipt', async () => {
  const vm = mount({ studentCourses: async () => ({ code: 403001, message: '无权访问' }), mySelections: async () => ok({ items: [] }) }, async () => ok({}))
  vm.groups = [{ sensitive: true }]; vm.mine = [{ sensitive: true }]; vm.receipt = { sensitive: true }
  await vm.load()
  assert.deepEqual(vm.groups, [])
  assert.deepEqual(vm.mine, [])
  assert.equal(vm.receipt, null)
  assert.match(vm.error, /已清除/)
})

test('T11 admin course and roster tables use server pagination and keyword filtering', () => {
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaSelectionConsoleView.vue', import.meta.url), 'utf8')
  assert.match(source, /listAllTasks\(\{[\s\S]*termId,[\s\S]*status: 'READY',[\s\S]*keyword:[\s\S]*pageSize: 50/)
  assert.doesNotMatch(source, /listAllTasks\(\{ status: 'READY', page: 1, pageSize: 500 \}\)/)
  assert.match(source, /listCourses\(batchId, \{ page: this\.coursePagination\.page, pageSize: this\.coursePagination\.pageSize \}\)/)
  assert.match(source, /courseRoster\(this\.rosterCourse\.selectionCourseId, \{[\s\S]*page: this\.rosterPagination\.page,[\s\S]*pageSize: this\.rosterPagination\.pageSize/)
  assert.match(source, /@change="onBatchPage"/)
  assert.match(source, /@change="onCoursePage"/)
  assert.match(source, /@change="onRosterPage"/)
})
