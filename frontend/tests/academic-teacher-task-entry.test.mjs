import test from 'node:test'
import assert from 'node:assert/strict'
import { academicAffairsRoutes } from '../src/modules/academicAffairs/academic-affairs.routes.js'
import { getVisibleNavPlan, matchPermission } from '../src/config/navPlan.js'
import { resolveRecipe } from '../src/modules/workbench/config/workbenchRecipes.js'

const teacherPermissions = ['academicAffairs.teachingTask.view']
const routeTree = Array.isArray(academicAffairsRoutes) ? academicAffairsRoutes : [academicAffairsRoutes]
const children = routeTree.flatMap(route => route.children || [])

test('teacher workbench reaches the existing personal confirmation route and visible menu', () => {
  const shortcut = resolveRecipe('ACADEMIC_TEACHER').quickLinks.find(link => link.label === '教学任务')
  assert.equal(shortcut.to, '/admin/academic-affairs/teaching-tasks/teacher-confirm')
  const route = children.find(item => item.path === 'teaching-tasks/teacher-confirm')
  assert.equal(route.meta.permissionKey, 'academicAffairs.teachingTask.view')
  assert.ok(matchPermission(teacherPermissions, route.meta.permissionKey))
  const visible = getVisibleNavPlan({ permissionPatterns: teacherPermissions, includePlanned: false })
    .find(group => group.key === 'academic-affairs').children.flatMap(group => group.children || [])
  const menu = visible.find(item => item.path === shortcut.to)
  assert.ok(menu && !menu.disabled)
  assert.equal(menu.permissionKey, route.meta.permissionKey)
})

test('personal task access does not grant managerial task commands or unprivileged entry', () => {
  for (const path of ['teaching-tasks/assign', 'teaching-tasks/confirm', 'teaching-tasks/merge-split', 'teaching-tasks/adjust']) {
    const route = children.find(item => item.path === path)
    assert.ok(route, path)
    assert.equal(matchPermission(teacherPermissions, route.meta.permissionKey), false, path)
  }
  const route = children.find(item => item.path === 'teaching-tasks/teacher-confirm')
  assert.equal(matchPermission([], route.meta.permissionKey), false)
})
