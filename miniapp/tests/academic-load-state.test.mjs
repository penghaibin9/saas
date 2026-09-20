import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as recovery from '../src/pages/teacher/academic-affairs/approval-recovery.js'
import * as writes from '../src/pages/teacher/academic-affairs/write-result.js'

const pages = [
  ['academic-affairs', 'getMySchedule', 'backToTeaching', 'back'],
  ['my-schedule', 'getMySchedule', 'backToSchedule'],
  ['exam-defer', 'getAcademicDeferPending', 'backToQueue'],
  ['academic-warning', 'getAcademicWarnings', 'backToWarnings']
]
const session = { identity: { tenantId: 'test-school', userId: 'test-teacher', activeContextId: 'ctx' }, currentRole: 'teacher' }
const denied = { code: 403001, httpStatus: 403, bizCode: 'NO_PERMISSION', message: '模块未购买或未授权：academicAffairs' }
const requestSource = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
const classification = requestSource.slice(requestSource.indexOf('export function isBusinessError'), requestSource.indexOf('/* ── 防刷屏'))
const normalizeError = new Function(classification.replace(/export /g, '') + '\nreturn normalizeError')()

test('read-state classification comes from the existing shared request module', () => {
  assert.equal(normalizeError(denied).pageState, 'noLicense')
})

function page(name, method, response) {
  const source = readFileSync(new URL(`../src/pages/teacher/${name}/index.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
  const backs = []
  const injected = { ...recovery, ...writes, normalizeError, teacherApi: { [method]: response }, useSessionStore: () => session, back: url => backs.push(url), navigateBack: url => backs.push(url), toast() {}, go() {} }
  const component = new Function(...Object.keys(injected), script)(...Object.values(injected))
  const vm = component.data()
  for (const [key, method] of Object.entries(component.methods)) vm[key] = method.bind(vm)
  for (const [key, getter] of Object.entries(component.computed || {})) Object.defineProperty(vm, key, { get: () => getter.call(vm) })
  Object.assign(vm, { _pageActive: true, _actionContext: vm.contextKey(), _viewContext: vm.contextKey() })
  return { vm, source, backs }
}

test('only an explicit module denial is noLicense; network/server failure stays retryable', () => {
  assert.equal(normalizeError(denied).pageState, 'noLicense')
  assert.equal(normalizeError({ ...denied, message: '不在当前数据范围' }).pageState, 'forbidden')
  assert.equal(normalizeError({ code: 'NETWORK', message: denied.message }).pageState, 'offline')
  assert.equal(normalizeError({ ...denied, httpStatus: 503 }).pageState, 'error')
})

for (const [name, method, guard, returnMethod = 'goBack'] of pages) {
  for (const [error, state] of [[denied, 'noLicense'], [{ ...denied, message: '无权查看' }, 'forbidden'], [{ code: 'NETWORK' }, 'offline']]) {
    test(`${name}: ${state} is distinct from empty success and has a usable return`, async () => {
      const { vm, source, backs } = page(name, method, async () => { throw error })
      Object.assign(vm, { list: [{ id: 'private' }], items: [{ id: 'private' }], todayItems: [{ id: 'private' }], detail: { id: 'private' } })
      await vm.load()
      assert.equal(vm.state, state)
      if (state === 'forbidden' || state === 'noLicense') {
        assert.ok(name === 'my-schedule' ? !vm.items?.length && !vm.todayItems.length : name === 'academic-affairs' ? !vm.scheduleItems.length && !vm.todayItems.length : !vm.list.length)
        if (name === 'academic-warning') assert.equal(vm.detail, null)
      }
      vm[returnMethod]()
      assert.deepEqual(backs, ['/pages/teacher/workbench/index'])
      assert.match(source, new RegExp(`@back="${returnMethod}"`))
    })
  }
  if (name !== 'academic-affairs') test(`${name}: returning respects its existing detail/write guard`, () => {
    const { vm, backs } = page(name, method, async () => ({}))
    vm[guard] = () => false
    vm.goBack()
    assert.deepEqual(backs, [])
  })
  test(`${name}: late denial cannot replace the state after leaving`, async () => {
    let reject
    const { vm } = page(name, method, () => new Promise((_resolve, fail) => { reject = fail }))
    const pending = vm.load()
    vm._pageActive = false
    vm.state = 'ready'
    reject(denied)
    await pending
    assert.equal(vm.state, 'ready')
  })
}
