import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function page(path, dependencies) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
  const sandbox = { ...dependencies, toastError() {}, decodeQueryText: value => value, go() {}, TEACHER_STUDENT_PAGE_SIZE: 20 }
  vm.runInNewContext(script, sandbox)
  return { definition: sandbox.component, state: Object.assign(sandbox.component.data(), sandbox.component.methods) }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('student profile refresh does not accept data from before hiding or a newer refresh', async () => {
  const first = deferred(), second = deferred()
  let count = 0
  const { state, definition } = page('../src/pages/student/profile/index.vue', { studentApi: { getProfile: () => ++count === 1 ? first.promise : second.promise } })
  const old = state.load()
  definition.onHide.call(state)
  const current = state.load()
  second.resolve({ org: { className: '新班级' } })
  await current
  first.resolve({ org: { className: '旧班级' } })
  await old
  assert.equal(state.p.org.className, '新班级')
  assert.equal(state.state, 'ready')
  assert.equal(state.studentStatusText('PRESERVED'), '保留学籍')
  assert.equal(state.studentStatusText('COMPLETED'), '结业')
})

test('student profile distinguishes a real empty response and a failed read', async () => {
  let fail = false
  const { state } = page('../src/pages/student/profile/index.vue', { studentApi: { getProfile: async () => { if (fail) throw Error('offline'); return { _empty: true } } } })
  await state.load()
  assert.equal(state.state, 'empty')
  assert.equal(state.p, null)
  fail = true
  await state.load()
  assert.equal(state.state, 'error')
})

test('teacher roster refresh discards an older page append after student membership changes', async () => {
  const append = deferred()
  const { state } = page('../src/pages/teacher/my-students/index.vue', { teacherStudentV3Api: { list: async params => params.cursor ? append.promise : { items: [{ studentId: 'new-student' }], total: 1, hasMore: false } } })
  state.items = [{ studentId: 'transferred-student' }]; state.hasMore = true; state.nextCursor = 'old-cursor'
  const old = state.loadMore()
  await state.reload()
  append.resolve({ items: [{ studentId: 'late-student' }], total: 200, hasMore: true, nextCursor: 'late-cursor' })
  await old
  assert.equal(state.items.length, 1)
  assert.equal(state.items[0].studentId, 'new-student')
  assert.equal(state.total, 1)
  assert.equal(state.hasMore, false)
})
