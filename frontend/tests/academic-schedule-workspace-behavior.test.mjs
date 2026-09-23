import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

// Execute the page's actual Options API methods with controlled transport responses.
function page(name, dependencies = {}, globals = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const context = { dependencies, ...globals }
  vm.runInNewContext(script, context)
  return context.component
}

test('新建课表须明确学院或全校范围，学院编号按字符串传递', async () => {
  const writes = []
  const component = page('AaScheduleBatchListView', { academicAffairsApi: { createScheduleBatch: async body => { writes.push(body); return { code: 0 } } }, toast: { success() {}, error() {} } })
  const state = Object.assign(component.data(), component.methods, { ctx: {}, load: async () => {} })
  state.draft.termId = '52'
  await state.createBatch()
  assert.equal(writes.length, 0)
  state.draft.collegeId = '1000000000000000128'
  await state.createBatch()
  assert.equal(writes[0].collegeId, '1000000000000000128')
  state.draft = { termId: '52', scopeType: 'SCHOOL', collegeId: '128' }
  await state.createBatch()
  assert.equal(writes[1].collegeId, undefined)
})

test('已发布课表的补排入口精确携带原批次', () => {
  const component = page('AaScheduleBatchListView')
  let destination
  component.methods.openWorkbench.call({ $router: { push: route => { destination = route } } }, { batchId: '41' })
  assert.equal(destination.path, '/admin/academic-affairs/scheduling')
  assert.equal(destination.query.batchId, '41')
})

test('publication record failure remains an error; retry clears it after success', async () => {
  let response = { code: 403, message: '无查看发布记录权限' }
  const component = page('AaSchedulePublishView', {
    academicAffairsApi: { getSchedulePublishRecords: async () => response },
    readAllPages: async (loadPage) => loadPage(1, 200),
    isDeniedResult: (result) => Number(result?.status || result?.code) === 403
  })
  const state = Object.assign(component.data(), component.methods, { focusGate: { invalidate() {} } })
  await state.loadRecords()
  assert.equal(state.recError, '无查看发布记录权限')
  assert.equal(state.recLoading, false)
  response = { code: 0, data: { list: [{ recordId: 'record-1' }] } }
  await state.loadRecords()
  assert.equal(state.recError, '')
  assert.equal(state.records[0].recordId, 'record-1')
})

test('today transport failure keeps the weekly schedule usable without claiming no classes', async () => {
  const component = page('AaTeacherScheduleView', {
    currentUserFromToken: () => ({ loginName: 'teacher-1' }),
    academicAffairsApi: {
      getTeacherSchedule: async () => ({ code: 0, data: { items: [{ itemId: 'lesson-1' }] } }),
      getMyTeacherToday: async () => { throw new Error('今日课表暂不可用') }
    }
  })
  const state = Object.assign(component.data.call({ $route: { params: {} } }), component.methods, {
    teacherKey: 'teacher-1', isSelfView: true, $router: { replace: async () => {} }
  })
  await state.load()
  assert.equal(state.error, '')
  assert.equal(state.items[0].itemId, 'lesson-1')
  assert.equal(state.todayError, '今日课表暂不可用')
  assert.equal(state.loading, false)
})

test('今日课表权限拒绝不得伪装今天无课，正式周课表继续可用', async () => {
  const component = page('AaTeacherScheduleView', {
    currentUserFromToken: () => ({ loginName: 'teacher-1' }),
    academicAffairsApi: {
      getTeacherSchedule: async () => ({ code: 0, data: { items: [{ itemId: 'lesson-1' }] } }),
      getMyTeacherToday: async () => ({ code: 403, message: '无今日课表访问权限' })
    }
  })
  const state = Object.assign(component.data.call({ $route: { params: {} } }), component.methods, {
    teacherKey: 'teacher-1', isSelfView: true, $router: { replace: async () => {} }
  })
  await state.load()
  assert.equal(state.todayError, '无今日课表访问权限')
  assert.equal(state.items[0].itemId, 'lesson-1')
})

test('switching query while a response is pending cannot display the previous object', async () => {
  let resolve
  const response = new Promise((done) => { resolve = done })
  const component = page('AaScheduleViewsView', {
    academicAffairsApi: { getScheduleClassView: () => response }
  })
  const state = Object.assign(component.data(), component.methods, { query: 'class-a', batchId: 'batch-1' })
  const pending = state.loadView()
  state.query = 'class-b'
  state.resetView()
  resolve({ code: 0, data: { items: [{ itemId: 'class-a-lesson' }] } })
  await pending
  assert.equal(state.loadedQuery, '')
  assert.equal(state.items.length, 0)
  assert.equal(state.loading, false)
})

test('student print preserves student query type and calls the student view endpoint', async () => {
  let destination = null
  const view = page('AaScheduleViewsView')
  view.methods.printView.call({
    loading: false, error: '', loadedQuery: 'student-1', query: 'student-1', batchId: 'batch-1', tab: 'student',
    $router: { push: (target) => { destination = target } }
  })
  assert.equal(destination.path, '/admin/academic-affairs/print/schedule/batch-1')
  assert.equal(destination.query.type, 'student')
  assert.equal(destination.query.key, 'student-1')
  let studentCalls = 0
  const print = page('AaPrintScheduleView', { academicAffairsApi: {
    getContext: async () => ({ code: 0, data: { tenantBrandConfig: { schoolName: '测试学校' } } }),
    getTimeSlots: async () => ({ code: 0, data: [] }),
    getScheduleStudentView: async (batch, key) => {
      assert.equal(batch, 'batch-1'); assert.equal(key, 'student-1'); studentCalls++
      return { code: 0, data: { items: [] } }
    },
    getScheduleClassView: () => { throw new Error('Student query must not call class view') }
  } })
  const state = Object.assign(print.data(), { type: 'student', keyText: 'student-1', $route: { params: { batchId: 'batch-1' } } })
  await print.methods.load.call(state)
  assert.equal(studentCalls, 1)
  assert.equal(state.error, '')
})
