import assert from 'node:assert/strict'
import test from 'node:test'

import NAV_PLAN from './navPlan.js'

function studentAffairsModule() {
  const module = NAV_PLAN.find((group) => group.key === 'student-affairs')
  assert.ok(module, 'student-affairs navigation group must exist')
  return module
}

test('数字迎新菜单权限与真实路由守卫一致', () => {
  const orientation = studentAffairsModule().children.find((item) => item.key === 'sa-orientation')
  assert.ok(orientation, 'sa-orientation navigation module must exist')
  assert.equal(orientation.path, '/admin/orientation')
  assert.equal(orientation.permissionKey, 'orientation.student.view')
})

test('班级管理菜单权限与真实路由守卫一致', () => {
  const classes = studentAffairsModule().children.find((item) => item.key === 'sa-classes')
  assert.ok(classes, 'sa-classes navigation module must exist')

  const classManagement = classes.children.find(
    (item) => item.path === '/admin/campus-service/classes'
  )
  assert.ok(classManagement, 'class-management navigation entry must exist')
  assert.equal(classManagement.permissionKey, 'campus.record.view')

  const counselorAssignments = classes.children.find(
    (item) => item.path === '/admin/student-affairs/counselor-assignments'
  )
  assert.ok(counselorAssignments, 'counselor-assignment navigation entry must exist')
  assert.equal(counselorAssignments.permissionKey, 'studentAffairs.class.view')
})
