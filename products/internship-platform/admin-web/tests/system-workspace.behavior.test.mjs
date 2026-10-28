import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function workspace({getResult,saveResult,visiblePaths=[]}={}) {
  const source=fs.readFileSync(new URL('../src/modules/system/SystemWorkspace.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const route={meta:{resource:'audit'},query:{search:'修改学校配置',page:'2',start:'2026-10-07T09:00'},fullPath:'/audit?initial'}
  const requests=[],writes=[],pushes=[]
  let changed
  const navigate=query=>{
    route.query=Object.fromEntries(Object.entries(query).filter(([,value])=>value!==undefined))
    route.fullPath='/audit?'+new URLSearchParams(route.query)
    changed()
  }
  const router={push:async target=>pushes.push(target),replace:async({query})=>{
    const path='/audit?'+new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([,value])=>value!==undefined)))
    if(path!==route.fullPath)navigate(query)
  }}
  const vm=new Function('ref','computed','watch','useRoute','useRouter','ElLoading','get','save','download','getPermissionPatterns','getVisibleNavPlan','matchPermission',script+
    '\nreturn {keyword,page,auditStart,auditEnd,orgKind,reset,setPage,submit,conflict,filesReady,form,edit,accountEdit,refreshImpact,impact,editLoading,opened,formError,receipt,saving,readOnly,taskStatus,dialogTitle,actionLabel,accountStatus,pathAllowed,exportPeople,issueType,issuePage,scopeType,scopeRefId,setIssuePage,focusResponsibility,scopeReviewOnly,retiringScope,blockedPage,setBlockedPage,data,exporting,error,retryExport}')(
    value=>({value}),getter=>({get value(){return getter()}}),(getter,callback)=>{changed=callback;callback()},
    ()=>route,()=>router,{directive:{}},async(path,params)=>{requests.push({path,params});return getResult ? getResult(path,params) : {items:[],total:90}},
    async(...args)=>{writes.push(args);return saveResult ? saveResult(...args) : {}},async(...args)=>{writes.push(args)},()=>[],()=>[{children:[{children:visiblePaths.map(path=>({path}))}]}],()=>false)
  return {vm,route,requests,writes,navigate,pushes}
}

test('大批量按原筛选排队，重复点击只发一次，失败保持筛选且迟到结果不跳走',async()=>{
  let complete
  const {vm,route,writes,pushes,navigate}=workspace({saveResult:()=>new Promise(resolve=>{complete=resolve})})
  route.meta.resource='student';navigate({binding:'UNBOUND',search:'容量'})
  await Promise.resolve();vm.data.value={total:5001,items:[]}
  const first=vm.exportPeople();await vm.exportPeople()
  assert.equal(writes.length,1)
  assert.deepEqual(writes[0],['/exports/student',{keyword:'容量',accountStatus:'UNBOUND'}])
  complete({id:'9007199254740993'});await first
  assert.deepEqual(pushes,[{path:'/admin/system/tasks',query:{search:'9007199254740993'}}])
  vm.data.value={total:5001,items:[]}
  const pending=vm.exportPeople();route.meta.resource='audit';navigate({})
  complete({id:'late'});await pending
  assert.equal(pushes.length,1);assert.equal(vm.exporting.value,false)
  const failed=workspace({saveResult:()=>{throw new Error('导出登记失败')}})
  failed.route.meta.resource='student';failed.navigate({search:'保留筛选'})
  await Promise.resolve();failed.vm.data.value={total:5001,items:[]}
  await failed.vm.exportPeople()
  assert.equal(failed.vm.error.value,'导出登记失败');assert.equal(failed.vm.keyword.value,'保留筛选')
  assert.deepEqual(failed.pushes,[])
})

test('概览问题深链恢复人员账号关联条件，查询与导出一致且离开人员页清除条件',async()=>{
  const {vm,route,navigate,requests,writes}=workspace({visiblePaths:['/admin/system/students']})
  route.meta.resource='student';navigate({binding:'UNBOUND',search:'001',page:'2'})
  assert.equal(vm.accountStatus.value,'UNBOUND')
  assert.deepEqual(requests.at(-1),{path:'/people/student',params:{page:2,pageSize:30,keyword:'001',accountStatus:'UNBOUND'}})
  assert.equal(vm.pathAllowed('/admin/system/students?binding=UNBOUND'),true)
  assert.equal(vm.pathAllowed('/admin/system/accounts?binding=UNBOUND'),false)
  await vm.exportPeople()
  assert.deepEqual(writes.at(-1),['/exports/student','学生资料导出.xlsx',{keyword:'001',accountStatus:'UNBOUND'}])
  vm.accountStatus.value='BOUND';await vm.reset()
  assert.equal(route.query.binding,'BOUND');assert.equal(route.query.page,undefined)
  route.meta.resource='staff';navigate({binding:'UNBOUND'})
  assert.equal(requests.at(-1).path,'/people/staff');assert.equal(requests.at(-1).params.accountStatus,'UNBOUND')
  route.meta.resource='task';navigate({binding:'UNBOUND',status:'FAILED'})
  assert.equal(vm.accountStatus.value,'');assert.equal(requests.at(-1).params.accountStatus,undefined)
  await vm.reset();assert.equal(route.query.binding,undefined)
  route.meta.resource='student';navigate({binding:'unknown'})
  assert.equal(vm.accountStatus.value,'');assert.equal(requests.at(-1).params.accountStatus,'')
})

test('任务编号和状态查询同步地址，刷新恢复，切换资料页面清除任务状态',async()=>{
  const {vm,route,navigate,requests}=workspace()
  route.meta.resource='task';navigate({search:'0017',status:'FAILED',page:'2'})
  assert.equal(vm.taskStatus.value,'FAILED')
  assert.deepEqual(requests.at(-1),{path:'/tasks',params:{page:2,pageSize:30,keyword:'0017',status:'FAILED'}})
  vm.taskStatus.value='SUCCESS';await vm.reset()
  assert.equal(route.query.status,'SUCCESS');assert.equal(route.query.page,undefined)
  assert.equal(requests.at(-1).params.status,'SUCCESS')
  route.meta.resource='migration';navigate({search:'原始资料',status:'SUCCESS'})
  assert.equal(vm.taskStatus.value,'')
  assert.equal(requests.at(-1).path,'/records/MIGRATION')
  assert.equal(requests.at(-1).params.keyword,'原始资料')
  assert.equal(requests.at(-1).params.status,undefined)
  await vm.reset();assert.equal(route.query.status,undefined)
  route.meta.resource='task';navigate({status:'UNKNOWN'})
  assert.equal(vm.taskStatus.value,'');assert.equal(requests.at(-1).params.status,'')
})

test('迁移登记详情可只读核对，禁止提交，维护时保留映射和异常记录',async()=>{
  const {vm,route,navigate,writes}=workspace()
  route.meta.resource='migration';navigate({})
  const row={id:'17',version:2,title:'合成迁移批次',details:{mappingRules:'按原代码对应',identityMapping:'旧C01对应新C01',exceptionResolution:'无待处理异常'}}
  await vm.edit(row,true)
  assert.equal(vm.readOnly.value,true)
  assert.equal(vm.form.value.mappingRules,row.details.mappingRules)
  await vm.submit();assert.equal(writes.length,0)
  await vm.edit(row)
  assert.equal(vm.readOnly.value,false)
  vm.form.value.reason='补充合成迁移登记'
  await vm.submit()
  assert.equal(writes[0][0],'/records/MIGRATION/17')
  for(const key of Object.keys(row.details))assert.equal(writes[0][1][key],row.details[key])
})

test('账号有效期使用绝对时刻回填，原样保存及长期有效不改变含义',async()=>{
  const {vm,route,navigate,writes}=workspace()
  route.meta.resource='account';navigate({})
  vm.accountEdit({id:'17',version:2,name:'合成教师',loginName:'T001',expiresAt:'2030-10-08T10:30:00Z'},'EXPIRY')
  assert.ok(vm.form.value.expiresAt instanceof Date)
  assert.equal(vm.form.value.expiresAt.toISOString(),'2030-10-08T10:30:00.000Z')
  await vm.submit()
  assert.equal(writes[0][1].expiresAt,'2030-10-08T10:30:00.000Z')
  vm.accountEdit({id:'17',version:3,expiresAt:null},'EXPIRY')
  await vm.submit()
  assert.equal(writes[1][1].expiresAt,null)
})

test('解锁提交保持明确动作，状态变化拒绝时保留原因，不自动改为启用',async()=>{
  const {vm,route,navigate,writes}=workspace({saveResult:()=>{throw new Error('只有已锁定账号可解锁；停用账号请明确办理启用')}})
  route.meta.resource='account';navigate({})
  vm.accountEdit({id:'17',version:2,name:'合成教师',loginName:'T001',status:'LOCKED'},'UNLOCK')
  assert.equal(vm.dialogTitle.value,'解锁用户账号')
  vm.form.value.reason='已核对合成账号锁定原因'
  await vm.submit()
  assert.equal(writes[0][0],'/accounts/17/actions')
  assert.equal(writes[0][1].action,'UNLOCK')
  assert.equal(writes[0][1].expectedVersion,2)
  assert.equal(vm.form.value.action,'UNLOCK')
  assert.equal(vm.form.value.reason,'已核对合成账号锁定原因')
  assert.equal(vm.opened.value,true)
  assert.match(vm.formError.value,/停用账号请明确办理启用/)
  assert.equal(vm.actionLabel('ACCOUNT_UNLOCK'),'解锁账号')
  vm.accountEdit({id:'17',version:3,status:'DISABLED'},'ENABLE')
  assert.equal(vm.dialogTitle.value,'启用用户账号')
})

test('有效期冲突按时刻比较，日期对象与带时区文本一致，差异使用中文时间',()=>{
  const source=fs.readFileSync(new URL('../src/modules/system/ConflictReview.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const props={conflict:{current:{expiresAt:'2030-10-08T10:30:00Z'}},input:{expiresAt:new Date('2030-10-08T18:30:00+08:00')}}
  const vm=new Function('computed','defineProps','defineEmits',script+'\nreturn {rows}')(getter=>({get value(){return getter()}}),()=>props,()=>{})
  assert.deepEqual(vm.rows.value,[])
  props.input.expiresAt=null
  assert.deepEqual(vm.rows.value,[{key:'expiresAt',label:'有效期',current:new Date('2030-10-08T10:30:00Z').toLocaleString('zh-CN'),input:'长期有效'}])
})

test('列表深链恢复筛选及分页，同页返回恢复查询和日期',async()=>{
  const {vm,route,requests,navigate}=workspace()
  assert.equal(vm.page.value,2)
  assert.equal(vm.keyword.value,'修改学校配置')
  assert.equal(requests.at(-1).params.startAt,new Date('2026-10-07T09:00').toISOString())
  await vm.setPage(3)
  assert.equal(route.query.page,'3')
  assert.equal(requests.at(-1).params.page,3)
  vm.keyword.value='登录'
  await vm.reset()
  assert.equal(vm.page.value,1)
  assert.equal(route.query.page,undefined)
  navigate({search:'修改学校配置',page:'2',start:'2026-10-07T09:00',end:'2026-10-07T18:00'})
  assert.equal(vm.keyword.value,'修改学校配置')
  assert.equal(vm.page.value,2)
  assert.equal(vm.auditEnd.value,'2026-10-07T18:00')
  assert.equal(requests.at(-1).params.keyword,'修改学校配置')
  const count=requests.length
  await vm.setPage(2)
  assert.equal(requests.length,count+1,'相同查询仍可主动刷新，不能重复请求')
})

test('切换页面清除审计日期并拒绝无效页码',()=>{
  const {vm,route,requests,navigate}=workspace()
  route.meta.resource='org'
  navigate({kind:'classes',page:'-5'})
  assert.equal(vm.page.value,1)
  assert.equal(vm.auditStart.value,'')
  assert.equal(vm.auditEnd.value,'')
  assert.equal(requests.at(-1).path,'/organizations/classes')
  assert.equal(requests.at(-1).params.startAt,undefined)
})

test('维护表单提交函数阻止未核对冲突和未就绪附件',async()=>{
  const {vm,writes}=workspace()
  vm.form.value={title:'保留输入'}
  vm.conflict.value={version:2}
  await vm.submit()
  vm.conflict.value=null;vm.filesReady.value=false
  await vm.submit()
  assert.equal(writes.length,0)
  assert.equal(vm.form.value.title,'保留输入')
})

test('人员影响预览不能跨人员或跨页面回填，加载期间不能保存',async()=>{
  let first,second
  const {vm,route,navigate,writes}=workspace({getResult:path=>path.endsWith('/1/impact') ? new Promise(resolve=>{first=resolve}) : path.endsWith('/2/impact') ? new Promise(resolve=>{second=resolve}) : {items:[],total:0}})
  route.meta.resource='student';navigate({})
  const old=vm.edit({id:'1',name:'原学生'}),current=vm.edit({id:'2',name:'当前学生'})
  await vm.submit();assert.equal(writes.length,0)
  first({internshipCount:99});await old
  assert.equal(vm.impact.value,null);assert.equal(vm.editLoading.value,true)
  route.meta.resource='org';navigate({kind:'classes'})
  second({internshipCount:1});await current
  assert.equal(vm.opened.value,false);assert.equal(vm.impact.value,null)
})

test('人员影响读取失败保留输入且不能勾选确认绕过提交',async()=>{
  const {vm,route,navigate,writes}=workspace({getResult:path=>{if(path.endsWith('/impact'))throw new Error('无法核对关联事项');return {items:[],total:0}}})
  route.meta.resource='staff';navigate({})
  await vm.edit({id:'1',name:'原教师'})
  vm.form.value.name='保留姓名';vm.form.value.confirmImpact=true
  await vm.submit()
  assert.equal(writes.length,0);assert.equal(vm.form.value.name,'保留姓名');assert.equal(vm.formError.value,'无法核对关联事项')
})

test('保存期间离开原工作区，迟到回执不能关闭新表单或覆盖新页面',async()=>{
  let complete
  const {vm,route,navigate}=workspace({saveResult:()=>new Promise(resolve=>{complete=resolve})})
  route.meta.resource='org';navigate({})
  await vm.edit({id:'1',name:'原学院'})
  const old=vm.submit()
  navigate({kind:'classes'})
  await vm.edit({id:'2',name:'当前班级'})
  complete({message:'旧学院已保存'});await old
  assert.equal(vm.form.value.name,'当前班级');assert.equal(vm.opened.value,true);assert.equal(vm.receipt.value,'');assert.equal(vm.saving.value,false)
})

test('停用有引用组织必须确认当前核对，重新核对保留输入并撤销旧确认',async()=>{
  let revision=1
  const {vm,route,navigate,writes}=workspace({getResult:path=>path.endsWith('/impact') ? {hasReferences:true,fingerprint:'review-'+revision,items:[]} : {items:[],total:0}})
  route.meta.resource='org';navigate({kind:'colleges'})
  await vm.edit({id:'1',name:'学院',status:'ACTIVE'})
  vm.form.value.status='DISABLED';vm.form.value.reason='保留的停用原因'
  await vm.submit();assert.equal(writes.length,0)
  vm.form.value.confirmImpact=true;revision=2
  await vm.refreshImpact()
  assert.equal(vm.form.value.confirmImpact,false);assert.equal(vm.form.value.reason,'保留的停用原因')
  await vm.submit();assert.equal(writes.length,0)
  vm.form.value.confirmImpact=true;await vm.submit()
  assert.equal(writes[0][1].impactFingerprint,'review-2')
})

test('专业和班级调整上级组织必须核对并确认，提交绑定当前引用版本',async()=>{
  for(const kind of ['majors','classes']){
    const {vm,route,navigate,writes}=workspace({getResult:path=>path.endsWith('/impact')?{parentId:'10',hasReferences:true,fingerprint:'current-impact',items:[]}:{items:[],total:0}})
    route.meta.resource='org';navigate({kind})
    await vm.edit({id:'1',version:3,name:'原组织',parentId:'10'})
    vm.form.value.parentId='20';vm.form.value.reason='核对当前学生归属调整'
    await vm.submit();assert.equal(writes.length,0)
    vm.form.value.confirmImpact=true;await vm.submit()
    assert.equal(writes[0][1].parentId,'20');assert.equal(writes[0][1].impactFingerprint,'current-impact')
    assert.equal(writes[0][1].expectedVersion,3)
  }
})

test('原责任影响读取失败禁止保存，重试保留调整内容且不加入无关提交字段',async()=>{
  let failed=true
  const {vm,route,navigate,writes}=workspace({getResult:path=>{
    if(path.endsWith('/impact')){if(failed)throw new Error('无法核对原责任');return {scopeId:'3',original:{},roleImpact:null}}
    return {items:[],total:0}
  }})
  route.meta.resource='scope';navigate({})
  await vm.edit({id:'3',userId:'4',scopeType:'COLLEGE',refId:'5'})
  vm.form.value.status='DISABLED';vm.form.value.reason='保留撤回原因'
  await vm.submit();assert.equal(writes.length,0)
  assert.equal(vm.formError.value,'无法核对原责任')
  failed=false;await vm.refreshImpact();await vm.submit()
  assert.equal(writes[0][0],'/scopes/3');assert.equal(writes[0][1].status,'DISABLED')
  assert.equal(writes[0][1].reason,'保留撤回原因');assert.equal('confirmImpact' in writes[0][1],false)
})

test('更换责任关系时旧原责任预览不回填，也不能放开新表单保存',async()=>{
  let first,second
  const {vm,route,navigate,writes}=workspace({getResult:path=>path.endsWith('/1/impact') ? new Promise(resolve=>{first=resolve}) : path.endsWith('/2/impact') ? new Promise(resolve=>{second=resolve}) : {items:[],total:0}})
  route.meta.resource='scope';navigate({})
  const old=vm.edit({id:'1',userId:'11'});await Promise.resolve();await Promise.resolve()
  const current=vm.edit({id:'2',userId:'22'});await Promise.resolve();await Promise.resolve()
  first({scopeId:'1'});await old;await vm.submit()
  assert.equal(vm.impact.value,null);assert.equal(writes.length,0)
  second({scopeId:'2'});await current;await vm.submit()
  assert.equal(writes[0][0],'/scopes/2');assert.equal(writes[0][1].userId,'22')
})


test('责任问题按地址恢复条件与分页，定位同一稳定对象，返回保留问题位置',async()=>{
  const {vm,route,navigate,requests}=workspace()
  route.meta.resource='scope';navigate({issue:'MISSING',issuePage:'2'})
  assert.equal(vm.issuePage.value,2)
  assert.equal(requests.at(-1).params.issueType,'MISSING')
  await vm.focusResponsibility({id:'9007199254740993',scopeType:'CLASS'})
  assert.equal(route.query.refId,'9007199254740993')
  assert.equal(route.query.issuePage,'2')
  assert.equal(requests.at(-1).params.scopeType,'CLASS')
  assert.equal(requests.at(-1).params.refId,'9007199254740993')
  await vm.focusResponsibility(null)
  assert.equal(route.query.refId,undefined);assert.equal(route.query.issuePage,'2')
  vm.issueType.value='DUPLICATE';await vm.setIssuePage(1)
  assert.equal(route.query.issue,'DUPLICATE');assert.equal(route.query.issuePage,undefined)
  route.meta.resource='staff';navigate({issue:'DUPLICATE',issuePage:'2',scopeType:'CLASS',refId:'17'})
  assert.equal(vm.scopeRefId.value,'');assert.equal(vm.issueType.value,'');assert.equal(vm.issuePage.value,1)
  await vm.reset();assert.equal(route.query.scopeType,undefined);assert.equal(requests.at(-1).params.refId,undefined)
})

test('为已核对对象新增责任保留稳定类型与编号，不误作原关系更新',async()=>{
  const {vm,route,navigate,writes}=workspace({getResult:()=>({items:[]})})
  route.meta.resource='scope';navigate({scopeType:'CLASS',refId:'9007199254740993'})
  await vm.edit({scopeType:'CLASS',refId:'9007199254740993',name:'同名班级'})
  assert.equal(vm.form.value.scopeType,'CLASS');assert.equal(vm.form.value.refId,'9007199254740993')
  assert.equal(vm.form.value.id,undefined);assert.equal(vm.form.value.userId,'')
  assert.equal(writes.length,0)
})


test('历史待核对条件随地址恢复和分页，离开工作区清除',async()=>{
  const {vm,route,navigate,requests}=workspace()
  route.meta.resource='scope';navigate({review:'1',page:'2'})
  assert.equal(vm.scopeReviewOnly.value,true);assert.equal(requests.at(-1).params.reviewOnly,true)
  await vm.setPage(3);assert.equal(route.query.review,'1');assert.equal(requests.at(-1).params.page,3)
  await vm.focusResponsibility({id:'17',scopeType:'COLLEGE'})
  assert.equal(vm.scopeReviewOnly.value,false);assert.equal(route.query.review,undefined)
  assert.equal(requests.at(-1).params.reviewOnly,false)
  vm.scopeReviewOnly.value=false;await vm.reset();assert.equal(route.query.review,undefined)
  route.meta.resource='staff';navigate({review:'1'});assert.equal(vm.scopeReviewOnly.value,false)
})

test('停用未定位历史关系先核对原资料，只提交版本原因，不补写人员对象或授予身份',async()=>{
  const {vm,route,navigate,requests,writes}=workspace({getResult:path=>path.endsWith('/impact')?{scopeId:'17',original:{name:'历史姓名',refName:'历史同名组织'},roleImpact:null}: {items:[]}})
  route.meta.resource='scope';navigate({review:'1'})
  await vm.edit({id:'17',version:4,status:'REVIEW',userId:'',refId:'',scopeType:'COLLEGE'},false,true)
  assert.equal(vm.dialogTitle.value,'停用待核对责任关系');assert.equal(vm.impact.value.scopeId,'17')
  assert.equal(requests.some(r=>r.path==='/roles'),false)
  vm.form.value.reason='核对原资料后确认不再使用此关系'
  await vm.submit()
  assert.deepEqual(writes[0],['/scopes/17/retire',{expectedVersion:4,reason:'核对原资料后确认不再使用此关系'},'POST'])
  await vm.edit({id:'18',version:1,status:'ACTIVE',userId:'2',refId:'3',scopeType:'COLLEGE'})
  assert.equal(vm.retiringScope.value,false)
})


test('异常待办分页同步地址并恢复，进入其他页面不携带查询参数',async()=>{
  const {vm,route,navigate,requests}=workspace()
  route.meta.resource='scope';navigate({blocked:'1',blockedPage:'2'})
  assert.equal(vm.blockedPage.value,2);assert.equal(requests.at(-1).params.blockedPage,2)
  await vm.setBlockedPage(3);assert.equal(route.query.blockedPage,'3')
  await vm.setBlockedPage(1);assert.equal(route.query.blockedPage,undefined)
  route.meta.resource='staff';navigate({blockedPage:'4'})
  assert.equal(vm.blockedPage.value,1);assert.equal(requests.at(-1).params.blockedPage,undefined)
})
