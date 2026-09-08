import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

// Exercise the actual view's state transitions with isolated API responses.
const source = readFileSync(new URL('../src/modules/studentAffairs/views/dorm/DormResourceView.vue', import.meta.url), 'utf8')
function createView(api = {}) {
  const names = []
  const script = parse(source).descriptor.script.content.replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, imports) => {
    names.push(...imports.split(',').map(x => x.trim()))
    return ''
  }).replace('export default', 'return')
  const component = new Function(...names, script)(...names.map(name => name === 'studentAffairsApi' ? api : name === 'canCode' ? () => true : {}))
  const view = component.data()
  for (const [key, method] of Object.entries(component.methods)) view[key] = method.bind(view)
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(view, key, { get: getter.bind(view) })
  return view
}

test('only enabled vacant beds open ordinary check-in; reserved and occupied beds show details', () => {
  const view = createView()
  view.rooms = [{ roomId: 'r', roomNo: '101', status: 'ENABLED' }]
  view.curRoom = 'r'
  view.openBedAction({ bedId: '1', bedNo: '1', status: 'LOCKED' })
  assert.equal(view.inDlg.visible, false)
  assert.equal(view.bedDlg.visible, true)
  assert.equal(view.bedStatusLabel('LOCKED'), '预留 / 锁定')
  view.openBedAction({ bedId: '2', bedNo: '2', status: 'VACANT' })
  assert.equal(view.inDlg.bedId, '2')
  assert.equal(view.inDlg.visible, true)
  view.inDlg.visible = false
  view.rooms[0].status = 'MAINTENANCE'
  view.openBedAction({ bedId: '3', status: 'VACANT' })
  assert.equal(view.inDlg.visible, false)
  view.rooms[0].status = 'ENABLED'
  view.canBtn = () => false
  view.openBedAction({ bedId: '3', status: 'VACANT' })
  assert.equal(view.inDlg.visible, false)
})

test('late room-bed responses never overwrite the newly selected room', async () => {
  const pending = {}
  const view = createView({ listDormBeds: id => new Promise(resolve => { pending[id] = resolve }) })
  const first = view.openRoom({ roomId: 'a', roomNo: '101' })
  const second = view.openRoom({ roomId: 'b', roomNo: '102' })
  pending.b({ data: { items: [{ bedId: 'b-bed' }] } })
  await second
  pending.a({ data: { items: [{ bedId: 'a-bed' }] } })
  await first
  assert.equal(view.curRoom, 'b')
  assert.deepEqual(view.beds, [{ bedId: 'b-bed' }])
  assert.equal(view.bedsLoading, false)
})

test('ordinary check-in validates a student and keeps the form on authoritative conflicts', async () => {
  let calls = 0
  const view = createView({ dormCheckin: async () => { calls++; throw new Error('该学生已有床位，请通过正式调宿流程变更') } })
  view.inDlg = { visible: true, bedId: 'b', studentId: '', label: '101 / 1', error: '' }
  await view.submitVisualCheckin()
  assert.equal(calls, 0)
  view.inDlg.studentId = 's'
  await view.submitVisualCheckin()
  assert.equal(calls, 1)
  assert.equal(view.inDlg.visible, true)
  assert.match(view.inDlg.error, /正式调宿/)
  assert.equal(view.successMessage, '')
  assert.equal(view.actioning, false)
})

test('successful check-in sends exact IDs and refreshes authoritative room state', async () => {
  let input, refreshed = 0
  const view = createView({ dormCheckin: async (...args) => { input = args } })
  view.load = async () => { refreshed++ }
  view.inDlg = { visible: true, bedId: 'bed-12', studentId: 'student-8', label: '东苑 / 101 / 2', error: '' }
  await view.submitVisualCheckin()
  assert.deepEqual(input, ['bed-12', 'student-8'])
  assert.equal(refreshed, 1)
  assert.equal(view.inDlg.visible, false)
  assert.match(view.successMessage, /入住已完成/)
})

test('orientation pages no longer expose text-only allocation or bulk status-only check-in writes', () => {
  for (const path of ['OrientationDormPreassignView.vue', 'DormCheckinView.vue']) {
    const content = readFileSync(new URL(`../src/views/admin/orientation/${path}`, import.meta.url), 'utf8')
    assert.doesNotMatch(content, /api\.(updateDormInfo|batchConfirmCheckin)\(/)
    assert.match(content, /\/admin\/student-affairs\/dorm\//)
  }
})
