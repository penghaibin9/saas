import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

function componentFor(studentApi) {
  const source = fs.readFileSync(new URL('../src/pages/student/weekly-report/index.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[^\n]+\n/gm, '')
    .replace('export default', 'return')
  return new Function('studentApi', 'normalizeError', 'toast', script)(studentApi, (error) => ({ text: error?.message || '失败' }), () => {})
}

function bind(component) {
  const vm = { ...component.data() }
  for (const [name, method] of Object.entries(component.methods)) vm[name] = (...args) => method.apply(vm, args)
  for (const [name, getter] of Object.entries(component.computed)) {
    Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  }
  return vm
}

test('student weekly report uses bounded pages and resolves a message focus with only one extra page', async () => {
  const calls = []
  const api = {
    getInternship: async () => ({
      company: '测试企业', post: '测试岗位', schoolMentor: '指导老师', batchId: '7', recordId: '19',
      weekly: { week: '第 9 周', lastFeedback: '' }
    }),
    getInternshipWeeklyReports: async (...args) => {
      calls.push(args)
      const page = args[2]
      if (page === 1) return {
        page: 1, pageSize: 20, total: 60, hasMore: true, focusPage: 2,
        items: [{ id: 'current', week: 9, status: 'PENDING_REVIEW' }]
      }
      if (page === 2) return {
        page: 2, pageSize: 20, total: 60, hasMore: true,
        items: [{ id: 'returned', week: 1, status: 'RETURNED', reviewComment: '请补全实习周报内容' }]
      }
      return { page: 3, pageSize: 20, total: 60, hasMore: false, items: [{ id: 'history', week: 2, status: 'APPROVED' }] }
    }
  }
  const component = componentFor(api)
  const vm = bind(component)
  vm.focusReportId = 'returned'
  vm.focusWeek = 1

  await vm.load()
  assert.deepEqual(calls[0], ['7', '19', 1, 20, 'returned'])
  assert.deepEqual(calls[1], ['7', '19', 2, 20])
  assert.equal(vm.selectedWeek, 1)
  assert.equal(vm.selectedReport.id, 'returned')
  assert.deepEqual(vm.loadedWeeklyPages, [1, 2])
  assert.equal(vm.hasMore, true)

  await vm.loadMore()
  assert.deepEqual(calls[2], ['7', '19', 3, 20])
  assert.deepEqual(vm.loadedWeeklyPages, [1, 2, 3])
  assert.equal(vm.hasMore, false)
})

test('weekly report page consumes the registered message focus parameters instead of opening a generic list', () => {
  const source = fs.readFileSync(new URL('../src/pages/student/weekly-report/index.vue', import.meta.url), 'utf8')
  assert.match(source, /onLoad\(options = \{\}\)/)
  assert.match(source, /options\.reportId/)
  assert.match(source, /options\.weekNo/)
  assert.match(source, /focusPage/)
  assert.match(source, /onReachBottom\(\) \{ this\.loadMore\(\) \}/)
})
