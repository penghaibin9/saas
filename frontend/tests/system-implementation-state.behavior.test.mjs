import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {roleDisplayLabel} from '../src/modules/system/utils/permissionLabels.js'
const root=new URL('../src/modules/system/',import.meta.url)
const descriptor=parse(fs.readFileSync(new URL('views/SystemImplementationView.vue',root),'utf8')).descriptor
function setup(api={}){
  const env={roleDisplayLabel,implementationApi:api,dataExchangeApi:{},systemApi:{},toast:{success:()=>{},error:()=>{}},
    systemConfirm:async()=>false,systemPrompt:async()=>null}
  for(const name of ['ModulePageShell','ModuleHero','StatusTag','LoadingState','ErrorState','ImplementationProjectSummary'])env[name]={}
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const c=env.component,state={...c.data(),$route:{meta:{implementationPageKey:'wizard'}},ctx:{}}
  for(const [key,fn] of Object.entries(c.methods))state[key]=fn.bind(state)
  for(const [key,fn] of Object.entries(c.computed))Object.defineProperty(state,key,{get:fn.bind(state)})
  return {state,env}
}
test('acceptance evidence uses catalog labels and never exposes unknown raw enum values',()=>{
  const {state}=setup()
  state.catalog.sections=[{code:'school_opening',questions:[{key:'schoolLevel',options:[['HIGHER_VOCATIONAL','高职']]},{key:'deliveryMode',options:[['STANDARD_WEEK','标准一周']]}]}]
  assert.equal(state.checkEvidenceText({code:'school_opening',evidence:{schoolLevel:'HIGHER_VOCATIONAL',deliveryMode:'STANDARD_WEEK',targetDays:7}}),'高职 · 标准一周 · 计划 7 天')
  assert.equal(state.configOptionLabel('school_opening','schoolLevel','UNKNOWN_INTERNAL'),'待确认')
  assert.equal(state.roleLabel('SYS_ADMIN'),'系统管理员')
  assert.equal(state.roleLabel('ACADEMIC_TEACHER'),'任课教师')
})

test('loaded recommendations are clean and version zero is a real project version',async()=>{
  const {state}=setup({catalog:async()=>({sections:[{code:'a',defaultConfig:{value:1}}]}),
    current:async()=>({id:'1',version:0,status:'CONFIGURING',progress:100,sections:[]})})
  await state.load();assert.equal(state.isDirty,false);assert.equal(await state.canLeave(),true)
  assert.equal(state.heroStats[1].label,'配置覆盖');assert.equal(state.heroStats[2].value,'0')
  state.sectionDrafts.a.value=2;assert.equal(state.isDirty,true);assert.equal(await state.canLeave(),false)
  state.sectionDrafts.a.value=1;assert.equal(state.isDirty,false)
  state.relationRollback.reason='核查历史';assert.equal(state.isDirty,true)
})
test('saving one section keeps other drafts and leaves them dirty',async()=>{
  const {state}=setup({saveSection:async()=>({id:'1',version:1,status:'CONFIGURING'})})
  state.project={id:'1',version:0,status:'CONFIGURING'};state.loading=false
  state.sectionDrafts={a:{value:1},b:{value:1}};state.draftBaseline=state.draftSnapshot()
  state.sectionDrafts.a.value=2;state.sectionDrafts.b.value=3
  await state.saveSection('a')
  assert.equal(state.sectionDrafts.b.value,3);assert.equal(state.isDirty,true)
  assert.equal(JSON.parse(state.draftBaseline).sections.a.value,2)
  assert.equal(JSON.parse(state.draftBaseline).sections.b.value,1)
})
test('failed save preserves drafts and sealed projects cannot invoke ordinary mutations',async()=>{
  let calls=0
  const {state}=setup({saveSection:async()=>{throw Error('版本已变化')}})
  state.project={id:'1',version:1,status:'CONFIGURING'};state.loading=false
  state.sectionDrafts={a:{value:1}};state.draftBaseline=state.draftSnapshot();state.sectionDrafts.a.value=2
  await state.saveSection('a');assert.equal(state.sectionDrafts.a.value,2);assert.equal(state.isDirty,true)
  state.project.acceptanceDigest='sealed-evidence'
  await state.action(async()=>{calls++},'不应写入')
  assert.equal(calls,0);assert.equal(state.isSealed,true)
})
test('both implementation views and shared summary compile',()=>{
  for(const file of ['views/SystemImplementationView.vue','views/SystemImplementationWorkspaceView.vue','components/ImplementationProjectSummary.vue']){
    const {descriptor}=parse(fs.readFileSync(new URL(file,root),'utf8'))
    assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:file,id:file}).errors,[])
  }
})

test('late installations response cannot overwrite a newer project load',async()=>{
  let finishOld, calls=0
  const old=new Promise(resolve=>{finishOld=resolve})
  const {state}=setup({catalog:async()=>({sections:[]}),
    current:async()=>({id:String(++calls),version:calls,status:'CONFIGURING',sections:[]}),
    installations:()=>calls===1?old:Promise.resolve([{id:'new'}])})
  state.$route.meta.implementationPageKey='installed'
  const first=state.load()
  await new Promise(resolve=>setImmediate(resolve))
  await state.load()
  finishOld([{id:'old'}]);await first
  assert.equal(state.project.id,'2')
  assert.equal(state.installations[0].id,'new')
  assert.equal(state.isDirty,false)
})

test('workspace counts pending policies from returned workflow records and preserves unknown',()=>{
  const script=parse(fs.readFileSync(new URL('views/SystemImplementationWorkspaceView.vue',root),'utf8')).descriptor.script.content
  const env={}
  for(const name of ['ModulePageShell','ModuleToolbar','DataTable','StatusTag','LoadingState','ErrorState','EmptyState','AppConfirmDialog','ImplementationProjectSummary'])env[name]={}
  vm.runInNewContext(script.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const computed=env.component.computed
  const state={runtimeLoaded:true,runtime:{workflows:[{policyConfirmed:false},{policyConfirmed:true},{policyConfirmed:false}]}}
  Object.defineProperty(state,'pendingPolicyCount',{get:()=>computed.pendingPolicyCount.call(state)})
  assert.equal(computed.pendingPolicyCountText.call(state),'2')
  state.runtime={};assert.equal(computed.pendingPolicyCountText.call(state),'待读取')
  state.runtime={workflows:[]};assert.equal(computed.pendingPolicyCountText.call(state),'0')
  state.project={status:'PREVIEW_READY',acceptanceDigest:'historical'}
  assert.deepEqual(Array.from(computed.toolbarActions.call(state),x=>x.key),['refresh'])
  for(const key of ['isSealed','hasFrozenChecks'])Object.defineProperty(state,key,{get:()=>computed[key].call(state)})
  assert.equal(computed.readinessTitle.call(state),'项目已封存，历史验收明细不完整')
  assert.equal(computed.readinessTone.call(state),'su-notice--warning')
  state.project.acceptanceSummary={checks:[{code:'historical'}]}
  assert.equal(computed.readinessTitle.call(state),'本项目已经验收封板')
  assert.match(computed.readinessDescription.call(state),/不代表当前学工、教务、毕业设计、岗位实习已经就绪/)
})
