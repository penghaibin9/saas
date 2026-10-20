import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const real = readFileSync(new URL('../src/services/realApi.js', import.meta.url), 'utf8')
const body = real.slice(real.indexOf('export async function enrichCampusService()'), real.indexOf('/* 教师端·移动聚合兼容导出 */'))
const factory = new Function('realRequest', body.replace('export async function', 'return async function'))
test('full directory is independent of home recommendations and preserves server actions', async () => {
  const action = { target: { path: '/pages/student/affairs/funding' }, allowedActions: ['OPEN'] }
  const paths = []
  const load = factory(async path => { paths.push(path); return { categories: [{ key: 'studentAffairs', label: '学工中心', action }], items: [{ id: 'FUNDING', cat: 'studentAffairs', name: '奖助申请', action }] } })
  const directory = await load()
  assert.deepEqual(paths, ['/mobile/student/services'])
  assert.equal(directory.items[0].action, action)
  assert.equal(directory.items[0].name, '奖助申请')
  assert.equal(directory.categories[0].key, directory.items[0].cat)
})
test('missing directory contract fails instead of showing blank successful page', async () => {
  await assert.rejects(factory(async () => ({ hasData: true, workOrders: [] }))(), /服务目录数据格式异常/)
})
test('service click retains exact business action rather than inferring an application type from its name', () => {
  const source = readFileSync(new URL('../src/pages/student/campus-service/index.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
  const calls = []
  const component = new Function('runAction', 'go', script)((...args) => calls.push(args), () => {})
  const action = { target: { path: '/pages/student/affairs/aid' } }
  component.methods.apply({ name: '任意显示名称', action })
  assert.deepEqual(calls, [[action, { side: 'student' }]])
})

function mount(api = {}, generation = () => 1) {
  const source = readFileSync(new URL('../src/pages/student/campus-service/index.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
  const component = new Function('studentApi', 'currentSessionGeneration', 'go', script)(api, generation, () => {})
  const vm = { ...component.data(), ...component.methods }
  return { vm, component }
}

test('category selection and cross-domain search operate on bounded navigation metadata', () => {
  const { vm, component } = mount()
  vm.data = { categories: [{ key: 'academicAffairs' }], items: [
    { name: '我的请假', cat: 'studentAffairs', group: '日常事务', desc: '学工中心' },
    { name: '考试与缓考', cat: 'academicAffairs', group: '课表与考试', desc: '教务中心' },
  ] }
  vm.keyword = '请假'
  vm.selectCategory('academicAffairs')
  assert.equal(vm.keyword, '')
  assert.equal(component.computed.groups.call(vm)[0].items[0].name, '考试与缓考')
  vm.keyword = '请假'
  assert.equal(component.computed.searchResult.call(vm)[0].cat, 'studentAffairs')
})

test('late directory responses cannot cross login sessions or disposed pages', async () => {
  for (const mode of ['session', 'unload']) {
    let resolve, session = 1
    const { vm, component } = mount({ getServices: () => new Promise(r => { resolve = r }) }, () => session)
    const pending = vm.load()
    if (mode === 'session') session++
    else component.onUnload.call(vm)
    resolve({ categories: [{ key: 'studentAffairs' }], items: [{ name: '旧学校菜单' }] })
    await pending
    assert.equal(vm.data, null)
  }
})

test('authorization network failure renders error, not empty success', async () => {
  const { vm } = mount({ getServices: async () => { throw Error('offline') } })
  await vm.load()
  assert.equal(vm.state, 'error')
  assert.equal(vm.data, null)
})
