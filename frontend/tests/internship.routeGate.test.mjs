/**
 * 岗位实习路由权限门 + 缓存隔离单测（P5.1 残留 / P6 §11.1）。
 * 测真实模块 @/security/permissionGate（内部相对导入 navPlan，故 node 可直接加载）。
 * 运行：node --test tests/
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { setPermissionPatterns, clearPermissionPatterns, canEnterRoute } from '../src/security/permissionGate.js'
import { getVisibleNavPlan } from '../src/config/navPlan.js'

test('非岗位实习路由：本门一律放行（不误伤其它模块）', () => {
  setPermissionPatterns([]) // 已知空权限
  assert.equal(canEnterRoute({ moduleCode: 'GRADUATION', permissionKey: 'graduation.topic.view' }), true)
  assert.equal(canEnterRoute({ moduleCode: 'STUDENT_AFFAIRS', permissionKey: 'affairs.leave.view' }), true)
  clearPermissionPatterns()
})

test('实习路由无 permissionKey：放行', () => {
  setPermissionPatterns([])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP' }), true)
  clearPermissionPatterns()
})

test('fail-open：patterns 未知（未登录/冷加载）→ 实习路由放行', () => {
  clearPermissionPatterns()
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.score.publish' }), true)
})

test('已知权限：实习路由匹配则放行，不匹配则拦截', () => {
  // 指导教师典型权限集（无成绩发布 / 无企业黑名单）
  setPermissionPatterns(['internship.dashboard.view', 'internship.report.review', 'internship.student.view'])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.report.review' }), true, '有周报批阅权应进')
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.dashboard.view' }), true, '有工作台权应进')
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.score.publish' }), false, '无成绩发布权应拦')
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.enterprise.manage' }), false, '无企业管理权应拦')
  clearPermissionPatterns()
})

test('校级管理员(*)：任何实习路由放行', () => {
  setPermissionPatterns(['*'])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.score.publish' }), true)
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.enterprise.manage' }), true)
  clearPermissionPatterns()
})

test('学院负责人(internship.*)：实习域全放行，跨域仍不由本门拦（放行）', () => {
  setPermissionPatterns(['internship.*'])
  assert.equal(canEnterRoute({ moduleCode: 'INTERNSHIP', permissionKey: 'internship.batch.manage' }), true)
  clearPermissionPatterns()
})

// ── P6 缓存隔离：permissionVersion 变化（ctxKey 变化）必须让菜单投影失效 ──
test('缓存隔离：同 ctxKey 命中缓存；ctxKey 含新 permissionVersion → 取到新投影', () => {
  const V1 = 't1|ctx1|2026-07-13T10:00:00Z'
  const V2 = 't1|ctx1|2026-07-13T11:00:00Z' // 仅 permissionVersion 变化
  // 身份1：指导教师有限权限
  const a = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['internship.dashboard.view'], ctxKey: V1 })
  const aMods = a.find((g) => g.key === 'internship')
  // 同 ctxKey 再取（即便传入不同 patterns）→ 命中缓存，仍是旧投影（证明缓存以 ctxKey 为键）
  const aCached = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: V1 })
  assert.equal(aCached, a, '同 ctxKey 必须命中同一缓存对象（不因传参变化而重算）')
  // 新 permissionVersion → 新 ctxKey → 重新投影，拿到升权后的完整目录
  const b = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: V2 })
  const bMods = b.find((g) => g.key === 'internship')
  assert.ok(bMods && bMods.children.length === 12, '升权后（新 permissionVersion）应见全部 12 个二级域')
  assert.notEqual(bMods && bMods.children.length, aMods ? aMods.children.length : 0, '换 permissionVersion 后投影必须变化')
})
