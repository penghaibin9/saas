/**
 * 岗位实习角色菜单投影单元测试（07 整改方案 §11.1）。
 * 只覆盖 navPlan.js 纯函数（无 @ 别名依赖），用 Node 内置 test runner：`node --test tests/`。
 * adminMenu/BasePortalLayout 因依赖 @ 别名与 Vue，另由 build 与后端权限测试联合担保。
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { matchPermission, getVisibleNavPlan, searchNavPlan } from '../src/config/navPlan.js'

function internshipLeaves(plan) {
  const g = plan.find((x) => x.key === 'internship')
  return g ? g.children.flatMap((m) => m.children) : []
}
// 指导教师典型权限集（与后端 ROLE_PERMISSIONS.INTERN_MENTOR 对齐的子集）
const MENTOR = [
  'internship.dashboard.view', 'internship.student.view', 'internship.report.review',
  'internship.guidance.record.create', 'internship.visit.plan.manage', 'internship.risk.view'
]

test('matchPermission: * / a.b.* 前缀 / *.view 后缀 / 精确 / 未命中', () => {
  assert.equal(matchPermission(['*'], 'internship.score.publish'), true)
  assert.equal(matchPermission(['internship.guide.*'], 'internship.guide.record'), true)
  assert.equal(matchPermission(['internship.guide.*'], 'internship.guide'), true)
  assert.equal(matchPermission(['internship.score.view'], 'internship.score.view'), true)
  assert.equal(matchPermission(['*.view'], 'internship.score.view'), true)
  assert.equal(matchPermission(['*.view'], 'internship.score.publish'), false)
  assert.equal(matchPermission(['internship.student.view'], 'internship.score.publish'), false)
  assert.equal(matchPermission([], 'x'), false)
  assert.equal(matchPermission(null, 'x'), false)
})

test('普通角色(指导教师)：只投影出被授权叶子，无权项被隐藏', () => {
  const leaves = internshipLeaves(getVisibleNavPlan({ includePlanned: false, permissionPatterns: MENTOR, ctxKey: 'mentor' }))
  const keys = leaves.map((l) => l.permissionKey)
  assert.ok(keys.includes('internship.dashboard.view'), '指导教师应见工作台')
  assert.ok(keys.includes('internship.report.review'), '指导教师应见周报批阅')
  assert.ok(!keys.includes('internship.score.publish'), '指导教师不应见成绩发布')
  assert.ok(!keys.includes('internship.enterprise.blacklist.manage'), '指导教师不应见企业黑名单')
})

test('学生/空权限集：实习中心不出现在日常侧栏', () => {
  const plan = getVisibleNavPlan({ includePlanned: false, permissionPatterns: [], ctxKey: 'student' })
  assert.equal(plan.find((g) => g.key === 'internship'), undefined)
})

test('校管 *：实习 12 个二级域全部可见', () => {
  const plan = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: 'admin' })
  assert.equal(plan.find((x) => x.key === 'internship').children.length, 12)
})

test('planner 视角不做权限投影：空权限集仍见完整能力目录', () => {
  const plan = getVisibleNavPlan({ includePlanned: true, permissionPatterns: [], ctxKey: 'planner' })
  assert.equal(plan.find((x) => x.key === 'internship').children.length, 12)
})

test('详情/动作型(hidden)不进日常侧栏', () => {
  const leaves = internshipLeaves(getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: 'a2' }))
  assert.ok(!leaves.some((l) => l.label === '批次详情'))
  assert.ok(!leaves.some((l) => l.label === '学生实习详情'))
  assert.ok(!leaves.some((l) => l.label === '实习档案包'))
})

test('搜索按权限过滤：无权限页面不被搜索命中，有权限则命中', () => {
  const noPerm = searchNavPlan('成绩发布', [])
  assert.ok(!noPerm.some((r) => r.path && r.path.includes('/internship/scores')), '空权限集不应搜到成绩发布')
  const withPerm = searchNavPlan('成绩发布', ['internship.score.publish'])
  assert.ok(withPerm.some((r) => r.path && r.path.includes('/internship/scores')), '有 publish 权限应搜到成绩发布')
})

test('ctxKey 不同 → 缓存不串味（不同身份得到不同投影）', () => {
  const a = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: 'k1' })
  const b = getVisibleNavPlan({ includePlanned: false, permissionPatterns: [], ctxKey: 'k2' })
  assert.equal(a.find((g) => g.key === 'internship').children.length, 12)
  assert.equal(b.find((g) => g.key === 'internship'), undefined)
})
