import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/pages/student/orientation/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const component = new Function('go', script)(() => {})
function view(overrides = {}) {
  const vm = { ...component.data(), o: {
    stage: 'VERIFIED', overallStatus: 'PREPARED', hasData: true,
    steps: [{ key: 'INFO', title: '信息核对', status: 'DONE' }, { key: 'MATERIAL', title: '材料审核', status: 'TODO' }, { key: 'PAYMENT', title: '缴费', status: 'TODO' }, { key: 'CHECKIN', title: '现场报到', status: 'TODO' }],
    selfService: { available: true, canSubmitMaterials: true, materials: [] },
    qualification: { facts: { materials: { required: [] } } },
    reportCode: { canIssue: true }, greenChannelStatus: 'NOT_APPLIED', payStatus: 'UNPAID', ...overrides
  } }
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: fn.bind(vm) })
  return vm
}

test('approved plus submitted materials wait for review without asking for another upload', () => {
  const vm = view({ qualification: { facts: { materials: { required: [{status:'APPROVED'}, {status:'UPLOADED'}] } } } })
  assert.equal(vm.materialsWaitingReview, true)
  assert.equal(vm.taskList.find(t => t.key === 'MATERIAL').needsAction, false)
  assert.equal(vm.nextAction.path, '/pages/student/orientation/code/index')
})
test('optional arrival plan never prevents a credential when no enabled material step exists', () => {
  const vm = view({ steps: [{ key:'INFO', status:'DONE' }, { key:'CHECKIN', status:'TODO' }] })
  assert.equal(vm.nextAction.path, '/pages/student/orientation/code/index')
})
test('returned green channel remains actionable after onsite checkin', () => {
  const vm = view({ overallStatus:'CHECKED_IN', greenChannelStatus:'RETURNED', greenChannel:{rejectReason:'请补充家庭情况说明'},
    selfService:{available:false,canSubmitMaterials:true,materials:[]}, reportCode:{canIssue:false} })
  assert.equal(vm.showGreenChannel, true)
  assert.equal(vm.nextAction.path, '/pages/student/orientation/green-channel/index')
  assert.match(vm.nextAction.description, /请补充家庭情况说明/)
})
test('returned material shows the actual review reason and resubmission action', () => {
  const vm = view({selfService:{available:true,canSubmitMaterials:true,materials:[{isCurrent:true,status:'RETURNED',returnReason:'照片不清晰，请重新上传'}]}})
  assert.match(vm.nextAction.description, /照片不清晰/)
  assert.equal(vm.nextAction.path, '/pages/student/orientation/materials/index')
})
test('onsite checkin with outstanding material still tells the student to act', () => {
  const vm = view({overallStatus:'CHECKED_IN', selfService:{available:false,canSubmitMaterials:true,materials:[]},
    reportCode:{canIssue:false}, qualification:{blockers:[{step:'MATERIAL',code:'MATERIAL_MISSING'}]}})
  assert.equal(vm.nextAction.path, '/pages/student/orientation/materials/index')
  assert.match(vm.heroSub, /继续完成待办/)
  assert.doesNotMatch(vm.heroSub, /等待学院/)
})
test('closed self-service does not send student to a forbidden form', () => {
  const vm = view({selfService:{available:false,canSubmitMaterials:false,reason:'预报到尚未开放'},reportCode:{canIssue:false}})
  assert.equal(vm.nextAction.path, '')
  assert.match(vm.nextAction.description, /尚未开放/)
})
test('finalized or cancelled admission never suggests another submission', () => {
  for (const changes of [{overallStatus:'COLLEGE_CONFIRMED'}, {stage:'CANCELLED'}]) {
    const vm=view(changes)
    assert.equal(vm.taskList.some(t=>t.needsAction),false)
    assert.equal(vm.taskList.some(t=>/orientation\/(collect|materials|green-channel)/.test(t.path)),false)
  }
  assert.equal(view({overallStatus:'COLLEGE_CONFIRMED'}).nextAction.title, '迎新手续已完成')
})
