import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { matchPermission } from '../src/config/navPlan.js'

function loadView(name) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies`)
    .replace('export default', 'return')
  return { source, component: new Function('dependencies', script)({ matchPermission, toast: { error() {} } }) }
}

const schedule = loadView('AaTeacherScheduleView')
const apply = loadView('AaScheduleChangeApplyView')

function state(role, permitted, self = false) {
  const pushed = []
  const vm = { ctx: { currentRole: { roleCode: role }, permissionPatterns: permitted ? ['academicAffairs.scheduleChange.apply'] : [] },
    isSelfView: self, selectedItem: { itemId: '42' }, selectedOccurrenceWeek: 3, $router: { push: value => pushed.push(value) } }
  Object.defineProperty(vm, 'canStartChange', { get: () => schedule.component.computed.canStartChange.call(vm) })
  return { vm, pushed }
}

test('学院教务可从已获授权的本院教师课位进入协助申请', () => {
  const { vm, pushed } = state('COLLEGE_ACADEMIC', true)
  assert.equal(vm.canStartChange, true)
  schedule.component.methods.applyChange.call(vm, 'STOP')
  assert.deepEqual(pushed[0].query, { originItemId: '42', changeType: 'STOP', occurrenceWeek: '3' })
  assert.match(schedule.source, /v-if="canStartChange" class="aa-item-detail__actions"/)
})

test('任课教师仅本人入口可用，其他查询岗位和无权限学院岗位不能发起', () => {
  assert.equal(state('ACADEMIC_TEACHER', true, true).vm.canStartChange, true)
  for (const [role, permitted] of [['ACADEMIC_TEACHER', true], ['COLLEGE_ACADEMIC', false], ['LEADER', false]]) {
    const { vm, pushed } = state(role, permitted)
    assert.equal(vm.canStartChange, false)
    schedule.component.methods.applyChange.call(vm, 'ADJUST')
    assert.equal(pushed.length, 0)
  }
})

test('停补课仍须具体教学周，学院身份不跳过发生课次校验', () => {
  const { vm, pushed } = state('COLLEGE_ACADEMIC', true)
  vm.selectedOccurrenceWeek = null
  schedule.component.methods.applyChange.call(vm, 'STOP')
  schedule.component.methods.applyChange.call(vm, 'MAKEUP')
  assert.equal(pushed.length, 0)
})

test('申请页明确区分学院代办与教师本人，学院不返回教师今日页', () => {
  for (const [role, expected] of [['COLLEGE_ACADEMIC', '本院课位'], ['ACADEMIC_TEACHER', '本人课位']]) {
    const vm = { ctx: { currentRole: { roleCode: role } } }
    vm.isCollegeAssistant = apply.component.computed.isCollegeAssistant.call(vm)
    assert.equal(apply.component.computed.scopeName.call(vm), expected)
  }
  assert.match(apply.source, /学院教务协助登记本院调停课/)
  assert.match(apply.source, /v-if="isAcademicTeacher"[^\n]+返回今日教学/)
})
