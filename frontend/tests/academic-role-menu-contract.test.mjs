import { NAV_PLAN, getVisibleNavPlan } from '../src/config/navPlan.js'
import { projectNavigationRoutePermissions } from '../src/router/navigationRouteProjection.js'
import { academicAffairsRoutes } from '../src/modules/academicAffairs/academic-affairs.routes.js'
import { Buffer } from 'node:buffer'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { academicRoleModules, academicRoleAllows, academicRoleDefaultPath, academicRoleSearchResults,
  academicRoleTabs, academicRoleActiveModule, hasAcademicRoleMenu } from '../src/modules/academicAffairs/config/academicRoleNavigation.js'
import { workspacePages, restoreWorkspace } from '../src/components/workspace/teacherWorkspace.js'
import * as gate from '../src/security/permissionGate.js'

const ROOT = '/admin/academic-affairs'
const ctx = (role, permissions = ['academicAffairs.*']) => ({ currentRole: { roleCode: role, roleType: 'ACADEMIC_STAFF' },
  permissionPatterns: permissions, moduleEntitlements: ['academicAffairs'] })
const college = ctx('COLLEGE_ACADEMIC')
const leader = ctx('LEADER', ['academicAffairs.dashboard.view', 'academicAffairs.stats.view', 'academicAffairs.stats.snapshot.view'])

test('两个岗位只投影既有入口，保留稳定叶子身份；其他岗位不接管', () => {
  assert.equal(academicRoleModules(college).length, 8)
  assert.deepEqual(academicRoleModules(leader).map(g => g.label), ['教务大屏', '统计报表'])
  const entries = academicRoleModules(leader).flatMap(g => g.children)
  assert.deepEqual(entries.map(e => e.path), [ROOT + '?wall=1', ROOT + '/stats', ROOT + '/stats?tab=snapshot'])
  for (const c of [college, leader]) for (const module of academicRoleModules(c)) for (const leaf of module.children) {
    assert.ok(leaf.leafId.startsWith('aa.'))
    assert.equal(academicRoleAllows(leaf.path, c), true, leaf.path)
    assert.equal(academicRoleActiveModule(c, leaf.path), module.key, leaf.path)
  }
  for (const role of ['ACADEMIC_TEACHER', 'ACADEMIC_ADMIN', 'COLLEGE_ADMIN', 'SCHOOL_ADMIN']) {
    assert.equal(hasAcademicRoleMenu(ctx(role)), false)
    assert.equal(academicRoleAllows(ROOT + '/scheduling', ctx(role)), true)
  }
})

test('学院办理与同对象详情可进入，筛选分页不改变岗位入口', () => {
  for (const path of ['/teaching-tasks/assign', '/teaching-tasks/123', '/courses/88/edit', '/programs/45',
    '/programs/console?tab=authoring&programId=45', '/programs/console?tab=planChange',
    '/grade-entry?taskId=87', '/schedule/teacher/teacher01?week=2', '/schedule-change/apply?originItemId=91',
    '/roster/222', '/status-changes/new?type=SUSPEND', '/status-changes/99', '/stats?tab=grade&collegeId=1&page=2']) {
    assert.equal(academicRoleAllows(ROOT + path, college), true, path)
  }
})

test('学院和领导即使误获全量权限，也不能从共用查看权限进入办理或校级页签', () => {
  const forbidden = ['/scheduling', '/schedule', '/workload-review', '/teaching-tasks/confirm',
    '/programs/console?tab=review', '/programs/console?tab=publish', '/programs/console?tab=archive',
    '/courses/console?tab=disable', '/grade-entry?action=import', '/stats?tab=export',
    '/warnings/console?tab=rules', '/status-changes/approval', '/roster/import-export']
  for (const role of ['COLLEGE_ACADEMIC', 'LEADER']) for (const path of forbidden) {
    assert.equal(academicRoleAllows(ROOT + path, ctx(role, ['*'])), false, `${role}: ${path}`)
  }
  for (const path of ['', '?panel=todos', '?wall=1&panel=gradeProgress', '/roster', '/grade-entry']) {
    assert.equal(academicRoleAllows(ROOT + path, leader), false, path)
  }
})

test('重复、编码或混合页签参数不能绕过；历史投影入口不能复活', () => {
  for (const path of ['/stats?tab=grade&tab=export', '/stats?tab=grade&action=export',
    '/stats?%74ab=export', '/programs/console?tab=authoring&panel=review',
    '/stats?_workspace=aa.stats.stats.tab.export', '/stats?tab=snapshot&_workspace=aa.grade-review.grade.publish']) {
    assert.equal(academicRoleAllows(ROOT + path, college), false, path)
  }
  assert.equal(academicRoleAllows({ path: ROOT + '/stats', query: { tab: ['grade', 'export'] } }, leader), false)
  assert.equal(academicRoleAllows('/admin/academic/grade-publish', college), false)
  assert.equal(academicRoleAllows(ROOT + '/stats?_workspace=aa.dashboard.overview', college), false)
})

test('岗位上限仍与当前权限和模块许可取交集，撤权后入口、搜索一起消失', () => {
  const onlyView = ctx('COLLEGE_ACADEMIC', ['academicAffairs.grade.view'])
  assert.equal(academicRoleAllows(ROOT + '/grade-overview', onlyView), true)
  assert.equal(academicRoleAllows(ROOT + '/grade-entry', onlyView), false)
  assert.equal(academicRoleAllows(ROOT + '/grade-entry', ctx('COLLEGE_ACADEMIC', ['academicAffairs.grade.scheme.manage'])), true)
  const noSnapshot = ctx('LEADER', ['academicAffairs.stats.view'])
  assert.equal(academicRoleDefaultPath(noSnapshot), ROOT + '/stats')
  assert.equal(academicRoleAllows(ROOT + '/stats?tab=snapshot', noSnapshot), false)
  assert.deepEqual(academicRoleModules({ ...leader, moduleEntitlements: [] }), [])
  assert.equal(academicRoleAllows(ROOT + '/stats', { ...leader, moduleEntitlements: [] }), false)
  assert.deepEqual(academicRoleModules(ctx('LEADER', [])), [])
})

test('侧栏、旧搜索别名和收藏恢复共同服从岗位规则，其他中心保持原样', () => {
  const source = [
    { kind: '功能/页面', label: '工作量审核', to: ROOT + '/workload-review' },
    { kind: '功能/页面', label: '成绩录入', to: ROOT + '/grade-entry' },
    { kind: '功能/页面', label: '课程成绩构成', to: ROOT + '/grade-entry' },
    { kind: '功能/页面', label: '其他中心', to: '/admin/student-affairs' },
    { kind: '规划', label: '审核配置', path: ROOT + '/workload-review', to: null, disabled: true }
  ]
  const found = academicRoleSearchResults(source, college)
  assert.equal(found.length, 2)
  assert.match(found[0].label, /课程成绩构成/)
  assert.equal(found[1], source[3])
  const pages = workspacePages(academicRoleModules(leader))
  const valid = pages.find(p => p.path === ROOT + '/stats').id
  const saved = { tabs: [valid, 'aa.dashboard.panel.todos'], recent: ['aa.grade-review.grade.publish'],
    shortcuts: [valid, 'aa.stats.stats.tab.export'] }
  const restored = restoreWorkspace(saved, pages)
  assert.deepEqual(restored.tabs, [valid])
  assert.deepEqual(restored.shortcuts, [valid])
  assert.deepEqual(restored.recent, [])
  assert.equal(academicRoleSearchResults(source, ctx('ACADEMIC_ADMIN')), source)
})

test('共用控制台页签使用同一规则，不能先切到隐藏页签再发请求', () => {
  const tabs = ['authoring', 'versions', 'review', 'publish', 'archive'].map(key => ({ key }))
  assert.deepEqual(academicRoleTabs(tabs, ROOT + '/programs/console', college).map(t => t.key), ['authoring', 'versions'])
  assert.equal(academicRoleTabs(tabs, ROOT + '/programs/console', ctx('ACADEMIC_ADMIN')), tabs)
  for (const name of ['AaProgramConsoleView', 'AaCourseConsoleView', 'AaWarningConsoleView']) {
    const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
    assert.match(source, /v-for="t in visibleTabs"/)
    assert.match(source, /switchTab\(k\)\s*\{\s*if \(!academicRoleAllows/)
  }
})

test('真实一级菜单缓存按岗位区分，并与角色侧栏使用同一分组', async () => {
  let source = readFileSync(new URL('../src/config/adminMenu.js', import.meta.url), 'utf8')
  for (const [alias, file] of [
    ['@/config/navPlan', '../src/config/navPlan.js'],
    ['@/security/moduleEntitlement', '../src/security/moduleEntitlement.js'],
    ['@/modules/academicAffairs/config/academicRoleNavigation', '../src/modules/academicAffairs/config/academicRoleNavigation.js']
  ]) source = source.replace(`'${alias}'`, JSON.stringify(new URL(file, import.meta.url).href))
  const menu = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
  for (const role of ['COLLEGE_ACADEMIC', 'LEADER', 'COLLEGE_ACADEMIC']) {
    const c = ctx(role, ['*'])
    const academic = menu.getVisibleAdminMenu(c).find(g => g.key === 'academic-affairs')
    assert.deepEqual(academic.children.map(g => g.key), academicRoleModules(c).map(g => g.key))
  }
})

test('真实全局路由守卫拦截直接网址和页签篡改，合法入口与角色默认页可用', async () => {
  const source = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const callback = source.slice(source.indexOf('router.beforeEach(') + 'router.beforeEach('.length, source.lastIndexOf('\n})') + 2)
  let actor = { currentRoleCode: 'LEADER' }
  const dependencies = { ...gate, getToken: () => 'test-token', currentUserFromToken: () => actor,
    request: async () => { throw Error('unexpected context request') }, isPlatformPrincipal: () => false,
    academicRoleAllows, academicRoleDefaultPath, hasAcademicRoleMenu }
  delete dependencies.default
  const factorySource = `export default dependencies => { const { ${Object.keys(dependencies).join(',')} } = dependencies; return (${callback}); }`
  const { default: makeGuard } = await import('data:text/javascript;base64,' + Buffer.from(factorySource).toString('base64'))
  const guard = makeGuard(dependencies)
  gate.clearPermissionPatterns(); gate.setPermissionPatterns(['*']); gate.setModuleEntitlements(['academicAffairs'])
  async function enter(path, query = {}) {
    let nextValue = 'not-called'
    const to = { path, query, meta: { moduleCode: 'ACADEMIC_AFFAIRS', permissionKey: 'academicAffairs.stats.view' } }
    await guard(to, {}, value => { nextValue = value })
    return { to, nextValue }
  }
  assert.ok((await enter(ROOT + '/workload-review')).to.meta.accessNotice)
  assert.ok((await enter(ROOT + '/stats', { tab: 'export' })).to.meta.accessNotice)
  assert.equal((await enter(ROOT + '/stats', { tab: 'grade' })).to.meta.accessNotice, undefined)
  assert.deepEqual((await enter(ROOT)).nextValue, { path: ROOT, query: { wall: '1' }, replace: true })
  actor = { currentRoleCode: 'COLLEGE_ACADEMIC' }
  assert.ok((await enter(ROOT + '/programs/console', { tab: 'review' })).to.meta.accessNotice)
  assert.equal((await enter(ROOT + '/programs/console', { tab: 'authoring', programId: '42' })).to.meta.accessNotice, undefined)
  actor = { currentRoleCode: 'ACADEMIC_ADMIN' }
  assert.equal((await enter(ROOT + '/workload-review')).to.meta.accessNotice, undefined)
  gate.clearPermissionPatterns()
})


test('学院补考和清考使用已有入口，仅本院成绩可见，不带出其他补重修页签', () => {
  const c = ctx('COLLEGE_ACADEMIC', ['academicAffairs.makeup.view'])
  assert.equal(academicRoleAllows(ROOT + '/makeup?tab=makeup', c), true)
  assert.equal(academicRoleAllows(ROOT + '/makeup?tab=clearance', c), true)
  assert.equal(academicRoleAllows(ROOT + '/makeup?tab=deferred', c), false)
  assert.equal(academicRoleAllows(ROOT + '/makeup?tab=exemption', c), false)
})


test('辅导员只持首审权限也能找到缓考入口，正式路由投影包含首审权限',()=>{
 const permission='academicAffairs.deferredExam.counselorReview'
 const groups=getVisibleNavPlan({permissionPatterns:[permission],ctxKey:'exam-counselor-only'})
 const leaves=groups.find(g=>g.key==='academic-affairs')?.children.flatMap(g=>g.children||[])||[]
 assert.ok(leaves.some(row=>row.leafId==='aa.exam.exam.tab.defer'))
 assert.equal(leaves.some(row=>row.leafId==='aa.exam.exam.tab.archive'),false)
 const routes=projectNavigationRoutePermissions(academicAffairsRoutes,NAV_PLAN)
 const exam=routes.find(r=>r.path==='/admin/academic-affairs').children.find(r=>r.path==='exam')
 assert.ok(exam.meta.permissionAny.includes(permission))
})

test('学院缓考入口服从当前权限，撤权后入口和地址一起被拒绝',()=>{
 const c=ctx('COLLEGE_ACADEMIC',['academicAffairs.deferredExam.review'])
 assert.ok(academicRoleModules(c).flatMap(g=>g.children).some(row=>row.leafId==='aa.exam.exam.tab.defer'))
 assert.equal(academicRoleAllows(ROOT+'/exam?tab=defer',c),true)
 c.permissionPatterns=['academicAffairs.exam.view']
 assert.equal(academicRoleAllows(ROOT+'/exam?tab=defer',c),false)
})


test('生成的能力清单保留缓考任一权限策略，不错误继承考试查看权限',()=>{
 const registry=JSON.parse(readFileSync(new URL('../../shared/generated/capability-registry.json',import.meta.url),'utf8'))
 const item=registry.capabilities.find(row=>row.path===ROOT+'/exam?tab=defer')
 assert.equal(item.permissionKey,null);assert.equal(item.permissionPolicy,'EXPLICIT')
 assert.deepEqual(item.permissionAny,['academicAffairs.deferredExam.counselorReview','academicAffairs.deferredExam.review'])
})
