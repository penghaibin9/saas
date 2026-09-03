import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import {
  NAV_PLAN,
  findActiveInPlan,
  getVisibleNavPlan,
  searchNavPlan
} from '../src/config/navPlan.js'

const group = NAV_PLAN.find((item) => item.key === 'student-affairs')
assert.ok(group, 'student-affairs group must exist')

const expectedWorkspaces = [
  ['01', 'sa-workbench', '今日工作', '今天先处理什么'],
  ['02', 'sa-profile', '唯一学生360', '围绕学生看完整背景'],
  ['03', 'sa-risk', '风险与重点学生', '按学生聚合多来源风险'],
  ['04', 'sa-talks', '谈心家校与回访', '处置后形成闭环'],
  ['05', 'sa-leave', '请假与返校', '申请 → 返校 → 超期'],
  ['06', 'sa-aid', '困难与资助', '认定 → 资助 → 发放'],
  ['07', 'sa-discipline', '违纪处分与教育', '处分 → 教育 → 回访'],
  ['08', 'sa-dorm', '宿舍与公寓', '房源 → 入住 → 异常'],
  ['09', 'sa-activities', '活动与成长', '活动成果沉淀成长事实'],
  ['10', 'sa-orientation', '数字迎新', '新生 → 报到 → 归档'],
  ['11', 'sa-mental', '心理专项', '按角色显示敏感工作区'],
  ['12', 'sa-archive-stats', '统计与档案', '领导聚合与正式归档']
]

const externalRoutes = new Set([
  '/workbench',
  '/admin/approval/todos',
  '/admin/campus-service/classes',
  '/admin/campus-service/grants'
])
const sources = {
  '/admin/student-affairs': fs.readFileSync(new URL('../src/modules/studentAffairs/studentAffairs.routes.js', import.meta.url), 'utf8'),
  '/admin/orientation': fs.readFileSync(new URL('../src/modules/orientation/orientation.routes.js', import.meta.url), 'utf8'),
  '/admin/student': fs.readFileSync(new URL('../src/modules/student/student.routes.js', import.meta.url), 'utf8')
}

function routeExists(navPath) {
  const path = navPath.split('?')[0]
  if (externalRoutes.has(path)) return true
  for (const [prefix, source] of Object.entries(sources)) {
    if (path === prefix) return source.includes(`path: '${prefix}'`)
    if (!path.startsWith(`${prefix}/`)) continue
    const relative = path.slice(prefix.length + 1)
    if (source.includes(`path: '${relative}'`)) return true
    if (!relative && source.includes(`path: '${prefix}'`)) return true
  }
  return false
}

test('student affairs sidebar is exactly three waves and twelve ordered workspaces', () => {
  assert.equal(group.workspaceTitle, '学工业务工作区')
  assert.equal(group.children.length, 12)
  assert.deepEqual(
    group.children.map((item) => [item.ordinal, item.key, item.label, item.description]),
    expectedWorkspaces
  )
  assert.deepEqual(
    [...new Set(group.children.map((item) => item.sectionKey))],
    ['wave-1', 'wave-2', 'wave-3']
  )
  for (const wave of ['wave-1', 'wave-2', 'wave-3']) {
    assert.equal(group.children.filter((item) => item.sectionKey === wave).length, 4)
  }
})

test('every configured leaf points to a registered real route or an audited external route', () => {
  const broken = []
  for (const workspace of group.children) {
    for (const leaf of workspace.children) {
      if (!leaf.path || !routeExists(leaf.path)) {
        broken.push(`${workspace.key}/${leaf.label} -> ${leaf.path || '(missing)'}`)
      }
    }
  }
  assert.deepEqual(broken, [])
})

test('visible third-level menu is curated while low-frequency routes remain searchable deep links', () => {
  const visible = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['*'],
    ctxKey: 'v6-workspace-test'
  }).find((item) => item.key === 'student-affairs')
  assert.ok(visible)
  assert.equal(visible.children.length, 12)
  const orientation = visible.children.find((item) => item.key === 'sa-orientation')
  assert.deepEqual(
    orientation.children.map((item) => item.label),
    ['迎新总览', '批次与规则', '新生底账', '报到资格', '报到办理', '异常闭环', '统计归档']
  )
  assert.equal(orientation.children.some((item) => item.label === '报到流程配置'), false)
  const search = searchNavPlan('报到流程配置', ['studentAffairs.orientation.view'])
  assert.equal(search.length, 1)
  assert.equal(search[0].path, '/admin/orientation/flow-config')
  assert.equal(search[0].trail, '学工中心 / 数字迎新 / 报到流程配置')
})

test('permissions project each workspace to a permitted landing page and search result', () => {
  const visible = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['studentAffairs.funding.view'],
    ctxKey: 'funding-only'
  }).find((item) => item.key === 'student-affairs')
  assert.ok(visible)
  assert.deepEqual(visible.children.map((item) => item.key), ['sa-aid'])
  assert.equal(visible.children[0].path, '/admin/student-affairs/funding')
  assert.equal(visible.children[0].children[0].label, '奖助评审')

  assert.equal(searchNavPlan('学生主档', ['studentAffairs.student.view'])[0].path, '/admin/student/list')
  assert.equal(searchNavPlan('学生主档', ['unrelated.permission']).length, 0)
})

test('deep routes highlight their visible workspace and semantic third-level stage', () => {
  const cases = [
    ['/admin/student/42', '/admin/student/42', 'sa-profile', '学生主档'],
    ['/admin/student-affairs/risk/R-18', '/admin/student-affairs/risk/R-18', 'sa-risk', '风险工作台'],
    ['/admin/student-affairs/leave/ledger', '/admin/student-affairs/leave/ledger?status=OVERDUE', 'sa-leave', '逾期未销假'],
    ['/admin/orientation/materials', '/admin/orientation/materials', 'sa-orientation', '报到办理'],
    ['/admin/orientation/archive', '/admin/orientation/archive', 'sa-orientation', '统计归档']
  ]
  for (const [path, fullPath, modKey, leafKey] of cases) {
    const active = findActiveInPlan(path, fullPath)
    assert.equal(active.groupKey, 'student-affairs', fullPath)
    assert.equal(active.modKey, modKey, fullPath)
    assert.equal(active.leafKey, leafKey, fullPath)
  }
})

test('visible labels and paths are unique inside each workspace and dorm allocation is no longer missing', () => {
  const visible = getVisibleNavPlan({
    includePlanned: false,
    permissionPatterns: ['*'],
    ctxKey: 'uniqueness'
  }).find((item) => item.key === 'student-affairs')
  for (const workspace of visible.children) {
    const labels = workspace.children.map((leaf) => leaf.label)
    const paths = workspace.children.map((leaf) => leaf.path)
    assert.equal(new Set(labels).size, labels.length, `${workspace.key} duplicate label`)
    assert.equal(new Set(paths).size, paths.length, `${workspace.key} duplicate path`)
  }
  const dorm = visible.children.find((item) => item.key === 'sa-dorm')
  assert.ok(dorm.children.some((item) => item.path === '/admin/student-affairs/dorm/allocation'))
})
