import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { getVisibleNavPlan } from '../src/config/navPlan.js'

test('校级教师台账只向学校管理身份显示，教师本人报告入口保留',()=>{
  const permissionPatterns=['internship.stats.view','internship.guidance.view']
  const paths=role=>getVisibleNavPlan({permissionPatterns,currentRole:role}).flatMap(group=>group.children.flatMap(module=>module.children.map(page=>page.path)))
  for(const role of [{roleCode:'INTERN_MENTOR'},{roleCode:'COUNSELOR'},null]){
    const entries=paths(role);assert.ok(entries.includes('/admin/internship/my-reports'))
    assert.ok(!entries.includes('/admin/internship/teacher-reports'));assert.ok(!entries.includes('/admin/internship/teacher-management'))
  }
  for(const role of [{roleCode:'SCHOOL_ADMIN'},{roleCode:'CUSTOM_SCHOOL',baseRoleCode:'SCHOOL_ADMIN'}]){
    const entries=paths(role);assert.ok(entries.includes('/admin/internship/teacher-reports'));assert.ok(entries.includes('/admin/internship/teacher-management'))
  }
})
import { workspacePages,workspaceTokens,restoreWorkspace } from '../src/components/workspace/teacherWorkspace.js'
import { activeWorkspacePage } from '../src/components/workspace/workspaceRouting.js'
import { withInternshipBatch } from '../src/modules/internship/navigation.js'

const computed=getter=>({get value(){return getter()}})
const ref=value=>({value})

test('两个区域始终可发现，仅列真实授权身份；读取失败和迟到响应不能冒充无权',async()=>{
  const source=fs.readFileSync(new URL('../src/layouts/BasePortalLayout.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const props={ctx:{permissionPatterns:['system.overview.view','system.role.view']}}
  let fetch=async()=>({activeContextId:'system',contexts:[
    {contextId:'system',enabled:true,permissionPatterns:['system.overview.view']},
    {contextId:'business',roleName:'学校自定实习职责',enabled:true,permissionPatterns:['internship.student.view']},
    {contextId:'empty',enabled:true,permissionPatterns:[]},
    {contextId:'disabled',enabled:false,permissionPatterns:['internship.*']}
  ]})
  const vm=new Function('computed','ref','watch','onMounted','onBeforeUnmount','useRoute','useRouter','defineProps','defineEmits','workspacePages','workspaceTokens','activeWorkspacePage','getVisibleNavPlan','currentUserFromToken','fetchMyAuthContexts',
    script+'\nreturn {centers,pages,loadContexts,pendingCenter,centerContexts,contextsError,contextsLoading,roleManagementPath}')(
    computed,ref,()=>{},()=>{},()=>{},()=>({path:'/admin/system'}),()=>({}),()=>props,()=>()=>{},
    workspacePages,workspaceTokens,activeWorkspacePage,getVisibleNavPlan,()=>({}),()=>fetch())
  assert.deepEqual(vm.centers.value.map(x=>x.key),['internship','system'])
  assert.equal(vm.centers.value[0].path,'')
  assert.equal(vm.centers.value[1].path,'/admin/system')
  assert.equal(vm.roleManagementPath.value,'/admin/system/roles')
  assert.ok(!vm.pages.value.some(x=>x.path.startsWith('/admin/internship')))
  vm.pendingCenter.value={key:'internship'};await vm.loadContexts()
  assert.deepEqual(vm.centerContexts.value.map(x=>x.contextId),['business'])
  let resolveOld;fetch=()=>new Promise(resolve=>{resolveOld=resolve});const old=vm.loadContexts()
  fetch=async()=>{throw Error('身份服务暂不可用')};await vm.loadContexts()
  resolveOld({activeContextId:'system',contexts:[{contextId:'old',enabled:true,permissionPatterns:['internship.*']}]});await old
  assert.equal(vm.contextsError.value,'身份服务暂不可用')
  assert.deepEqual(vm.centerContexts.value,[])
  assert.equal(vm.contextsLoading.value,false)
})

test('开局步骤识别教职工导入及带分区业务路径，无权入口仍拒绝',()=>{
  const source=fs.readFileSync(new URL('../src/modules/system/SystemWorkspace.vue',import.meta.url),'utf8')
  const body=source.match(/function pathAllowed\(path\) \{([\s\S]*?)\n\}/)[1]
  let permissions=['system.identity-import.view','internship.student.view','internship.batch.view']
  const allowed=new Function('getVisibleNavPlan','getPermissionPatterns','path',body)
  const check=path=>allowed(getVisibleNavPlan,()=>permissions,path)
  assert.equal(check('/admin/system/identity-import/staff'),true)
  assert.equal(check('/admin/internship/batches?panel=list'),true)
  assert.equal(check('/admin/internship/students?panel=mentor'),true)
  assert.equal(check('/admin/system/roles'),false)
  permissions=[]
  assert.equal(check('/admin/system/identity-import/staff'),false)
})

test('切换进入所选区域；取消不切换，新身份读取失败离开旧工作区',async()=>{
  const source=fs.readFileSync(new URL('../src/layouts/BasePortalLayout.vue',import.meta.url),'utf8')
  const body=source.match(/async function changeRole\(target, centerKey = ''\) \{([\s\S]*?)\n\}\r?\n<\/script>/)[1]
  const targets=[],switches=[],errors=[];let cancel=false,fail=false
  const switching=ref(false),activeContext=ref('old')
  let prefix=''
  const router={resolve:path=>({href:prefix+path})}
  const run=new Function('switching','activeContext','ElMessageBox','switchAuthContext','clearPermissionPatterns','getVisibleNavPlan','request','window','ElMessage','target','centerKey','router','return (async()=>{'+body+'})()')
  const call=()=>run(switching,activeContext,{confirm:async()=>{if(cancel)throw 'cancel'}},async id=>switches.push(id),()=>{},getVisibleNavPlan,
    async()=>{if(fail)throw Error('权限服务暂不可用');return {permissionPatterns:['internship.dashboard.view','system.audit.view']}},
    {location:{assign:path=>targets.push(path)}},{error:e=>errors.push(e)},'assigned','system',router)
  cancel=true;await call();assert.deepEqual(switches,[]);assert.deepEqual(targets,[])
  cancel=false;await call();assert.equal(targets.at(-1),'/admin/system/audit')
  fail=true;await call();assert.equal(targets.at(-1),'/security/500');assert.equal(errors.at(-1),'权限服务暂不可用')
  assert.equal(switching.value,false)
  prefix='/internship';fail=false;await call();assert.equal(targets.at(-1),'/internship/admin/system/audit')
  fail=true;await call();assert.equal(targets.at(-1),'/internship/security/500')
})

test('深链初次打开的页签立即保存，随后跨中心重新挂载仍保留',()=>{
  const source=fs.readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue',import.meta.url),'utf8')
  const persistence=source.match(/^watch\(prefs,.*$/m)[0]
  const plan=getVisibleNavPlan({permissionPatterns:['internship.dashboard.view','internship.student.view','system.student.view']})
  const pages=workspacePages(plan.flatMap(group=>group.children))
  const roster=pages.find(page=>page.title==='学生名单')
  const tabs=['/admin/internship','/admin/system/students',roster.id]
  const prefs=ref({tabs}),storageKey=ref('same-school-account-role'),stored=new Map()
  const localStorage={setItem:(key,value)=>stored.set(key,value)}
  const watch=(value,callback,options)=>{if(options.immediate)callback(value.value)}
  new Function('watch','prefs','localStorage','storageKey',persistence)(watch,prefs,localStorage,storageKey)
  assert.deepEqual(restoreWorkspace(JSON.parse(stored.get(storageKey.value)||'null'),pages).tabs,tabs)
})

test('实习工作台进入默认学生名单仍归属原工作区，明确资格视图优先匹配',()=>{
  const plan=getVisibleNavPlan({permissionPatterns:['internship.student.view','internship.student.eligibility.review','system.student.view']})
  const pages=workspacePages(plan.flatMap(group=>group.children))
  const roster=activeWorkspacePage(pages,{fullPath:'/admin/internship/students?batchId=9007199254740993',query:{batchId:'9007199254740993'}})
  assert.equal(roster?.title,'学生名单')
  assert.equal(roster?.moduleKey,'in-batch-rules')
  const eligibility=activeWorkspacePage(pages,{fullPath:'/admin/internship/students?panel=eligibility&batchId=9007199254740993',query:{panel:'eligibility',batchId:'9007199254740993'}})
  assert.equal(eligibility?.title,'资格认定')
})

test('同一工作身份可跨实习和系统管理搜索，侧栏仍属于当前中心，撤权后不显示旧管理入口',()=>{
  const source=fs.readFileSync(new URL('../src/layouts/BasePortalLayout.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const route={path:'/admin/internship',fullPath:'/admin/internship'},destinations=[]
  const props={ctx:{ctxKey:'same-school-role',permissionPatterns:['internship.dashboard.view','system.student.view']},workspaceNavigate:path=>withInternshipBatch(path,'9007199254740993')}
  const vm=new Function('computed','ref','watch','onMounted','onBeforeUnmount','useRoute','useRouter','defineProps','defineEmits','workspacePages','workspaceTokens','activeWorkspacePage','getVisibleNavPlan','currentUserFromToken',
    script+'\nreturn {pages,modules,results,query,select}')(
    computed,ref,()=>{},()=>{},()=>{},()=>route,()=>({push:path=>destinations.push(path)}),()=>props,()=>()=>{},
    workspacePages,workspaceTokens,activeWorkspacePage,getVisibleNavPlan,()=>({tenantId:'1',userId:'2',currentRoleCode:'COLLEGE_ADMIN'}))
  vm.query.value='学生资料'
  assert.deepEqual(vm.results.value.map(row=>row.path),['/admin/system/students'])
  vm.select(vm.results.value[0])
  assert.deepEqual(destinations[0],{path:'/admin/system/students',query:{},hash:''},'系统管理不继承实习批次')
  assert.ok(vm.modules.value.every(row=>row.key.startsWith('in-')))
  route.path='/admin/system/students';route.fullPath=route.path
  vm.query.value='待办与进度'
  assert.deepEqual(vm.results.value.map(row=>row.path),['/admin/internship'])
  vm.select(vm.results.value[0])
  assert.equal(destinations[1].query.batchId,'9007199254740993')
  assert.ok(vm.modules.value.every(row=>row.key.startsWith('sys-')))
  props.ctx.permissionPatterns=['internship.dashboard.view']
  vm.query.value='学生资料'
  assert.deepEqual(vm.results.value,[])
  assert.ok(!vm.pages.value.some(row=>row.path.startsWith('/admin/system')))
})

test('跨中心页签从同一有效权限目录恢复，筛选保留，单中心消费者仍可用，撤权移除原页签',()=>{
  const source=fs.readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue',import.meta.url),'utf8')
  const expression=source.match(/const pages = computed\(\(\) => ([^\n]+)\)/)[1]
  const plan=getVisibleNavPlan({permissionPatterns:['internship.dashboard.view','system.student.view']})
  const props={modules:plan[0].children,workspaceModules:plan.flatMap(group=>group.children)}
  const read=new Function('props','workspacePages','return '+expression)
  const pages=read(props,workspacePages),ids=pages.filter(row=>['/admin/internship','/admin/system/students'].includes(row.path)).map(row=>row.id)
  const saved={tabs:ids,destinations:{'/admin/system/students':'/admin/system/students?binding=UNBOUND&search=000001'}}
  assert.deepEqual(restoreWorkspace(saved,pages).tabs,ids)
  props.modules=plan[1].children
  assert.deepEqual(restoreWorkspace(saved,read(props,workspacePages)).tabs,ids)
  assert.deepEqual(Object.fromEntries(new URL(restoreWorkspace(saved,read(props,workspacePages)).destinations['/admin/system/students'],'http://workspace.local').searchParams),{binding:'UNBOUND',search:'000001'})
  props.workspaceModules=plan[0].children
  assert.deepEqual(restoreWorkspace(saved,read(props,workspacePages)).tabs,['/admin/internship'])
  props.workspaceModules=null;props.modules=plan[1].children
  assert.deepEqual(read(props,workspacePages).map(row=>row.id),workspacePages(props.modules).map(row=>row.id))
})
