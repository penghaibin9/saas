/**
 * 毕设菜单按人群收敛：普通老师（权限全部来自自动带出的导师/评阅/评委/秘书身份）只看到 3 个入口，
 * 管理员保持原菜单；menuRequiresAny 只影响菜单，不进入路由权限投影（旧链接照常可进）。
 */
import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { getVisibleNavPlan, matchPermission, NAV_PLAN } from '../src/config/navPlan.js'
import { GRADUATION_WORKSPACES, isGraduationManager } from '../src/modules/graduation/config/graduationWorkspaces.js'
import { projectNavigationRoutePermissions } from '../src/router/navigationRouteProjection.js'

// 与后端 ROLE_PERMISSIONS 中四个毕设老师身份的 graduationDesign.* 并集一致
const TEACHER = [
  'graduationDesign.batch.view', 'graduationDesign.dashboard.view', 'graduationDesign.defense.view',
  'graduationDesign.final.review', 'graduationDesign.final.view', 'graduationDesign.grade.review',
  'graduationDesign.grade.view', 'graduationDesign.guidance.*', 'graduationDesign.midterm.review',
  'graduationDesign.proposal.review', 'graduationDesign.proposal.view', 'graduationDesign.risk.view',
  'graduationDesign.student.view', 'graduationDesign.taskbook.issue', 'graduationDesign.taskbook.update',
  'graduationDesign.taskbook.view', 'graduationDesign.topic.assign', 'graduationDesign.topic.create',
  'graduationDesign.topic.review', 'graduationDesign.topic.view', 'graduationDesign.review.submit',
  'graduationDesign.review.view', 'graduationDesign.defense.score', 'graduationDesign.defense.scoreConfirm',
  'graduationDesign.defense.notify', 'graduationDesign.defense.secondRound',
  'graduationDesign.grade.advisorScore'
]
const GRADE_ADMIN = [
  'graduationDesign.batch.view', 'graduationDesign.dashboard.view', 'graduationDesign.grade.appealReview',
  'graduationDesign.grade.calculate', 'graduationDesign.grade.publish', 'graduationDesign.grade.review',
  'graduationDesign.grade.view', 'graduationDesign.grade.withdraw', 'graduationDesign.student.view'
]

function graduationLeaves(patterns) {
  const plan = getVisibleNavPlan({ includePlanned: false, permissionPatterns: patterns, ctxKey: `t|${patterns.join(',')}` })
  const group = plan.find((item) => item.key === 'graduation')
  return group ? group.children.flatMap((mod) => mod.children.map((leaf) => leaf.label)) : []
}

test('普通老师只看到：我的毕设工作、题目库、过程指导台', () => {
  assert.equal(isGraduationManager(TEACHER, matchPermission), false)
  assert.deepEqual(graduationLeaves(TEACHER), ['我的毕设工作', '题目库', '过程指导台'])
})

test('管理员菜单：总览 + 6 个阶段 + 更多，旧入口一个不少', () => {
  const leaves = graduationLeaves(['graduationDesign.*'])
  assert.equal(leaves.length, 29)
  assert.deepEqual(leaves.slice(0, 3), ['毕设总览', '开工检查', '我的毕设工作'])
  assert.ok(leaves.includes('中期检查（按导师）'))
  assert.equal(isGraduationManager(['graduationDesign.*'], matchPermission), true)
  assert.equal(isGraduationManager(['*'], matchPermission), true)
})

test('成绩管理员仍是管理者，看得到成绩台账', () => {
  assert.equal(isGraduationManager(GRADE_ADMIN, matchPermission), true)
  assert.ok(graduationLeaves(GRADE_ADMIN).includes('成绩台账'))
})

test('menuRequiresAny 不进入路由权限投影：老师从工作台深链进入旧页面不受影响', () => {
  const routes = [{ path: '/admin/graduation', children: [{ path: 'proposals', meta: { permissionKey: 'graduationDesign.proposal.view' } }] }]
  const projected = projectNavigationRoutePermissions(routes, NAV_PLAN)
  const any = projected[0].children[0].meta.permissionAny || []
  assert.ok(any.includes('graduationDesign.proposal.view'))
  for (const key of ['graduationDesign.student.manage', 'graduationDesign.batch.update', 'graduationDesign.template.manage']) {
    assert.ok(!any.includes(key), `${key} 不应成为进入开题列表的替代权限`)
  }
  const labels = GRADUATION_WORKSPACES.flatMap((ws) => ws.children).filter((leaf) => !leaf.menuRequiresAny).map((leaf) => leaf.label)
  assert.deepEqual(labels, ['我的毕设工作', '题目库', '过程指导台'])
})

test('顶部菜单（adminMenu）同口径：老师的毕设分组只剩三个模块入口', async () => {
  const navPlanUrl = pathToFileURL(fileURLToPath(new URL('../src/config/navPlan.js', import.meta.url))).href
  const entitlementUrl = pathToFileURL(fileURLToPath(new URL('../src/security/moduleEntitlement.js', import.meta.url))).href
  const source = fs.readFileSync(new URL('../src/config/adminMenu.js', import.meta.url), 'utf8')
    .replace("from '@/config/navPlan'", `from '${navPlanUrl}'`)
    .replace("from '@/security/moduleEntitlement'", `from '${entitlementUrl}'`)
  const { getVisibleAdminMenu } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
  const ctx = (patterns) => ({
    activeContextId: 'ctx', currentRole: { roleCode: 'TEACHER', contextId: 'ctx' }, permissionPatterns: patterns,
    permissionVersion: 'v1', moduleEntitlements: ['graduation'], moduleAccessHealthy: true
  })
  const teacher = getVisibleAdminMenu(ctx(TEACHER)).find((group) => group.key === 'graduation')
  assert.ok(teacher, '老师应能看到毕业设计中心')
  assert.deepEqual(teacher.children.map((item) => item.path), [
    '/admin/graduation/my-work', '/admin/graduation/topic-lib?panel=list', '/admin/graduation/process?panel=taskbook'
  ])
  const admin = getVisibleAdminMenu(ctx(['graduationDesign.*'])).find((group) => group.key === 'graduation')
  assert.equal(admin.children[0].path, '/admin/graduation')
  assert.equal(admin.children.length, 8)
})
