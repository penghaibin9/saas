import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'

function page(api = {}, catalog = {}) {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaClassroomListView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { matchPermission, academicAffairsApi: api, classroomCatalogApi: catalog }, window: { confirm: () => true } }
  vm.runInNewContext(script, sandbox)
  const c = sandbox.component
  const state = { ctx: { permissionPatterns: ['academicAffairs.classroom.*'] }, $route: { query: {} }, $refs: {}, $el: { querySelector: () => null }, $nextTick: action => action() }
  state.$router = { replace: async route => { state.$route.query = route.query }, push() {} }
  Object.assign(state, c.data.call(state), c.methods)
  for (const [key, getter] of Object.entries(c.computed)) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return { state, component: c }
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('building and explicit unknown-floor filters survive refresh; reset keeps the selected building', async () => {
  const { state } = page()
  state.$route.query = { buildingId: '9007199254740999', floorNo: '0', page: '3', keyword: '0101' }
  state.restoreFilters()
  assert.equal(state.filters.buildingId, '9007199254740999')
  assert.equal(state.filters.floorNo, '0')
  assert.equal(state.pagination.page, 3)
  await state.reset()
  assert.equal(state.$route.query.buildingId, '9007199254740999')
  assert.equal(state.$route.query.keyword, undefined)
  assert.equal(state.$route.query.floorNo, undefined)
})

test('late room-list response does not overwrite a newly selected building', async () => {
  const old = deferred()
  const { state } = page({ listClassrooms: params => params.buildingId === 'old' ? old.promise : Promise.resolve({ code: 0, data: { items: [{ classroomId: 'new-room' }], total: 1 } }) })
  state.filters.buildingId = 'old'
  const pending = state.load()
  state.filters.buildingId = 'new'
  await state.load()
  old.resolve({ code: 0, data: { items: [{ classroomId: 'old-room' }], total: 1 } })
  await pending
  assert.equal(state.rows[0].classroomId, 'new-room')
})

test('room-list failure stays an error and never displays a stale room as current', async () => {
  const { state } = page({ listClassrooms: async () => ({ code: 503, message: '教室服务暂不可用' }) })
  state.rows = [{ classroomId: 'old-room' }]
  await state.load()
  assert.equal(state.rows.length, 0)
  assert.equal(state.error, '教室服务暂不可用')
})

test('individual edit retains input and expected version after conflict', async () => {
  let sent
  const { state } = page({ updateClassroom: async (id, body) => { sent = { id, body }; return { code: 409, message: '资料已变化' } } })
  state.openEdit({ classroomId: '9007199254740999', buildingCode: 'A', buildingName: '教学楼', roomCode: '0101', capacity: 60, version: 7 })
  state.form.capacity = 80
  await state.submitForm()
  assert.equal(sent.id, '9007199254740999')
  assert.equal(sent.body.expectedVersion, 7)
  assert.equal(state.form.capacity, 80)
  assert.equal(state.form.roomCode, '0101')
  assert.equal(state.formVisible, true)
  assert.equal(state.formError, '资料已变化')
})

test('single-room creation inherits location, not the building aggregate capacity', () => {
  const { state } = page()
  state.openCreate({ buildingId: '1', buildingCode: 'A', buildingName: '教学楼', capacity: 12000, campusCode: '主校区' })
  assert.equal(state.form.buildingId, '1')
  assert.equal(state.form.capacity, 0)
  assert.equal(state.form.campusCode, '主校区')
  state.ctx.permissionPatterns = ['academicAffairs.classroom.view']
  state.openBatch('import')
  assert.equal(state.batchMode, '')
})
