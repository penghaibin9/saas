import test from 'node:test'
import assert from 'node:assert/strict'

test('师生问题筛选在工作页签保留，只接受明确账号关联状态',()=>{
  for(const path of ['/admin/system/staff','/admin/system/students']){
    assert.equal(systemContextDestination({path},path+'?binding=UNBOUND&page=2'),path+'?binding=UNBOUND&page=2')
    assert.equal(systemContextDestination({path},path+'?binding=BOUND'),path+'?binding=BOUND')
    assert.equal(systemContextDestination({path},path+'?binding=UNKNOWN'),'')
    assert.equal(systemContextDestination({path},path+'?binding=BOUND&binding=UNBOUND'),'')
  }
  const path='/admin/system/accounts'
  assert.equal(systemContextDestination({path},path+'?binding=UNBOUND'),'')
})
import fs from 'node:fs'
import { getVisibleNavPlan } from '../src/config/navPlan.js'
import { workspacePages, restoreWorkspace, systemContextDestination } from '../src/components/workspace/teacherWorkspace.js'
import { activeWorkspacePage } from '../src/components/workspace/workspaceRouting.js'
import { internshipLocation, internshipWorkspaces, internshipBatchSwitch } from '../src/modules/internship/navigation.js'

test('志愿查询和操作回读均适配中文状态，历史决定和大编号保持',async()=>{
  const original={id:'9007199254740993001',status:'NEEDS_REVISION',volunteers:[{id:'9007199254740993002',enterpriseDecision:{status:'UNKNOWN_INTERNAL',effectStatus:'ACTIVE'}}],decisionHistory:[{id:'9007199254740993003',status:'REJECTED',effectStatus:'NEW_EFFECT',reason:'原企业意见'}]}
  const before=JSON.stringify(original),source=fs.readFileSync(new URL('../src/modules/internship/api/school-volunteer.api.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const schoolVolunteerApi','const schoolVolunteerApi')+'\nreturn schoolVolunteerApi'
  const api=new Function('request',source)(async(path,options)=>!options?.method && !/\/\d+$/.test(path)?{items:[original],total:1}:original)
  for(const result of [(await api.list('31',{})).items[0],await api.detail('31','32'),await api.confirm('31','32',{}),await api.return('31','32',{})]){
    assert.equal(result.id,original.id);assert.equal(result.statusLabel,'待学生补正');assert.equal(result.volunteers[0].enterpriseDecision.statusLabel,'状态待确认');assert.equal(result.volunteers[0].enterpriseDecision.effectLabel,'退回前的企业意见')
    assert.equal(result.decisionHistory[0].effectLabel,'效力待确认');assert.equal(result.decisionHistory[0].reason,'原企业意见')
  }
  assert.equal(JSON.stringify(original),before)
})

test('学校管理台账切批次保留原工作区，角色过滤不影响静态路由归属',()=>{
  for(const path of ['/admin/internship/teacher-reports','/admin/internship/teacher-management']){
    const result=internshipBatchSwitch(path+'?batchId=1&id=99','9007199254740993002')
    assert.equal(result.path,path);assert.equal(result.query.batchId,'9007199254740993002');assert.ok(!('id' in result.query))
    const workspaces=internshipWorkspaces({permissionPatterns:['internship.stats.view'],currentRole:{roleCode:'SCHOOL_ADMIN'}})
    assert.equal(internshipLocation(path,workspaces).path,path)
  }
})
const route = fullPath => ({ fullPath, path: fullPath.split('?')[0], query: Object.fromEntries(new URL(fullPath, 'http://workspace.local').searchParams) })
test('正式详情与缺省页签保留所属菜单，特定队列与权限仍优先',()=>{
  const pages=workspacePages(getVisibleNavPlan({permissionPatterns:['*']}).find(g=>g.key==='internship').children)
  for(const [ref,title] of [['students/13045?batchId=5959','学生名单'],['batches/5959?batchId=5959','批次管理'],['enterprises/227?section=members&batchId=5959','企业库'],['positions/280/edit?batchId=5959','岗位库'],['agreements/75?batchId=5959','三方协议'],['student-evals?id=7&batchId=5959','学生与教师评价'],['scores/7?batchId=5959','综合成绩'],['archive?id=13045&batchId=5959','材料归档'],['scores?stage=appeal&batchId=5959','成绩申诉'],['students?panel=eligibility&batchId=5959','资格认定']])
    assert.equal(activeWorkspacePage(pages,route('/admin/internship/'+ref))?.title,title)
  assert.equal(activeWorkspacePage([],route('/admin/internship/students/13045?batchId=5959')),undefined)
})

test('系统管理页签只恢复允许的数字上下文，撤权或非法地址不能恢复',()=>{
  const page={id:'handoff',path:'/admin/system/scopes'},policy={id:'policy',path:'/admin/system/leave-policy'}
  const ref=page.path+'?handoffBatchId=9007199254740993&handoffSourceId=23&handoffPage=2&reason=private&token=secret'
  const safe=systemContextDestination(page,ref)
  assert.equal(safe,page.path+'?handoffBatchId=9007199254740993&handoffSourceId=23&handoffPage=2')
  assert.equal(systemContextDestination(page,'https://other.example'+ref),'')
  assert.equal(systemContextDestination(page,policy.path+'?batchId=2'),'')
  assert.equal(systemContextDestination(page,page.path+'?handoffBatchId=1&handoffBatchId=2&handoffSourceId=bad'),'')
  const saved={destinations:{handoff:ref,policy:policy.path+'?batchId=9',unknown:'/admin/system/scopes?handoffBatchId=8'}}
  assert.deepEqual(restoreWorkspace(saved,[page,policy]).destinations,{handoff:safe,policy:policy.path+'?batchId=9'})
  assert.deepEqual(restoreWorkspace(saved,[policy]).destinations,{policy:policy.path+'?batchId=9'})
  assert.deepEqual(restoreWorkspace(null,[page,policy]).destinations,{})
})

test('管理列表页签刷新后保留受限查询，排除凭据、重复或非法条件', () => {
  const pages = ['tasks', 'migration', 'delivery'].map(key => ({ id:key, path:`/admin/system/${key}` }))
  const task = `${pages[0].path}?search=000001&status=FAILED&page=2&token=secret&jobId=9`
  const saved = { destinations:{ tasks:task, migration:`${pages[1].path}?search=%E9%81%97%E7%95%99%E7%B3%BB%E7%BB%9F&page=3&status=FAILED`, delivery:`${pages[2].path}?search=%25&page=4&reason=private` } }
  assert.deepEqual(restoreWorkspace(saved, pages).destinations, {
    tasks:`${pages[0].path}?search=000001&status=FAILED&page=2`,
    migration:`${pages[1].path}?search=%E9%81%97%E7%95%99%E7%B3%BB%E7%BB%9F&page=3`,
    delivery:`${pages[2].path}?search=%25&page=4`
  })
  for (const query of ['search=1&search=2', `search=${'x'.repeat(101)}`, 'search=%00', 'status=UNKNOWN', 'page=0', 'page=-1', 'page=9999999999999999'])
    assert.equal(systemContextDestination(pages[0], `${pages[0].path}?${query}`), '')
  assert.equal(systemContextDestination(pages[0], `https://other.example${task}`), '')
  assert.deepEqual(restoreWorkspace(saved, pages.slice(1)).destinations, {
    migration:`${pages[1].path}?search=%E9%81%97%E7%95%99%E7%B3%BB%E7%BB%9F&page=3`, delivery:`${pages[2].path}?search=%25&page=4`
  })
  for (const key of ['staff', 'students', 'accounts']) {
    const page = {id:key, path:`/admin/system/${key}`}
    assert.equal(systemContextDestination(page, `${page.path}?search=000001&page=2&status=FAILED`), `${page.path}?search=000001&page=2`)
  }
  const org={id:'org',path:'/admin/system/organizations'},audit={id:'audit',path:'/admin/system/audit'}
  assert.equal(systemContextDestination(org, `${org.path}?search=0001&kind=majors&page=2&jobId=9`), `${org.path}?search=0001&kind=majors&page=2`)
  assert.equal(systemContextDestination(org, `${org.path}?kind=unknown`), '')
  const dates='search=497&start=2026-10-08T04%3A50&end=2026-10-08T04%3A55%3A00&page=2'
  assert.equal(systemContextDestination(audit, `${audit.path}?${dates}&token=secret`), `${audit.path}?${dates}`)
  assert.equal(systemContextDestination(audit, `${audit.path}?start=invalid&end=2026-13-08T04:55&page=-1`), '')
})

test('工作区原生fieldset禁用正文不误报未保存，可编辑草稿仍确认离开', async () => {
  const source = fs.readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue', import.meta.url), 'utf8')
  const body = source.match(/async function confirmUnsubmitted\(to, from\) \{([\s\S]*?)\n\}\nonBeforeRouteLeave/)[1]
  let confirmations = 0
  const field = { readOnly: false, disabled: false, value: '实际已保存的正文', matches: selector => selector === ':disabled', getClientRects: () => [1] }
  const check = new Function('document', 'window', 'systemConfirm', `return async (to, from) => {${body}}`)(
    { querySelectorAll: () => [field] }, {}, async () => { confirmations++; return false })
  assert.equal(await check({ path: '/detail' }, { path: '/form' }), true)
  assert.equal(confirmations, 0)
  field.matches = () => false
  assert.equal(await check({ path: '/detail' }, { path: '/form' }), false)
  assert.equal(confirmations, 1)
})
test('协议模板与异常详情继承业务菜单，额外批次不会丢失高亮', () => {
  const pages = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.agreement.view', 'internship.attendance.view'] }).find(item => item.key === 'internship')?.children || [])
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/agreement-templates/9/edit?batchId=23')).title, '三方协议')
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/exceptions?batchId=23')).title, '异常核验')
})

test('报告列表、原单批阅与过程报告详情保持同一菜单，撤权不能恢复', () => {
  const context = { permissionPatterns: ['internship.report.view'] }
  const pages = workspacePages(getVisibleNavPlan(context).find(item => item.key === 'internship')?.children || [])
  const denied = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.archive.view'] }).find(item => item.key === 'internship')?.children || [])
  for (const ref of ['/admin/internship/reports?panel=review&batchId=5041', '/admin/internship/reports/2113?panel=review&batchId=5041&page=2', '/admin/internship/process-reports/56?batchId=5041']) {
    assert.equal(activeWorkspacePage(pages, route(ref)).title, '报告批阅')
    assert.equal(internshipLocation(ref, internshipWorkspaces(context)).label, '报告批阅')
    assert.equal(activeWorkspacePage(denied, route(ref)), undefined)
  }
})
test('请假所有办理视图与原单深链都归属同一菜单，未授权仍不识别', () => {
  const context = { permissionPatterns: ['internship.leave.view'] }
  const modules = getVisibleNavPlan(context).find(item => item.key === 'internship')?.children || []
  const pages = workspacePages(modules)
  for (const panel of ['', 'pending', 'approved', 'return', 'all']) {
    const ref = '/admin/internship/leaves?batchId=9007199254740993001&id=3&keyword=000123&page=2' + (panel ? '&panel=' + panel : '')
    assert.equal(activeWorkspacePage(pages, route(ref)).title, '请假与返岗')
    const owner = internshipLocation(ref, internshipWorkspaces(context))
    assert.equal(owner.workspaceKey, 'in-attendance-leave'); assert.equal(owner.label, '请假与返岗')
    const denied = getVisibleNavPlan({ permissionPatterns: ['internship.archive.view'] }).find(item => item.key === 'internship')?.children || []
    assert.equal(activeWorkspacePage(workspacePages(denied), route(ref)), undefined)
  }
})
test('工作区按照当前权限建立菜单，撤权后移除旧页签及收藏', () => {
  const allowed = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.agreement.view'] }).find(item => item.key === 'internship')?.children || [])
  assert.ok(allowed.length)
  assert.ok(allowed.every(item => item.permissionKey === 'internship.agreement.view'))
  const restored = restoreWorkspace({ tabs: [allowed[0].id, '/admin/other-school'], shortcuts: ['/admin/other-school', allowed[0].id] }, allowed)
  assert.deepEqual(restored.tabs, [allowed[0].id])
  assert.deepEqual(restored.shortcuts, [allowed[0].id])
  assert.deepEqual(restoreWorkspace(restored, []).tabs, [])
})

test('指导巡访四个办理页签及原单深链保持同一导航身份，撤权后不可恢复', () => {
  const context = { permissionPatterns: ['internship.guidance.view'] }
  const pages = workspacePages(getVisibleNavPlan(context).find(item => item.key === 'internship')?.children || [])
  const guidance = activeWorkspacePage(pages, route('/admin/internship/guidance?panel=guidance'))
  const denied = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.archive.view'] }).find(item => item.key === 'internship')?.children || [])
  for (const panel of ['guidance', 'communication', 'visit', 'visit-plan']) {
    const ref = '/admin/internship/guidance?panel='+panel+'&batchId=9007199254740993001&id=1&keyword=000123&page=2'
    const current = activeWorkspacePage(pages, route(ref))
    assert.equal(current.id, guidance.id); assert.equal(current.moduleKey, guidance.moduleKey)
    assert.equal(internshipLocation(ref, internshipWorkspaces(context)).label, '指导巡访')
    assert.equal(activeWorkspacePage(denied, route(ref)), undefined)
  }
  for (const type of ['guidance', 'visit']) {
    const ref = '/admin/internship/guidance/new?type='+type+'&batchId=9007199254740993001'
    assert.equal(activeWorkspacePage(pages, route(ref)).id, guidance.id)
    assert.equal(internshipLocation(ref, internshipWorkspaces(context)).label, '指导巡访')
    assert.equal(activeWorkspacePage(denied, route(ref)), undefined)
  }
  const saved = { tabs: [guidance.id], shortcuts: [guidance.id] }
  assert.deepEqual(restoreWorkspace(saved, denied).tabs, [])
  assert.deepEqual(restoreWorkspace(saved, denied).shortcuts, [])
})
test('业务筛选与批次参数保留准确高亮，详情不误认总览', () => {
  const pages = workspacePages([{ key: 'students', label: '学生', children: [{ path: '/admin/internship/students?panel=roster', label: '名单' }, { path: '/admin/internship/students?panel=eligibility', label: '资格' }] }, { key: 'home', label: '今日工作', children: [{ path: '/admin/internship', label: '总览' }] }])
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/students?batchId=23&page=2&panel=eligibility')).title, '资格')
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/agreements/3?batchId=23')), undefined)
})
test('重复菜单地址只接受同一页面的有效工作区标识', () => {
  const pages = workspacePages([{ key: 'first', label: '一级', children: [{ path: '/admin/internship/agreements', label: '协议' }] }, { key: 'second', label: '二级', children: [{ path: '/admin/internship/agreements', label: '复核' }] }])
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/agreements?batchId=23&_workspace=second%3A%E5%A4%8D%E6%A0%B8')).title, '复核')
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/students?_workspace=second%3A%E5%A4%8D%E6%A0%B8')), undefined)
})
test('未授权身份的菜单为空，存储不能恢复被撤销页面', () => {
  const modules = getVisibleNavPlan({ permissionPatterns: [] }).find(item => item.key === 'internship')?.children || []
  assert.equal(workspacePages(modules).length, 0)
  assert.deepEqual(restoreWorkspace({ tabs: ['/admin/internship'], shortcuts: ['/admin/internship'] }, []).shortcuts, [])
})
test('材料收件深链刷新属于材料归档，批次切换不误入今日工作或学生配置', () => {
  const context = { permissionPatterns: ['internship.archive.view'] }
  const modules = getVisibleNavPlan(context).find(item => item.key === 'internship')?.children || []
  const pages = workspacePages(modules)
  const ref = '/admin/internship/material-requirements?batchId=9007199254740993001'
  assert.equal(activeWorkspacePage(pages, route(ref)).title, '材料归档')
  const owner = internshipLocation(ref, internshipWorkspaces(context))
  assert.equal(owner.workspaceKey, 'in-archive-stats'); assert.equal(owner.label, '材料归档')
  assert.equal(activeWorkspacePage(workspacePages([]), route(ref)), undefined)
})
