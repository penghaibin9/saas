/**
 * 岗位实习角色菜单投影单元测试（07 整改方案 §11.1）。
 * 只覆盖 navPlan.js 纯函数（无 @ 别名依赖），用 Node 内置 test runner：`node --test tests/`。
 * adminMenu/BasePortalLayout 因依赖 @ 别名与 Vue，另由 build 与后端权限测试联合担保。
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { NAV_PLAN, matchPermission, getVisibleNavPlan, navPlanStats, searchNavPlan } from '../src/config/navPlan.js'

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

test('校管 *：V8 实习 11 个工作区全部可见', () => {
  const plan = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: 'admin' })
  const internship = plan.find((x) => x.key === 'internship')
  assert.equal(internship.children.length, 11)
  const visibleLeafCount = internship.children.flatMap((m) => m.children).length
  assert.ok(visibleLeafCount >= 32 && visibleLeafCount <= 36, '宽权限日常入口必须保持 32～36 个')
})

test('planner 视角不做权限投影：空权限集仍见完整能力目录', () => {
  const plan = getVisibleNavPlan({ includePlanned: true, permissionPatterns: [], ctxKey: 'planner' })
  assert.equal(plan.find((x) => x.key === 'internship').children.length, 11)
})

test('详情/动作型(hidden)不进日常侧栏', () => {
  const leaves = internshipLeaves(getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: 'a2' }))
  assert.ok(!leaves.some((l) => l.label === '批次详情'))
  assert.ok(!leaves.some((l) => l.label === '学生实习详情'))
  assert.ok(!leaves.some((l) => l.label === '实习档案包'))
})

test('搜索只暴露 Primary Command Owner：隐藏动作不命中，主工作台按权限命中', () => {
  const noPerm = searchNavPlan('成绩发布', [])
  assert.ok(!noPerm.some((r) => r.path && r.path.includes('/internship/scores')), '空权限集不应搜到成绩发布')
  const hiddenCommand = searchNavPlan('成绩发布', ['internship.score.publish'])
  assert.ok(!hiddenCommand.some((r) => r.path && r.path.includes('/internship/scores')), '页内成绩发布动作不应回到全局搜索')
  const primary = searchNavPlan('成绩工作台', ['internship.score.view'])
  assert.ok(primary.some((r) => r.path && r.path.includes('/internship/scores')), '有 view 权限应搜到成绩工作台')
})

test('ctxKey 不同 → 缓存不串味（不同身份得到不同投影）', () => {
  const a = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'], ctxKey: 'k1' })
  const b = getVisibleNavPlan({ includePlanned: false, permissionPatterns: [], ctxKey: 'k2' })
  assert.equal(a.find((g) => g.key === 'internship').children.length, 11)
  assert.equal(b.find((g) => g.key === 'internship'), undefined)
})

test('V6 学工十二个业务工作区均有真实安全落点，不再依赖无入口容器', () => {
  const studentAffairs = NAV_PLAN.find((group) => group.key === 'student-affairs')
  assert.equal(studentAffairs.children.length, 12)
  const workbench = studentAffairs.children.find((mod) => mod.key === 'sa-workbench')
  assert.equal(workbench.path, '/admin/student-affairs/dashboard')
  assert.equal(workbench.status, 'implemented')
  assert.equal(workbench.disabled, false)
  for (const workspace of studentAffairs.children) {
    assert.match(workspace.path, /^\/admin\//, `${workspace.key} 必须有真实站内落点`)
    assert.ok(workspace.children.length > 0, `${workspace.key} 必须保留三级业务入口`)
  }
})

test('navPlanStats 精确反映 V6 工作区已经从容器升级为真实落点', () => {
  const studentAffairs = NAV_PLAN.find((group) => group.key === 'student-affairs')
  const row = navPlanStats().find((item) => item.key === 'student-affairs')
  for (const key of ['implemented', 'partial', 'planned', 'unauthorized', 'containers', 'total']) {
    assert.equal(Number.isInteger(row[key]), true, `${key} 应为整数`)
  }
  const expectedContainers = studentAffairs.children.filter((item) => item.entryType === 'CONTAINER').length
  assert.equal(expectedContainers, 0)
  assert.equal(row.containers, expectedContainers)
  assert.equal(row.total, row.implemented + row.partial + row.planned + row.unauthorized)
})

// ── P6 §11.3 全角色菜单快照矩阵（权限集对齐后端 ROLE_PERMISSIONS 实习模板）──
const ROLE_PATTERNS = {
  校级管理员: ['*'],
  学院负责人: ['internship.*'],
  指导教师: ['internship.guide.*', 'internship.dashboard.view', 'internship.student.view',
    'internship.attendance.*', 'internship.makeup.*', 'internship.leave.view', 'internship.leave.review',
    'internship.report.view', 'internship.report.review', 'internship.plan.view', 'internship.task.view',
    'internship.guidance.*', 'internship.visit.*', 'internship.communication.*',
    'internship.risk.view', 'internship.risk.handle', 'internship.eval.self.view',
    'internship.score.view', 'internship.application.view', 'internship.application.review',
    'internship.agreement.view', 'internship.enterprise.view', 'internship.position.view',
    'internship.match.intention.view', 'internship.stats.view', 'internship.insurance.*', 'internship.archive.*'],
  辅导员: ['internship.dashboard.view', 'internship.student.view', 'internship.attendance.view',
    'internship.leave.view', 'internship.report.view', 'internship.risk.view'],
  领导: ['*.view', '*.stat'],
  督导审计: ['internship.dashboard.view', 'internship.student.view', 'internship.risk.view',
    'internship.stats.view', 'internship.stats.enterprise.view', 'internship.match.log.view',
    'internship.application.view', 'internship.archive.view', 'internship.complaint.view'],
  就业教师: ['internship.dashboard.view', 'internship.employment.view', 'internship.archive.*',
    'internship.stats.view', 'internship.stats.enterprise.view']
}

function internshipMods(patterns, key) {
  const plan = getVisibleNavPlan({ includePlanned: false, permissionPatterns: patterns, ctxKey: key })
  const g = plan.find((x) => x.key === 'internship')
  return g ? g.children : []
}

test('全角色菜单快照：各角色可见实习二级域数量按权限收敛', () => {
  const snap = {}
  for (const [role, patterns] of Object.entries(ROLE_PATTERNS)) snap[role] = internshipMods(patterns, role).length
  assert.equal(snap['校级管理员'], 11, '校管见全 11 工作区')
  assert.equal(snap['学院负责人'], 11, '院管见全 11 工作区')
  assert.ok(snap['指导教师'] > 0 && snap['指导教师'] <= 11)
  assert.ok(snap['辅导员'] < snap['校级管理员'], '辅导员菜单严格少于校管')
  assert.ok(snap['就业教师'] < 11 && snap['就业教师'] > 0)
  assert.ok(snap['督导审计'] < 11 && snap['督导审计'] > 0)
})

test('领导只读：见 view 叶子但不见成绩发布等高危操作项', () => {
  const leaves = internshipMods(['*.view', '*.stat'], 'leader').flatMap((m) => m.children)
  assert.ok(leaves.some((l) => l.permissionKey && l.permissionKey.endsWith('.view')), '领导应见只读项')
  assert.ok(!leaves.some((l) => l.permissionKey === 'internship.score.publish'), '领导不应见成绩发布')
  assert.ok(!leaves.some((l) => l.permissionKey === 'internship.enterprise.blacklist.manage'), '领导不应见企业黑名单')
})

test('辅导员：见协同只读项，不见成绩发布/批次规则配置', () => {
  const keys = internshipMods(ROLE_PATTERNS['辅导员'], 'counselor').flatMap((m) => m.children).map((l) => l.permissionKey)
  assert.ok(keys.includes('internship.student.view'), '辅导员应见学生名单')
  assert.ok(keys.includes('internship.risk.view'), '辅导员应见风险协同')
  assert.ok(!keys.includes('internship.score.publish'))
  assert.ok(!keys.includes('internship.batch.rule.checkin.manage'))
})
