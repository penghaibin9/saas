import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { optionsInstance, deferred } from './platform-workspace-test-support.mjs'
import { contextFingerprint } from '../src/modules/system/utils/workspaceContract.js'
const path='../src/modules/system/views/SystemWorkflowGovernanceView.vue'
const page=api=>optionsInstance(path,{ctx:{currentRole:{userId:'test'}}},{ModuleToolbar:{},DataTable:{},StatusTag:{},AppConfirmDialog:{},systemApi:api,contextFingerprint,matchPermission,workflowNames:{},roleDisplayLabel:x=>x,permissionDisplayLabel:x=>x,toast:{error(){},success(){}}})
test('task node names fall back to the existing Chinese code catalog',()=>{
  const {state}=page({})
  assert.equal(state.nodeDisplayLabel('COLLEGE_REVIEW','COLLEGE_REVIEW'),'学院审核')
  assert.equal(state.nodeDisplayLabel('学院复核','COLLEGE_REVIEW'),'学院复核')
  assert.equal(state.nodeDisplayLabel('UNKNOWN',null),'节点名称待维护')
})

test('late task reads do not replace the latest page',async()=>{
  const old=deferred();const {state}=page({listWorkflowGovernanceTasks:p=>p===1?old.promise:Promise.resolve({code:0,data:{items:[{taskId:'new'}],total:21,page:2}})})
  const pending=state.loadTasks(1);await state.loadTasks(2)
  old.resolve({code:0,data:{items:[{taskId:'old'}],total:1,page:1}});await pending
  assert.equal(state.tasks[0].taskId,'new');assert.equal(state.taskPage,2)
})
test('failed task reads clear stale tasks and show an error',async()=>{
  const {state}=page({listWorkflowGovernanceTasks:async()=>({code:1,message:'没有权限'})})
  state.tasks=[{taskId:'old'}];await state.loadTasks()
  assert.equal(state.tasks.length,0);assert.equal(state.taskError,'没有权限')
})
test('governance routes to the existing approval detail and cannot dispatch old force actions',async()=>{
  const {state}=page({forceAdvanceWorkflowTask:()=>{throw Error('must not write')}})
  let target;state.$router={push:x=>{target=x}};state.openTask({taskId:'123'})
  assert.equal(target.name,'approval-detail');assert.equal(target.params.taskId,'123')
  state.pendingAction='force';await state.submitDialog({reason:'不应调用旧人工强推'})
  assert.equal(state.submitting,false)
})
test('workflow governance template compiles',()=>{
  const d=parse(fs.readFileSync(new URL(path,import.meta.url),'utf8')).descriptor
  assert.deepEqual(compileTemplate({source:d.template.content,filename:path,id:path}).errors,[])
})

import { matchPermission } from '../src/config/navPlan.js'
const communicationPath='../src/modules/system/views/SystemCommunicationGovernanceView.vue'
const communication=(api,permissions=['systemAdmin.communication.manage'])=>optionsInstance(communicationPath,
  {ctx:{permissionPatterns:permissions,currentRole:{userId:'test'}}},
  {ModuleToolbar:{},DataTable:{},StatusTag:{},AppConfirmDialog:{},systemApi:api,matchPermission,contextFingerprint,toast:{error(){},success(){}}})
test('communication read failures never masquerade as empty backlog',async()=>{
  const ok=async()=>({code:0,data:{items:[]}})
  const {state}=communication({getCommunicationGovernanceOverview:ok,getCommunicationRegistry:ok,listTodoBacklog:async()=>({code:1,message:'读取失败'}),listDeadOutbox:ok})
  state.todos=[{id:'old'}];await state.load();assert.equal(state.error,'读取失败');assert.equal(state.todos.length,0)
})
test('readonly communication operators cannot dispatch recovery writes',async()=>{
  const fail=()=>{throw Error('unexpected write')};const {state}=communication({closeTodoWithEvidence:fail,retryDeadOutbox:fail},['systemAdmin.communication.view'])
  state.askClose({id:'1',version:0});await state.retry({outboxId:'1'});assert.equal(state.pendingTodo,null)
})
test('todo close pins version and prevents duplicate submission',async()=>{
  const response=deferred();let calls=0;const {state}=communication({closeTodoWithEvidence:(id,payload)=>{calls++;assert.equal(id,'1');assert.equal(payload.expectedVersion,4);return response.promise}})
  state.askClose({id:'1',version:4});const pending=state.submitClose({reason:'核对来源状态'});await state.submitClose({reason:'重复点击'})
  response.resolve({code:1,message:'来源仍在办理'});await pending
  assert.equal(calls,1);assert.equal(state.pendingTodo.id,'1');assert.equal(state.closeDialogOpen,true)
})
test('communication governance template compiles',()=>{
  const d=parse(fs.readFileSync(new URL(communicationPath,import.meta.url),'utf8')).descriptor
  assert.deepEqual(compileTemplate({source:d.template.content,filename:communicationPath,id:communicationPath}).errors,[])
})

test('communication pagination requests the selected server page and rejects beyond last page',async()=>{
  const requests=[];const ok=async()=>({code:0,data:{items:[],total:41}})
  const {state}=communication({getCommunicationGovernanceOverview:ok,getCommunicationRegistry:ok,listTodoBacklog:async p=>{requests.push(p.page);return {code:0,data:{items:[{id:'page-'+p.page}],total:41}}},listDeadOutbox:ok})
  state.todoPage=2;await state.load();assert.equal(requests[0],2);assert.equal(state.todos[0].id,'page-2')
  state.todoPage=3;state.loading=false;let writes=0;state.load=()=>{writes++};state.changePage('todo',1)
  assert.equal(state.todoPage,3);assert.equal(writes,0)
})
