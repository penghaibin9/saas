import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

function mount(get) {
  const generation = { value: 1 }
  const context = vm.createContext({ teacherStudent360V3Api: { get }, currentSessionGeneration: () => generation.value,
    normalizeError: e => ({ kind: e.kind, pageState: e.kind || 'error' }), toast() {} })
  const presentation = readFileSync(new URL('../src/services/student360Presentation.js', import.meta.url), 'utf8').replace(/export const /g, 'const ')
  vm.runInContext(presentation, context)
  const source = readFileSync(new URL('../src/pages/teacher/student-detail/index.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
  vm.runInContext(source, context)
  const component = context.component
  const page = component.data()
  for (const [name, fn] of Object.entries(component.methods)) page[name] = fn.bind(page)
  page.id = '100'
  return { page, component, generation }
}

test('学生详情状态与风险只显示中文，未知机器值不回显', () => {
  const { page, component } = mount(async () => null)
  assert.equal(page.studentStatusText('ACTIVE'), '在读')
  assert.equal(page.studentStatusText('UNKNOWN_CODE'), '状态待确认')
  assert.equal(page.stageText('UNKNOWN_STAGE'), '阶段待确认')
  assert.equal(page.statusText('UNKNOWN_DISCIPLINE'), '处分状态待确认')
  page.s = { risk: { warningCount: 2, internshipRisk: 'HIGH', affairsRisk: 'NEW_RISK' } }
  assert.equal(component.computed.riskDescription.call(page), '2 条学业预警 · 实习风险：高 · 学工风险：风险待确认')
})

test('学生详情拒绝旧学生、旧账号和页面卸载后的迟到数据', async () => {
  for (const scenario of ['student', 'account', 'unload']) {
    let resolve
    const { page, component, generation } = mount(() => new Promise(r => { resolve = r }))
    page.s = { base: { name: '旧测试学生' } }
    const pending = page.load()
    assert.equal(page.s, null)
    if (scenario === 'student') page.id = '200'
    if (scenario === 'account') generation.value++
    if (scenario === 'unload') component.onUnload.call(page)
    resolve({ hasData: true, studentId: '100' })
    await pending
    assert.equal(page.s, null)
  }
})

test('旧请求失败不覆盖新学生，撤权后清空旧详情并显示无权限', async () => {
  let rejectOld, calls = 0
  const { page } = mount(() => ++calls === 1 ? new Promise((_r, reject) => { rejectOld = reject }) : Promise.resolve({ hasData: true, studentId: '200' }))
  const old = page.load()
  page.id = '200'
  await page.load()
  rejectOld({ kind: 'forbidden' })
  await old
  assert.equal(page.s.studentId, '200')
  assert.equal(page.state, 'ready')
  const denied = mount(async () => { throw { kind: 'forbidden' } }).page
  denied.s = { studentId: '100' }
  await denied.load()
  assert.equal(denied.s, null)
  assert.equal(denied.state, 'forbidden')
})
