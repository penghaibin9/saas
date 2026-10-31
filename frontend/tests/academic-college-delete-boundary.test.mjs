import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { matchPermission } from '../src/config/navPlan.js'

function loadView(name) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm, (_, binding) => `const ${binding} = dependencies`)
    .replace('export default', 'return')
  const dependencies = { matchPermission, canSubmit: status => ['DRAFT', 'RETURNED'].includes(status) }
  return { source, component: new Function('dependencies', script)(dependencies) }
}

const program = loadView('AaProgramConsoleView')
const course = loadView('AaCourseConsoleView')

function state(component, role, permissions, status = 'DRAFT') {
  const vm = { ctx: { currentRole: { roleCode: role }, permissionPatterns: permissions },
    selectedProgram: { status }, confirmDlg: { visible: false }, materialVoidConfirm: { visible: false } }
  vm.hasPermission = code => matchPermission(permissions, code)
  for (const name of ['isEditable', 'canDeleteItems', 'canVoidMaterial']) {
    if (component.computed[name]) Object.defineProperty(vm, name, { get: () => component.computed[name].call(vm) })
  }
  return vm
}

test('学院教务仍可编制方案，但三个实体删除入口均隐藏并拒绝打开确认框', () => {
  const vm = state(program.component, 'COLLEGE_ACADEMIC', ['academicAffairs.program.manage'])
  assert.equal(vm.isEditable, true)
  assert.equal(vm.canDeleteItems, false)
  for (const method of ['confirmDeleteCourse', 'confirmDeletePractice', 'confirmDeleteGrad']) {
    program.component.methods[method].call(vm, {})
    assert.equal(vm.confirmDlg.visible, false)
    assert.match(program.source, new RegExp(`<button v-if="canDeleteItems"[^>]+@click="${method}\\(row\\)">删除</button>`))
  }
})

test('其他岗位原有编制态删除能力与办理权限限制保留', () => {
  for (const role of ['ACADEMIC_ADMIN', 'SCHOOL_ADMIN', 'COLLEGE_ADMIN']) {
    assert.equal(state(program.component, role, ['academicAffairs.program.manage']).canDeleteItems, true)
    assert.equal(state(program.component, role, []).canDeleteItems, false)
    assert.equal(state(program.component, role, ['academicAffairs.program.manage'], 'PUBLISHED').canDeleteItems, false)
  }
})

test('学院教务不显示材料作废，其他有课程维护权限岗位保留材料作废', () => {
  const vm = state(course.component, 'COLLEGE_ACADEMIC', ['academicAffairs.course.manage'])
  assert.equal(vm.canVoidMaterial, false)
  course.component.methods.confirmVoidMaterial.call(vm, { id: '1', name: '课程大纲' })
  assert.equal(vm.materialVoidConfirm.visible, false)
  assert.match(course.source, /:removable="canVoidMaterial"/)
  for (const role of ['ACADEMIC_ADMIN', 'SCHOOL_ADMIN', 'COLLEGE_ADMIN']) {
    const allowed = state(course.component, role, ['academicAffairs.course.manage'])
    assert.equal(allowed.canVoidMaterial, true)
    course.component.methods.confirmVoidMaterial.call(allowed, { id: '1', name: '课程大纲' })
    assert.equal(allowed.materialVoidConfirm.visible, true)
    assert.equal(state(course.component, role, []).canVoidMaterial, false)
  }
})

test('切换为学院教务后旧确认动作不继续提交', async () => {
  let calls = 0
  const vm = state(program.component, 'COLLEGE_ACADEMIC', ['academicAffairs.program.manage'])
  vm.confirmDlg = { visible: true, submitting: false, action: async () => { calls++ } }
  await program.component.methods.onConfirmDelete.call(vm)
  assert.equal(calls, 0)
  const courseVm = state(course.component, 'COLLEGE_ACADEMIC', ['academicAffairs.course.manage'])
  await course.component.methods.doVoidMaterial.call(courseVm)
  assert.equal(courseVm.materialVoidConfirm.submitting, undefined)
})
