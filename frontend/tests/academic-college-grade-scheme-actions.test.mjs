import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { matchPermission } from '../src/config/navPlan.js'
import { academicAffairsRoutes } from '../src/modules/academicAffairs/academic-affairs.routes.js'
import { canEnterRoute, clearPermissionPatterns, setModuleEntitlements, setPermissionPatterns } from '../src/security/permissionGate.js'

function page(name, patterns, dependencies = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm,
      (_, binding) => `const ${binding} = dependencies${binding.trim().startsWith('{') ? '' : '.' + binding.trim()}`)
    .replace('export default', 'return')
  const definition = new Function('dependencies', script)({ matchPermission, currentUserFromToken: () => null,
    toast: { success() {}, error() {} }, gradeError: () => '读取失败', ...dependencies })
  const state = { ...definition.data(), ctx: { permissionPatterns: patterns,
    currentRole: { roleCode: 'COLLEGE_ACADEMIC' }, dataScope: { scopeType: 'COLLEGE' } },
    $route: { query: {} }, $router: { push() {} } }
  for (const [key, method] of Object.entries(definition.methods || {})) {
    if (typeof method === 'function') state[key] = method.bind(state)
  }
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return state
}

const components = [
  { code: 'PROJECT', name: '项目考核', weight: 40, required: true, order: 1 },
  { code: 'FINAL', name: '期末考核', weight: 60, required: true, order: 2 }
]
const task = { gradeTaskId: '51', status: 'NOT_STARTED', allowedActions: ['INPUT', 'SUBMIT', 'EXTEND_DEADLINE'] }

test('实际成绩页路由接受独立构成权限，校级策略权限不会替代录分权限', () => {
  const route = academicAffairsRoutes.flatMap(row => row.children || []).find(row => row.path === 'grade-entry')
  assert.ok(route)
  try {
    setModuleEntitlements(['academicAffairs'])
    for (const code of ['academicAffairs.grade.scheme.manage', 'academicAffairs.grade.input']) {
      setPermissionPatterns([code])
      assert.equal(canEnterRoute(route.meta), true)
    }
    setPermissionPatterns(['academicAffairs.grade.policy.manage'])
    assert.equal(canEnterRoute(route.meta), false)
  } finally { clearPermissionPatterns() }
})

test('学院从实际任务入口维护构成，仅回读方案，不调用录分名册或提交入口', async () => {
  let scheme = { gradeTaskId: '51', schemeId: '7', schemeVersion: 1, status: 'DRAFT', editable: true, components }
  const calls = []
  const state = page('AaGradeEntryView', ['academicAffairs.grade.scheme.manage'], {
    academicAffairsApi: { async getGradeTasks() { return { code: 0, data: { list: [task] } } } },
    academicAffairsR10Api: {
      async getGradeScheme() { calls.push('scheme-read'); return { code: 0, data: scheme } },
      async updateGradeScheme(id, next) { calls.push('scheme-save'); scheme = { ...scheme, components: next, schemeVersion: 2 }; return { code: 0, data: scheme } },
      async getDynamicGradeRoster() { assert.fail('学院方案模式不得调用录分名册') },
      async submitDynamicGrade() { assert.fail('学院方案模式不得提交成绩') }
    }
  })
  await state.openTask({ gradeTaskId: '51' })
  assert.equal(state.schemeOnly, true)
  assert.equal(state.schemeEditable, true)
  assert.equal(state.editable, false)
  assert.equal(state.dynamicWritable, false)
  assert.equal(state.canSubmit, false)
  assert.equal(state.canExtendDeadline, false)
  state.schemeDraft[0].weight = 50
  state.schemeDraft[1].weight = 50
  await state.saveScheme()
  assert.equal(calls.filter(value => value === 'scheme-save').length, 1)
  assert.equal(state.schemePending, false)
  assert.deepEqual(state.dynamicComponents.map(row => row.weight), [50, 50])
  assert.equal(state.dynamicData.items.length, 0)
})

test('教师保留原动态名单和录分能力，服务器锁定方案后不可编辑构成', async () => {
  let rosterReads = 0
  const state = page('AaGradeEntryView', ['academicAffairs.grade.input'], {
    academicAffairsR10Api: { async getDynamicGradeRoster() {
      rosterReads++
      return { code: 0, data: { gradeTaskId: '51', status: 'NOT_STARTED', canWriteComponents: true,
        scheme: { schemeId: '7', status: 'DRAFT', editable: true, components }, items: [] } }
    }, async getGradeScheme() { assert.fail('教师工作区应继续使用正式名单投影') } }
  })
  state.task = { ...task }
  await state.loadDynamic()
  assert.equal(rosterReads, 1)
  assert.equal(state.schemeOnly, false)
  assert.equal(state.dynamicWritable, true)
  assert.equal(state.schemeEditable, true)
  state.dynamicData.scheme.editable = false
  state.dynamicData.scheme.status = 'LOCKED'
  assert.equal(state.schemeEditable, false)
})

test('移除后添加成绩项仍生成不重复内部编号，失败回读不开放编辑', () => {
  const state = page('AaGradeEntryView', ['academicAffairs.grade.scheme.manage'])
  state.schemeDraft = [{ code: 'ITEM_1' }, { code: 'ITEM_3' }]
  state.addComponent()
  assert.equal(state.schemeDraft[2].code, 'ITEM_4')
  state.dynamicData = { scheme: { editable: true }, items: [] }
  state.dynamicError = '读取失败'
  assert.equal(state.schemeEditable, false)
})

test('分配教师按钮使用分配权限，任务管理权限不会单独开放分配按钮', () => {
  const row = { status: 'PENDING_ASSIGN' }
  const allowed = page('AaTeacherAssignConsoleView', ['academicAffairs.teachingTask.assign'])
  const denied = page('AaTeacherAssignConsoleView', ['academicAffairs.teachingTask.manage'])
  assert.equal(allowed.canAssign(row), true)
  assert.equal(denied.canAssign(row), false)
  const detail = page('AaTaskDetailView', ['academicAffairs.teachingTask.assign'])
  detail.workbench = { status: 'DRAFT', actions: { canAssign: true, canVoidDraft: false } }
  assert.equal(detail.canAssignRow(row), true)
  assert.equal(detail.canVoidDraftRow({ ...row, teacherKey: '' }), false)
})
