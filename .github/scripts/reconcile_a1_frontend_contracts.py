from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    file = Path(path)
    text = file.read_text(encoding='utf-8')
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one audited block, got {count}')
    file.write_text(text.replace(old, new, 1), encoding='utf-8')


replace_once(
    'frontend/src/config/navPlan.js',
    "if (score > best.score || (score === best.score && row.isLeaf && !best.leafKey)) {",
    "if (score > best.score || (score === best.score && row.isLeaf && !best.leafKey && row.groupKey === 'student-affairs')) {",
    'keep V6 third-level highlight scoped to student affairs'
)

replace_once(
    'frontend/src/config/navPlan.js',
    """      H('旧学工画像入口', '/admin/student-affairs/profile', 'studentAffairs.student.view', 'COMPAT', {
        activeLabel: '学生主档'
      }),""",
    """      H('学工画像兼容详情', '/admin/student-affairs/profile', null, 'DETAIL', {
        permissionAny: _STU_VIEW_ANY,
        activeLabel: '学生主档',
        matchPrefix: true
      }),""",
    'preserve the legacy student-affairs profile as a permission-safe drilldown'
)

replace_once(
    'frontend/tests/d1-dorm-professional-workspace-contract.test.mjs',
    """test('D1 publishes one professional dorm cockpit and six real workspaces', () => {
  for (const [label, path] of [
    ['宿舍驾驶舱', '/admin/student-affairs/dormitory'],
    ['房源管理', '/admin/student-affairs/dorm/resource'],
    ['入住管理', '/admin/student-affairs/dorm/checkin'],
    ['调宿与退宿', '/admin/student-affairs/dorm/transfer'],
    ['宿舍检查', '/admin/student-affairs/dorm/check'],
    ['宿舍异常（含夜不归宿）', '/admin/student-affairs/dorm/exception'],
    ['宿舍统计', '/admin/student-affairs/dorm/stats']
  ]) {
    assert.match(nav, new RegExp(`I\\\\('${label.replace(/[.*+?^${}()|[\\\\]\\\\]/g, '\\\\$&')}', '${path.replaceAll('/', '\\\\/')}', 'studentAffairs\\\\.dorm\\\\.view'\\\\)`))
  }
  assert.match(routes, /path: 'dormitory'[\\s\\S]*permissionKey: 'studentAffairs\\.dorm\\.view'/)
})""",
    """test('D1 publishes one professional dorm cockpit and the complete real workspace chain', () => {
  for (const [label, path] of [
    ['宿舍驾驶舱', '/admin/student-affairs/dormitory'],
    ['房源管理', '/admin/student-affairs/dorm/resource'],
    ['分配计划', '/admin/student-affairs/dorm/allocation'],
    ['入住管理', '/admin/student-affairs/dorm/checkin'],
    ['调宿与退宿', '/admin/student-affairs/dorm/transfer'],
    ['宿舍检查', '/admin/student-affairs/dorm/check'],
    ['宿舍异常', '/admin/student-affairs/dorm/exception'],
    ['宿舍统计', '/admin/student-affairs/dorm/stats']
  ]) {
    const escapedLabel = label.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')
    const escapedPath = path.replaceAll('/', '\\/')
    assert.match(nav, new RegExp(`I\\('${escapedLabel}', '${escapedPath}', 'studentAffairs\\.dorm\\.view'`))
  }
  assert.match(routes, /path: 'dormitory'[\\s\\S]*permissionKey: 'studentAffairs\\.dorm\\.view'/)
})""",
    'modernize dorm navigation contract without weakening route or permission checks'
)

replace_once(
    'frontend/tests/navPlan.projection.test.mjs',
    """test('无独立入口但已有真实子页的学工二级模块是可展开容器，不再误报待施工', () => {
  const studentAffairs = NAV_PLAN.find((group) => group.key === 'student-affairs')
  const workbench = studentAffairs.children.find((mod) => mod.key === 'sa-workbench')
  assert.equal(workbench.path, undefined)
  assert.equal(workbench.entryType, 'CONTAINER')
  assert.equal(workbench.status, 'implemented')
  assert.equal(workbench.disabled, false)
})

test('navPlanStats 分开统计 implemented/partial/planned/unauthorized，并保留兼容字段', () => {
  const row = navPlanStats().find((item) => item.key === 'student-affairs')
  for (const key of ['implemented', 'partial', 'planned', 'unauthorized', 'containers', 'total']) {
    assert.equal(Number.isInteger(row[key]), true, `${key} 应为整数`)
  }
  assert.ok(row.containers > 0, '学工应包含无独立入口的可展开容器')
  assert.equal(row.total, row.implemented + row.partial + row.planned + row.unauthorized)
})""",
    """test('V6 学工十二个业务工作区均有真实安全落点，不再依赖无入口容器', () => {
  const studentAffairs = NAV_PLAN.find((group) => group.key === 'student-affairs')
  assert.equal(studentAffairs.children.length, 12)
  const workbench = studentAffairs.children.find((mod) => mod.key === 'sa-workbench')
  assert.equal(workbench.path, '/admin/student-affairs/dashboard')
  assert.equal(workbench.status, 'implemented')
  assert.equal(workbench.disabled, false)
  for (const workspace of studentAffairs.children) {
    assert.match(workspace.path, /^\\/admin\\//, `${workspace.key} 必须有真实站内落点`)
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
})""",
    'align projection tests with the frozen twelve-workspace V6 information architecture'
)

replace_once(
    'frontend/tests/stage-b-orientation-capability-contract.test.mjs',
    """  const orientationNav = navPlan.slice(navPlan.indexOf(\"mod('sa-orientation'\"), navPlan.indexOf(\"mod('sa-leave'\"))
  assert.match(orientationNav, /studentAffairs\\.orientation\\.view/)
  assert.doesNotMatch(orientationNav, /'orientation\\./)""",
    """  const orientationStart = navPlan.indexOf(\"mod('sa-orientation'\")
  const orientationEnd = navPlan.indexOf(\"mod('sa-mental'\", orientationStart)
  assert.ok(orientationStart >= 0 && orientationEnd > orientationStart)
  const orientationNav = navPlan.slice(orientationStart, orientationEnd)
  assert.match(orientationNav, /studentAffairs\\.orientation\\.view/)
  assert.doesNotMatch(orientationNav, /'orientation\\./)""",
    'make orientation capability contract independent of the old menu order'
)

replace_once(
    'frontend/tests/studentAffairs.permissionCatalog.test.mjs',
    """test('学生画像兼容入口使用隐藏 DETAIL + permissionAny，覆盖路由权限', async () => {
  const { nav, routes } = await sources()
  assert.match(
    nav,
    /H\\('学生360详情',\\s*'\\/admin\\/student-affairs\\/profile',\\s*null,\\s*'DETAIL',\\s*\\{\\s*permissionAny:\\s*_STU_VIEW_ANY\\s*\\}\\)/
  )
  const routePermission = routePermissionForPath(routes, 'profile')
  const escapedRoutePermission = routePermission.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')
  assert.match(nav, new RegExp(`const _STU_VIEW_ANY = \\\\[[\\\\s\\\\S]*?['\"]${escapedRoutePermission}['\"][\\\\s\\\\S]*?\\\\]`))
})""",
    """test('公共学生360为正式对象中心，旧学工画像仍是隐藏且权限安全的详情下钻', async () => {
  const { nav, routes } = await sources()
  assert.match(
    nav,
    /H\\('学生360详情',\\s*'\\/admin\\/student',\\s*null,\\s*'DETAIL',\\s*\\{[\\s\\S]{0,180}?permissionAny:\\s*_STU_VIEW_ANY[\\s\\S]{0,180}?matchPrefix:\\s*true[\\s\\S]{0,80}?\\}\\)/
  )
  assert.match(
    nav,
    /H\\('学工画像兼容详情',\\s*'\\/admin\\/student-affairs\\/profile',\\s*null,\\s*'DETAIL',\\s*\\{[\\s\\S]{0,180}?permissionAny:\\s*_STU_VIEW_ANY[\\s\\S]{0,180}?matchPrefix:\\s*true[\\s\\S]{0,80}?\\}\\)/
  )
  const routePermission = routePermissionForPath(routes, 'profile')
  const escapedRoutePermission = routePermission.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')
  assert.match(nav, new RegExp(`const _STU_VIEW_ANY = \\\\[[\\\\s\\\\S]*?['\"]${escapedRoutePermission}['\"][\\\\s\\\\S]*?\\\\]`))
})""",
    'lock the canonical Student360 plus legacy profile compatibility contract'
)

print('A1 frontend regression contracts reconciled')
