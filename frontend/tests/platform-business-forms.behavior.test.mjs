import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { optionsInstance, deferred } from './platform-workspace-test-support.mjs'
import { normalizeUiError } from '../src/utils/presentationSafety.js'
import { matchPermission } from '../src/config/navPlan.js'
import { contextFingerprint } from '../src/modules/system/utils/workspaceContract.js'

const pagePath='../src/modules/platform/views/control/PlatformBusinessFormsView.vue'
const page=(api={},extra={})=>optionsInstance(pagePath,{
  ctx:{permissionPatterns:['platform.businessForms.view','platform.businessForms.manage'],currentRole:{userId:'test',roleCode:'PLATFORM_TEST'}},...extra
},{api,matchPermission,contextFingerprint,normalizeUiError,BusinessFormVersionWorkbench:{},SchemaBusinessForm:{},WorkspaceConfirmDialog:{}})

test('late school data cannot replace another school selection',async()=>{
  const old=deferred()
  const {state}=page({definitions:id=>id==='A'?old.promise:Promise.resolve({tenantId:id,tenantName:'学校乙',items:[{id:'B-form'}]})})
  state.tenantId='A';const request=state.loadDefinitions();state.tenantId='B';await state.loadDefinitions()
  old.resolve({tenantId:'A',tenantName:'学校甲',items:[{id:'A-form'}]});await request
  assert.equal(state.tenantName,'学校乙');assert.equal(state.definitions[0].id,'B-form')
})

test('readonly platform form role cannot prepare a write',async()=>{
  let calls=0
  const {state}=page({impact:async()=>{calls++;return {}}},{ctx:{permissionPatterns:['platform.businessForms.view']}})
  await state.prepare('publish',{version:0,versionId:'1'})
  assert.equal(calls,0);assert.equal(state.pending,null)
})

test('uncertain writes stay pinned and cannot be automatically replayed',async()=>{
  let calls=0
  const {state}=page({publish:async(tid,vid,body)=>{calls++;assert.equal(tid,'A');assert.equal(vid,'7');assert.equal(body.expectedVersion,3);throw Error('请求结果未确认')}})
  state.tenantId='A';state.pending={tenantId:'A',versionId:'7',version:3,action:'publish',dynamicPolicyCount:0}
  await state.submit({reason:'独立发布验证原因'});await state.submit({reason:'不能重复发送请求'})
  assert.equal(calls,1);assert.equal(state.uncertain,true);assert.equal(state.pending.versionId,'7')
})

test('a write response from a previous identity cannot reopen its old school data',async()=>{
  const result=deferred()
  const {state,definition}=page({publish:()=>result.promise,schools:async()=>({items:[],hasMore:false})})
  state.tenantId='A';state.pending={tenantId:'A',versionId:'7',version:3,action:'publish',dynamicPolicyCount:0,definition:{id:'f'}}
  const request=state.submit({reason:'独立身份变化验证'})
  state.ctx={permissionPatterns:[],currentRole:{userId:'other'}};definition.watch.contextKey.call(state)
  result.resolve({});await request
  assert.equal(state.tenantId,'');assert.equal(state.selected,null);assert.equal(state.receipt,'')
})

test('platform menu uses the first authorized leaf when the group landing is forbidden',()=>{
  const {state}=optionsInstance('../src/modules/platform/views/AdminPlatformLayout.vue',{
    ctx:{},$router:{resolve:path=>({meta:{permissionKey:path.endsWith('business-forms')?'platform.businessForms.view':'platform.productIam.view'}})}
  },{BasePortalLayout:{},TenantProfileEditor:{},PLATFORM_MANAGEMENT_CATALOG:[{key:'plt-standards',label:'全局标准与发布',items:[{path:'/admin/platform/product-iam'},{path:'/admin/platform/business-forms'}]}],canEnterRoute:meta=>meta.permissionKey==='platform.businessForms.view'})
  assert.equal(state.menus.length,1);assert.equal(state.menus[0].path,'/admin/platform/business-forms')
})

test('platform form workspace and reused version table compile',()=>{
  for(const path of [pagePath,'../src/modules/platform/businessForms/components/BusinessFormVersionWorkbench.vue']){
    const d=parse(fs.readFileSync(new URL(path,import.meta.url),'utf8')).descriptor
    assert.deepEqual(compileTemplate({source:d.template.content,filename:path,id:path}).errors,[])
  }
})
