import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {formatDateTime} from '../src/utils/dateUtils.js'
import {safeEnumLabel} from '../src/utils/presentationSafety.js'
import {contextFingerprint} from '../src/modules/system/utils/workspaceContract.js'

const {descriptor}=parse(readFileSync(new URL('../src/modules/system/views/SystemJobCenterView.vue',import.meta.url),'utf8'))
function component(api){
  const env={systemApi:api,toast:{success(){},error(){}},safeEnumLabel,formatDateTime,contextFingerprint,WorkspaceConfirmDialog:{}}
  for(const name of ['ModulePageShell','ModuleToolbar','DataTable','StatusTag','LoadingState','ErrorState','EmptyState'])env[name]={}
  vm.runInNewContext(descriptor.script.content.replace(/^import[^\n]+\n/gm,'').replace('export default','globalThis.component='),env)
  return env.component
}
test('unsupported, completed and busy actions cannot submit requests',async()=>{
  let calls=0
  const c=component({retryJob:async()=>{calls++;return{code:0}},cancelJob:async()=>{calls++;return{code:0}}})
  const state={...c.data(),ctx:{},load:async()=>{}}
  const row={jobId:'EXPORT:1',availableActions:{retry:{allowed:false},cancel:{allowed:false}}}
  c.methods.prepareAction.call(state,'retry',row)
  c.methods.prepareAction.call(state,'cancel',row)
  assert.equal(state.pending,null)
  state.busy=true
  c.methods.prepareAction.call(state,'cancel',{...row,availableActions:{cancel:{allowed:true}}})
  assert.equal(calls,0)
})
test('job times use the school time zone and the actual template compiles',()=>{
  const c=component({})
  assert.equal(c.methods.formatTime({createdAt:'2026-10-25T10:54:00Z',timeZone:'Asia/Shanghai'}),'2026-10-25 18:54')
  assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'SystemJobCenterView.vue',id:'jobs'}).errors,[])
  assert.equal(c.methods.authorizationActorLabel({currentActorAuthorization:{policyType:'TENANT_SYSTEM_TASK'}}),'当前经办人')
  assert.equal(c.methods.scopeSummary(null),'未记录任务范围')
})
test('a failed or ambiguous action rereads before another action is enabled',async()=>{
  let calls=0,reads=0,release
  const c=component({cancelJob:()=>{calls++;return new Promise(resolve=>{release=resolve})}})
  const state={...c.data(),ctx:{},load:async()=>{assert.equal(state.busy,true);reads++}}
  const row={jobId:'EXPORT:1',version:0,availableActions:{cancel:{allowed:true}}}
  c.methods.prepareAction.call(state,'cancel',row)
  const first=c.methods.performAction.call(state,{reason:'测试取消这个独立任务'})
  await c.methods.performAction.call(state,{reason:'测试取消这个独立任务'})
  assert.equal(calls,1)
  release({code:1,message:'结果需要回读'})
  await first
  assert.equal(reads,1)
  assert.equal(state.busy,false)
  assert.equal(state.actionNeedsReview,true)
  assert.notEqual(state.pending,null)
  await c.methods.performAction.call(state,{reason:'不能盲目重放同一请求'})
  assert.equal(calls,1)
})
test('confirmation submits the reviewed version and user reason, not a fixed phrase',async()=>{
  let sent
  const c=component({cancelJob:async(id,payload)=>{sent={id,...payload};return{code:0}}})
  const state={...c.data(),ctx:{},load:async()=>{}}
  const row={jobId:'EXPORT:2',version:3,availableActions:{cancel:{allowed:true}}}
  c.methods.prepareAction.call(state,'cancel',row)
  row.version=8
  await c.methods.performAction.call(state,{reason:'  该测试任务已不再需要  '})
  assert.equal(sent.expectedVersion,3)
  assert.equal(sent.reason,'该测试任务已不再需要')
  assert.equal(state.pending,null)
})
test('changed identity or missing reason prevents submission',async()=>{
  let calls=0
  const c=component({cancelJob:async()=>{calls++;return{code:0}}})
  const state={...c.data(),ctx:{currentRole:{roleCode:'SYS_ADMIN'}},load:async()=>{}}
  const row={jobId:'EXPORT:2',version:0,availableActions:{cancel:{allowed:true}}}
  c.methods.prepareAction.call(state,'cancel',row)
  await c.methods.performAction.call(state,{reason:''})
  assert.equal(calls,0)
  state.ctx={currentRole:{roleCode:'SCHOOL_ADMIN'}}
  await c.methods.performAction.call(state,{reason:'换了身份必须重新核对'})
  assert.equal(calls,0)
  assert.equal(state.actionNeedsReview,true)
})
