import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse } from '@babel/parser'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/DisciplineWorkbenchView.vue', import.meta.url), 'utf8').split('<script>')[1].split('</script>')[0]
const ast = parse(source, { sourceType: 'module' })
const component = ast.program.body.find(node => node.type === 'ExportDefaultDeclaration').declaration
const computed = component.properties.find(node => node.key.name === 'computed').value
const method = computed.properties.find(node => node.key.name === 'detailActions')
const actions = vm.runInNewContext(`({${source.slice(method.start, method.end)}}).detailActions`, {
  REVIEW_NODES: ['COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW', 'SCHOOL_REVIEW']
})
const keys = (status, allowedActions, effect) => Array.from(actions.call({ selected: { status, allowedActions }, postEffectState: effect }), action => action.key)

test('a school-wide viewer without the current task never receives review buttons', () => {
  assert.deepEqual(keys('STUDENT_AFFAIRS_REVIEW', []), [])
  assert.deepEqual(keys('COLLEGE_REVIEW', undefined), [])
  assert.deepEqual(keys('COLLEGE_REVIEW', ['APPROVE', 'REJECT']), ['approve', 'reject'])
})
test('resubmission and removal actions also use the current backend receipt', () => {
  assert.deepEqual(keys('RETURNED', ['SUBMIT']), ['submit'])
  assert.deepEqual(keys('REMOVE_REVIEW', []), [])
  assert.deepEqual(keys('REMOVE_REVIEW', ['REMOVE_REJECT']), ['removeReject'])
})
test('a read-only result preserves history navigation without inventing a removal write', () => {
  assert.deepEqual(keys('EFFECTIVE', [], { key: 'DELIVERY_REQUIRED', actionLabel: '登记送达', permission: 'studentAffairs.discipline.deliver' }), ['postEffect'])
})
