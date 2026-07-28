/**
 * 业务中心路由权限门 + 菜单缓存隔离单测。
 * 测真实模块 @/security/permissionGate（内部相对导入 navPlan，故 node 可直接加载）。
 * 运行：node --test tests/
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { setPermissionPatterns, clearPermissionPatterns, canEnterRoute } from '../src/security/permissionGate.js'
import { getVisibleNavPlan } from '../src/config/navPlan.js'

test('未纳入业务门禁的公共路由一律放行', () => {
  setPermissionPatterns([])
  assert.equal(canEnterRoute({ moduleCode: 'PUBLIC', permissionKey: 'public.page.view' }), true)
  assert.equal(canEnterRoute({ permissionKey: 'unknown.page.view' }), true)
  clearPermissionPatterns()
})

test('实习路由无 permissionKey：开发测试环境放行', () => {
  setPermissionPatterns([])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP' }), true)
  clearPermissionPatterns()
})

test('fail-open：patterns 未知（未登录/冷加载）→ 测试环境实习路由放行', () => {
  clearPermissionPatterns()
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.score.publish' }), true)
})

test('已知权限：实习路由匹配则放行，不匹配则拦截', () => {
  setPermissionPatterns(['internship.dashboard.view', 'internship.report.review', 'internship.student.view'])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.report.review' }), true, '有周报批阅权应进')
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.dashboard.view' }), true, '有工作台权应进')
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.score.publish' }), false, '无成绩发布权应拦')
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.enterprise.manage' }), false, '无企业管理权应拦')
  clearPermissionPatterns()
})

test('校级管理员(*)：任何受管业务路由放行', () => {
  setPermissionPatterns(['*'])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.score.publish' }), true)
  assert.equal(canEnterRoute({ moduleCode: 'GRADUATION', permissionKey: 'graduation.topic.view' }), true)
  assert.equal(canEnterRoute({ moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'studentAffairs.leave.view' }), true)
  clearPermissionPatterns()
})

test('学院负责人(internship.*)：实习域全放行', () => {
  setPermissionPatterns(['internship.*'])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.batch.manage' }), true)
  clearPermissionPatterns()
})

// 缓存隔离：ctxKey 与权限签名共同组成缓存键，任一变化都必须重新投影。
test('菜单缓存：同 ctxKey+同权限命中缓存；权限或 permissionVersion 变化重新投影', () => {
  const V1 = 't1|ctx1|2026-07-13T10:00:00Z'
  const V2 = 't1|ctx1|2026-07-13T11:00:00Z'
  const limited = ['internship.dashboard.view']

  const a = getVisibleNavPlan({ includePlanned: false, permissionPatterns: limited, ctxKey: V1 })
  const aMods = a.find((g) => g.key === 'internship')
  const aCached = getVisibleNavPlan({ includePlanned: false, permissionPatterns: [...limited], ctxKey: V1 })
  assert.equal(aCached, a, '同 ctxKey 与同权限签名必须命中同一缓存对象')

  const elevatedSameContext = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: V1 })
  assert.notEqual(elevatedSameContext, a, '权限签名变化不得复用旧权限投影')

  const b = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: V2 })
  const bMods = b.find((g) => g.key === 'internship')
  assert.ok(bMods && bMods.children.length === 12, '升权后（新 permissionVersion）应见全部 12 个二级域')
  assert.notEqual(b, elevatedSameContext, 'permissionVersion 变化必须创建新的缓存投影')
  assert.notEqual(bMods && bMods.children.length, aMods ? aMods.children.length : 0, '换权限后投影必须变化')
})
