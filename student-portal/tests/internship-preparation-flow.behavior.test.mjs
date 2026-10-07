import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/views/internship/InternshipView.vue', import.meta.url), 'utf8')
function computedBody(name) {
  return source.split('const ' + name + ' = computed(() => {')[1].split('\n})')[0]
}
function action(overrides = {}) {
  const state = { my: { value: { status: 'PREPARING', hasData: true } }, qualification: { value: { status: 'QUALIFIED' } }, qualificationHint: { value: '' }, sourceStates: { insurance: { status: 'empty' }, plan: { status: 'empty' } }, planMeta: { value: null }, activeAgreement: { value: null }, fmt: (v) => v, statusText: (v) => v, ...overrides }
  return new Function(...Object.keys(state), computedBody('currentAction'))(...Object.values(state))
}
test('preparation shows the actual phase without completed agreement or training claims', () => {
  const flow = (status) => new Function('my', computedBody('flowSteps'))({ value: { status } })
  assert.deepEqual(flow('PREPARING').map(s => s.state), ['current', 'todo', 'todo', 'todo', 'todo'])
  assert.equal(flow('READY').find(s => s.state === 'current').name, '待上岗')
  assert.equal(flow('ASSESSING').find(s => s.state === 'current').name, '考核评价')
  assert.ok(flow('UNKNOWN').every(s => s.state === 'todo'))
})
test('qualification decisions precede downstream instructions and missing positions lead to selection', () => {
  assert.equal(action().tab, 'enterprises')
  for (const status of ['PENDING', 'UNQUALIFIED', 'UNKNOWN']) {
    assert.equal(action({ qualification: { value: { status } } }).tab, 'overview')
  }
})
test('an empty plan response cannot claim the school has published a plan or the student is onboard', () => {
  const common = { my: { value: { status: 'READY', positionName: '机器人调试', enterpriseName: '验收企业' } }, sourceStates: { insurance: { status: 'data' }, plan: { status: 'data' } } }
  assert.equal(action({ ...common, planMeta: { value: {} } }).tab, 'overview')
  assert.equal(action({ ...common, planMeta: { value: { id: '9', status: 'PUBLISHED', ackStatus: 'PENDING' } } }).tab, 'plan')
})
