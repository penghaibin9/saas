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

test('publication record failure remains an error; retry clears it after success', async () => {
  let response = { code: 403, message: '无查看发布记录权限' }
  const component = page('AaSchedulePublishView', {
    academicAffairsApi: { getSchedulePublishRecords: async () => response }
  })
  const state = component.data()
  await component.methods.loadRecords.call(state)
  assert.equal(state.recError, '无查看发布记录权限')
  assert.equal(state.recLoading, false)
  response = { code: 0, data: { list: [{ recordId: 'record-1' }] } }
  await component.methods.loadRecords.call(state)
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
  let opened = ''
  const view = page('AaScheduleViewsView', {}, { window: { open: (url) => { opened = url } } })
  view.methods.printView.call({ loading: false, error: '', loadedQuery: 'student-1', query: 'student-1', batchId: 'batch-1', tab: 'student' })
  assert.match(opened, /type=student&key=student-1$/)
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
