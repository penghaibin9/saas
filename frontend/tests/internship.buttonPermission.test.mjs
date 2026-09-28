/**
 * 岗位实习 PC 操作按钮角色化（P5.1）单元测试。
 * 覆盖 getContext() 的按钮判定内核：permissionActions[k].allowed = matchPermission(patterns, ACTION_PERMISSION_CODES[k])。
 *
 * 只依赖两个纯模块（无 @ 别名 / 无 Vue / 无 import.meta.env）：
 *   - navPlan.js 的 matchPermission（与后端 enforce_permission 同一套匹配语义）
 *   - context.constants.js 的 ACTION_PERMISSION_CODES（动作→后端真实权限码映射表）
 * 运行：node --test tests/
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { matchPermission } from '../src/config/navPlan.js'
import { ACTION_PERMISSION_CODES, ACTION_DENY_REASONS, permissionActions } from '../src/modules/internship/constants/context.constants.js'

// 后端 internship 各 router require_permission / _P_* 真实权限码全集（核验来源：
// backend/app/modules/internship/routers/*.py，2026-07-13）。用作“禁止装饰性假码”回归闸门。
const REAL_BACKEND_CODES = new Set([
  'internship.dashboard.view',
  'internship.batch.view', 'internship.batch.manage', 'internship.batch.export',
  'internship.student.view', 'internship.student.manage', 'internship.student.export',
  'internship.student.eligibility.review', 'internship.match.log.view',
  'internship.attendance.view', 'internship.attendance.review', 'internship.attendance.export',
  'internship.makeup.view', 'internship.makeup.review', 'internship.makeup.export',
  'internship.leave.view', 'internship.leave.review', 'internship.leave.export',
  'internship.report.view', 'internship.report.review', 'internship.report.export',
  'internship.plan.view', 'internship.plan.manage', 'internship.task.view', 'internship.task.review',
  'internship.guidance.view', 'internship.guidance.manage', 'internship.guidance.export',
  'internship.visit.view', 'internship.visit.manage', 'internship.visit.export',
  'internship.visit.plan.view', 'internship.visit.plan.manage',
  'internship.enterprise.view', 'internship.enterprise.manage', 'internship.enterprise.export',
  'internship.position.view', 'internship.position.manage', 'internship.position.publish', 'internship.position.export',
  'internship.match.intention.view', 'internship.match.intention.manage', 'internship.match.manual',
  'internship.match.batch', 'internship.match.result.view', 'internship.match.conflict.view', 'internship.match.export',
  'internship.application.view', 'internship.application.review',
  'internship.agreement.view', 'internship.agreement.manage', 'internship.agreement.sign', 'internship.agreement.export',
  'internship.agreement.template.manage',
  'internship.insurance.view', 'internship.insurance.verify',
  'internship.risk.view', 'internship.risk.handle', 'internship.risk.export',
  'internship.communication.view', 'internship.communication.manage',
  'internship.complaint.view', 'internship.complaint.intake',
  'internship.change.view', 'internship.change.review',
  'internship.archive.view', 'internship.archive.manage',
  'internship.eval.enterprise.view', 'internship.eval.enterprise.manage', 'internship.eval.enterprise.review', 'internship.eval.enterprise.export',
  'internship.eval.self.view', 'internship.eval.self.review', 'internship.eval.self.export', 'internship.eval.advisor.manage',
  'internship.score.view', 'internship.score.config', 'internship.score.manage', 'internship.score.publish', 'internship.score.export',
  'internship.stats.view', 'internship.stats.export'
])

// getContext() 的按钮判定内核（与 internship.api.js 一致；patterns 为数组时即 matchPermission）
function deriveAllowed(patterns, actionKey) {
  return matchPermission(patterns, ACTION_PERMISSION_CODES[actionKey])
}

test('回归闸门：ACTION_PERMISSION_CODES 每个映射值都是后端真实权限码（禁装饰性假码）', () => {
  for (const [k, code] of Object.entries(ACTION_PERMISSION_CODES)) {
    assert.ok(REAL_BACKEND_CODES.has(code), `动作 ${k} 映射到非真实权限码 ${code}`)
  }
})

test('映射表与静态兜底态 key 集一致（每个动作都有码 + 无权限文案）', () => {
  const paKeys = Object.keys(permissionActions).sort()
  assert.deepEqual(Object.keys(ACTION_PERMISSION_CODES).sort(), paKeys, 'ACTION_PERMISSION_CODES 覆盖全部动作')
  assert.deepEqual(Object.keys(ACTION_DENY_REASONS).sort(), paKeys, 'ACTION_DENY_REASONS 覆盖全部动作')
})

test('校级管理员(*)：所有操作按钮均可用', () => {
  const patterns = ['*']
  for (const k of Object.keys(ACTION_PERMISSION_CODES)) {
    assert.equal(deriveAllowed(patterns, k), true, `校管应可 ${k}`)
  }
})

test('学院负责人(internship.*)：所有实习操作按钮均可用', () => {
  const patterns = ['internship.*']
  for (const k of Object.keys(ACTION_PERMISSION_CODES)) {
    assert.equal(deriveAllowed(patterns, k), true, `院管应可 ${k}`)
  }
})

test('领导只读(*.view)：只读动作放开，管理/审核/发布类禁用', () => {
  const patterns = ['*.view', '*.stat']
  // 只读类
  assert.equal(deriveAllowed(patterns, 'exportGroup'), true, '领导可看统计(stats.view)')
  assert.equal(deriveAllowed(patterns, 'viewAuditLog'), true, '领导可看日志(match.log.view)')
  // 管理/审核/发布/导出类必须禁用
  assert.equal(deriveAllowed(patterns, 'createBatch'), false, '领导不可建批次(batch.manage)')
  assert.equal(deriveAllowed(patterns, 'reviewReport'), false, '领导不可批阅周报(report.review)')
  assert.equal(deriveAllowed(patterns, 'blacklistEnterprise'), false, '领导不可拉黑企业(enterprise.manage)')
  assert.equal(deriveAllowed(patterns, 'exportReports'), false, '领导不可导出周报(report.export)')
})

test('指导教师：本域审核类放开，成绩发布/企业黑名单等校级动作禁用', () => {
  // 与后端 ROLE_PERMISSIONS.INTERN_MENTOR 对齐的子集
  const MENTOR = [
    'internship.dashboard.view', 'internship.student.view',
    'internship.report.review', 'internship.attendance.review',
    'internship.leave.review', 'internship.risk.handle',
    'internship.guidance.manage', 'internship.visit.manage',
    'internship.agreement.manage', 'internship.agreement.sign',
    'internship.eval.enterprise.manage', 'internship.eval.self.review',
    'internship.archive.manage', 'internship.insurance.verify'
  ]
  assert.equal(deriveAllowed(MENTOR, 'batchApproveReports'), true, '导师可批阅周报')
  assert.equal(deriveAllowed(MENTOR, 'handleException'), true, '导师可处理考勤异常')
  assert.equal(deriveAllowed(MENTOR, 'manageRisk'), true, '导师可处置风险')
  // 校级/院级专属动作导师无权
  assert.equal(deriveAllowed(MENTOR, 'createBatch'), false, '导师不可建批次')
  assert.equal(deriveAllowed(MENTOR, 'blacklistEnterprise'), false, '导师不可拉黑企业')
  assert.equal(deriveAllowed(MENTOR, 'importStudents'), false, '导师不可批量导入学生建档')
})

test('空权限集：所有按钮禁用（正式构建降级=禁用的判定同义）', () => {
  for (const k of Object.keys(ACTION_PERMISSION_CODES)) {
    assert.equal(deriveAllowed([], k), false, `空权限应禁 ${k}`)
  }
})
