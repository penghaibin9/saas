import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { SYSTEM_MANAGEMENT_CATALOG as catalog,SYSTEM_MANAGEMENT_ITEMS as items } from '../src/modules/system/systemManagementCatalog.js'
import { getVisibleNavPlan,matchPermission,searchNavPlan } from '../src/config/navPlan.js'
import { workspacePages,restoreWorkspace,workspaceMenuItems } from '../src/components/workspace/teacherWorkspace.js'
import { optionsInstance } from './platform-workspace-test-support.mjs'
const baseline=JSON.parse(fs.readFileSync(new URL('./fixtures/system-management-d612-baseline.json',import.meta.url),'utf8'))

const schoolBaseline=baseline.filter(item=>item.key!=='sys-business-forms')
test('nine daily workspaces retain 51 school capabilities with platform forms separately owned',()=>{
  assert.deepEqual(catalog.map(g=>g.label),['管理概览','账号管理','组织与任职','角色与权限','数据任务','学校设置','流程管理','安全与审计','第三方对接','实施与交付'])
  assert.equal(baseline.length,52)
  assert.equal(items.length,51);assert.equal(new Set(items.map(x=>x.key)).size,51)
  for(const old of schoolBaseline){const current=items.find(x=>x.key===old.key);assert.ok(current,old.key)
    assert.deepEqual({key:current.key,path:current.path,permissionKey:current.permissionKey,actions:current.actions.map(a=>({key:a.key,risk:a.risk}))},old)
  }
  assert.ok(catalog.find(g=>g.key==='sys-data-tasks').items.some(x=>x.key==='sys-data-exchange'))
  assert.ok(catalog.find(g=>g.key==='sys-implementation').items.some(x=>x.key==='sys-migration-workbench'))
})
test('regrouping preserves existing page, tab and shortcut identities',()=>{
  const group=getVisibleNavPlan({permissionPatterns:['*']}).find(g=>g.key==='system')
  const pages=workspacePages(group.children)
  for(const old of schoolBaseline){const restored=restoreWorkspace({tabs:[old.path],shortcuts:[old.path]},pages)
    assert.deepEqual(restored.tabs,[old.path],old.key);assert.deepEqual(restored.shortcuts,[old.path],old.key)
  }
})

test('retired school entries are absent while platform forms keep their own permission boundary',async()=>{
  const systemRoutes=fs.readFileSync(new URL('../src/modules/system/system.routes.js',import.meta.url),'utf8')
  for(const retired of ['roles','identity-import','business-forms']) assert.ok(!systemRoutes.includes(`path: '${retired}',`),retired)
  const {default:platform}=await import('../src/modules/platform/platform.routes.js')
  const form=platform.children.find(route=>route.path==='business-forms')
  assert.equal(form.meta.permissionKey,'platform.businessForms.view')
  const pages=workspacePages(getVisibleNavPlan({permissionPatterns:['*']}).find(g=>g.key==='system').children)
  assert.ok(!pages.some(page=>page.path==='/admin/system/business-forms'))
  const restored=restoreWorkspace({tabs:['/admin/system/business-forms'],shortcuts:['/admin/system/business-forms']},pages)
  assert.ok(!restored.tabs.includes('/admin/system/business-forms'))
  assert.ok(!restored.shortcuts.includes('/admin/system/business-forms'))
})
test('old group names remain searchable without bypassing permission filters',()=>{
  const visibleGroups=new Set(['system'])
  assert.ok(searchNavPlan('身份与账号',['systemAdmin.user.import']).filter(x=>visibleGroups.has(x.groupKey)).some(x=>x.path==='/admin/system/identity-import/teachers'))
  assert.equal(searchNavPlan('身份与账号',[]).filter(x=>x.path?.startsWith('/admin/system/')).length,0)
})
test('role steps and log tabs stay reachable without occupying the default side menu',()=>{
  const pages=workspacePages(getVisibleNavPlan({permissionPatterns:['*']}).find(g=>g.key==='system').children)
  const roles=workspaceMenuItems(pages,'sys-access','/admin/system/iam?surface=roles')
  assert.equal(roles[0].path,'/admin/system/iam?surface=roles')
  assert.ok(!roles.some(item=>item.path.includes('surface=templates')))
  assert.ok(workspaceMenuItems(pages,'sys-access','/admin/system/iam?surface=roles',true).some(item=>item.path.includes('surface=templates')))
  const logs=workspaceMenuItems(pages,'sys-security-audit','/admin/system/logs?tab=operation')
  assert.ok(!logs.some(item=>item.path==='/admin/system/logs?tab=login'))
  assert.ok(searchNavPlan('登录与安全审计',['systemAdmin.audit.view']).some(item=>item.path==='/admin/system/logs?tab=login'))
})
test('limited data-task readers land on their authorized task page and highlight its new workspace',()=>{
  const {state}=optionsInstance('../src/modules/system/views/AdminSystemLayout.vue',{
    ctx:{permissionPatterns:['systemAdmin.dataExchange.viewOwn']},$route:{path:'/admin/system/data-exchange'}
  },{BasePortalLayout:{},SystemP1ClosurePanel:{},SYSTEM_MANAGEMENT_CATALOG:catalog,matchPermission,systemApi:{},installSystemAuthorityCompatibility(){}})
  assert.equal(state.menus.length,1);assert.equal(state.menus[0].path,'/admin/system/data-exchange')
  assert.equal(state.activeKey,'sys-data-tasks')
})

test('system-only search does not request student data without student-view capability',()=>{
  const source=fs.readFileSync(new URL('../src/layouts/BasePortalLayout.vue',import.meta.url),'utf8')
  const body=source.match(/workspaceStudentSearchEnabled\(\)\s*\{([\s\S]*?)\n    \},/)[1]
  const enabled=new Function('matchPermission','isAcademicTeacherContext',`return function(){${body}}`)(matchPermission,ctx=>ctx?.currentRole?.roleCode==='ACADEMIC_TEACHER')
  const ctx={useWorkspace:true,isPlatformMode:false,railActiveKey:'system',ctx:{currentRole:{roleCode:'SYS_ADMIN'},permissionPatterns:['systemAdmin.user.view']}}
  assert.equal(enabled.call(ctx),false)
  ctx.ctx.permissionPatterns=['student.profile.view'];assert.equal(enabled.call(ctx),true)
  ctx.isPlatformMode=true;assert.equal(enabled.call(ctx),false)
})
