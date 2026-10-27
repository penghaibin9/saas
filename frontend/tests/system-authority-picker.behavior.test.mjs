import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {parse,compileTemplate} from '@vue/compiler-sfc'
const root=new URL('../src/modules/system/',import.meta.url)
const picker=parse(readFileSync(new URL('components/AccountCandidatePicker.vue',root),'utf8')).descriptor
function setup(request){
  const env={systemApi:{getAuthorizationCandidates:request},contextFingerprint:ctx=>ctx.identity}
  vm.runInNewContext(picker.script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const emitted=[];const c=env.component
  const state={...c.data(),disabled:false,ctx:{identity:'one'},$emit:(...args)=>emitted.push(args)}
  Object.assign(state,Object.fromEntries(Object.entries(c.methods).map(([key,fn])=>[key,fn.bind(state)])))
  return {state,c,emitted}
}
test('person search uses bounded active-account query and preserves stable string identifiers',async()=>{
  let params
  const {state,emitted}=setup(async value=>{params=value;return {code:0,data:{list:[{id:'9007199254740999',name:'同名老师',userNo:'T01',orgName:'学院甲'}],total:1}}})
  state.keyword=' 同名老师 ';await state.search(1);state.choose(state.rows[0])
  assert.equal(params.keyword,'同名老师');assert.equal(params.pageSize,10);assert.equal(params.status,'ACTIVE')
  assert.equal(emitted.at(-1)[1].id,'9007199254740999')
  const before=emitted.length;state.choose({id:'forged'});assert.equal(emitted.length,before)
})
test('identity change discards pending candidate results and selected account',async()=>{
  let finish
  const {state,c,emitted}=setup(()=>new Promise(resolve=>{finish=resolve}))
  const pending=state.search(1);c.watch.contextKey.call(state)
  finish({code:0,data:{list:[{id:'old'}],total:1}});await pending
  assert.equal(state.rows.length,0);assert.equal(emitted.at(-1)[1],null)
})
test('failed candidate reads stay visible errors rather than an empty success',async()=>{
  const {state}=setup(async()=>({code:1,message:'无权读取本校人员'}));await state.search(1)
  assert.equal(state.error,'无权读取本校人员');assert.equal(state.loading,false)
})
test('shared picker and both authorization forms compile',()=>{
  for(const file of ['components/AccountCandidatePicker.vue','components/SystemP1ClosurePanel.vue','views/SystemDelegationView.vue']){
    const {descriptor}=parse(readFileSync(new URL(file,root),'utf8'))
    assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:file,id:file}).errors,[])
  }
})
function formView(file,api){
  const {descriptor}=parse(readFileSync(new URL(file,root),'utf8'))
  const env={contextFingerprint:ctx=>JSON.stringify(ctx),systemApi:api,systemP1ClosureApi:{},toast:{error:()=>{},success:()=>{}},FormFields:{validateRequired:()=>({})}}
  for(const name of ['AppButton','AccountCandidatePicker','AppDrawer','AppConfirmDialog','ModulePageShell','ModuleToolbar','DataTable','StatusTag','LoadingState','ErrorState','EmptyState'])env[name]={}
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const c=env.component
  const state={...c.data(),ctx:{permissionPatterns:['systemAdmin.user.assign']},$route:{path:'/admin/system/role-assignments'},$emit:()=>{}}
  for(const [key,fn] of Object.entries(c.methods))state[key]=fn.bind(state)
  for(const [key,fn] of Object.entries(c.computed||{}))Object.defineProperty(state,key,{get:fn.bind(state)})
  return state
}
test('uncertain formal grant preserves the reviewed account and blocks a second POST',async()=>{
  let calls=0,body
  const state=formView('components/SystemP1ClosurePanel.vue',{grantRoleAssignment:async value=>{calls++;body=value;return {code:503,bizCode:'REQUEST_TIMEOUT',message:'结果未确认'}}})
  state.rolePerson={id:'9007199254740999'};state.roleForm={roleCode:'ACADEMIC_TEACHER',reason:'独立输入保留验证',expiresAt:''}
  await state.grantRole();await state.grantRole()
  assert.equal(calls,1);assert.equal(body.userId,'9007199254740999');assert.equal(state.grantUncertain,true)
  assert.equal(state.roleForm.reason,'独立输入保留验证');assert.equal(state.rolePerson.id,'9007199254740999')
})
test('uncertain temporary grant retains input even when the dialog is reopened',async()=>{
  let calls=0
  const state=formView('views/SystemDelegationView.vue',{createDelegation:async()=>{calls++;return {code:503,bizCode:'REQUEST_TIMEOUT',message:'结果未确认'}}})
  state.person={id:'11',loginName:'fixture'};state.form.value={roleCode:'ACADEMIC_TEACHER',reason:'独立临时授权验证',expiresAt:'2099-01-01T10:00'}
  await state.submitCreate();state.openCreate();await state.submitCreate()
  assert.equal(calls,1);assert.equal(state.uncertain,true);assert.equal(state.form.value.reason,'独立临时授权验证')
})

test('formal grant recovers only after a successful targeted read and explicit acknowledgment',async()=>{
  let writes=0,reads=0
  const state=formView('components/SystemP1ClosurePanel.vue',{
    grantRoleAssignment:async()=>{writes++;return {code:503,bizCode:'REQUEST_TIMEOUT'}},
    listRoleAssignments:async params=>{reads++;assert.equal(params.userId,'11');assert.equal(params.roleCode,'ACADEMIC_TEACHER');return {code:0,data:{list:[],total:0}}}
  })
  state.rolePerson={id:'11'};state.roleForm={roleCode:'ACADEMIC_TEACHER',reason:'原申请原因保留',expiresAt:''}
  await state.grantRole();state.finishGrantCheck();assert.equal(state.grantUncertain,true)
  await state.checkGrant();state.finishGrantCheck();assert.equal(state.grantUncertain,true)
  assert.equal(writes,1);assert.equal(reads,1);assert.equal(state.roleForm.reason,'原申请原因保留')
  state.grantAcknowledged=true;state.finishGrantCheck()
  assert.equal(state.grantUncertain,false);assert.equal(state.rolePerson,null);assert.equal(state.roleForm.reason,'')
  state.rolePerson={id:'12'};state.roleForm={roleCode:'ACADEMIC_TEACHER',reason:'另一笔新的申请',expiresAt:''}
  await state.grantRole();assert.equal(writes,2)
})

test('temporary recovery preserves errors and requires acknowledgment without resending',async()=>{
  let writes=0,fail=true
  const state=formView('views/SystemDelegationView.vue',{
    createDelegation:async()=>{writes++;return {code:503,bizCode:'REQUEST_TIMEOUT'}},
    listDelegations:async()=>fail?{code:1,message:'读取失败'}:{code:0,data:{list:[{id:'5',granteeUserNo:'fixture',roleCode:'ACADEMIC_TEACHER',statusLabel:'生效中'}]}}
  })
  state.person={id:'11',loginName:'fixture'};state.form.value={roleCode:'ACADEMIC_TEACHER',reason:'临时授权原申请',expiresAt:'2099-01-01T10:00'}
  await state.submitCreate();await state.checkSubmission();state.acknowledged=true;state.finishCheck()
  assert.equal(state.uncertain,true);assert.equal(state.checkError,'读取失败')
  fail=false;await state.checkSubmission();assert.equal(state.checkedRows.length,1)
  state.finishCheck();assert.equal(state.uncertain,true);assert.equal(writes,1)
  state.acknowledged=true;state.finishCheck();assert.equal(state.uncertain,false);assert.equal(state.person,null)
  assert.equal(state.form.value.reason,'');assert.equal(writes,1)
})
