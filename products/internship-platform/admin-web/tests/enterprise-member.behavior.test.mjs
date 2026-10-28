import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, reactive, ref } from 'vue'
import * as contextConstants from '../src/modules/internship/constants/context.constants.js'
import { matchPermission } from '../src/config/navPlan.js'

const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function page(api={},context=null){
  const props={companyId:'22',batchId:'99',contacts:[{id:'55',name:'合成导师',status:'ACTIVE',contactType:'MENTOR'}],ctx:{ctxKey:'school-one',permissionPatterns:['internship.enterprise.manage'],currentRole:{baseRoleCode:'SCHOOL_ADMIN',contextId:'school',permissionVersion:'1'}}}
  if(context)props.ctx=context
  const row={id:'11',realName:'企业合成导师',memberRole:'MENTOR',status:'ACTIVE',version:2,contactId:'33',acceptedAt:'2026-10-01T00:00:00Z'}
  const calls=[],watchers=[];let unmount
  const service={members:async()=>({items:[row],total:1}),grants:async()=>({items:[],total:0}),bind:async(...args)=>{calls.push(args);return {...row,contactId:'55',version:3}},...api}
  const source=parse(fs.readFileSync(new URL('../src/modules/internship/views/components/EnterpriseMemberWorkspace.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+
    '\nreturn {rows,selected,contactId,grantForm,batchId,error,receipt,busy,bind,issue,choose,loadMembers,allowed,confirm,confirmAction}'
  const vm=new Function('computed','reactive','ref','watch','onBeforeUnmount','defineProps','api','internshipApi','recruitmentCampaignApi','canCode','currentUserFromToken','ENTERPRISE_LOGIN_URL','formatDateTime',source)(
    computed,reactive,ref,(_source,fn)=>{watchers.push(fn)},fn=>{unmount=fn},()=>props,service,{}, {},(ctx,code)=>!ctx.readonlyTenant&&matchPermission(ctx.permissionPatterns,code),()=>({tenantCode:'fixture'}),'/enterprise/login',String)
  return {vm,props,row,calls,watchers,unmount:()=>unmount()}
}

test('binding suppresses duplicate submit and uses the selected version without silently rebasing',async()=>{
  const waiting=deferred(),calls=[]
  const {vm,row}=page({bind:(...args)=>{calls.push(args);return waiting.promise}})
  vm.choose(row);vm.contactId.value='55'
  const first=vm.bind();await vm.bind()
  assert.equal(calls.length,1);assert.deepEqual(calls[0],['22','11',{contactId:'55',expectedVersion:2}])
  waiting.resolve({...row,contactId:'55',version:3});await first
  assert.equal(vm.selected.value.version,3);assert.match(vm.receipt.value,/重新登录/)
})

test('version conflict keeps the chosen contact and original expected version for explicit user review',async()=>{
  const {vm,row}=page({bind:async()=>{throw new Error('成员版本冲突')}})
  vm.choose(row);vm.contactId.value='55';await vm.bind()
  assert.equal(vm.contactId.value,'55');assert.equal(vm.selected.value.version,2)
  assert.match(vm.error.value,/填写内容已保留/);assert.equal(vm.receipt.value,'')
})

test('late successful binding after unmount cannot publish a receipt or replace another member',async()=>{
  const waiting=deferred(),{vm,row,unmount}=page({bind:()=>waiting.promise})
  vm.choose(row);vm.contactId.value='55';const first=vm.bind();unmount()
  waiting.resolve({...row,version:3});await first
  assert.equal(vm.selected.value.version,2);assert.equal(vm.receipt.value,'')
})

test('collaboration issue requires explicit dates, preserves string batch id and does not invent a grant type',async()=>{
  const calls=[],{vm,row}=page({issue:async(...args)=>{calls.push(args)}})
  vm.choose(row);await vm.issue();assert.equal(calls.length,0);assert.match(vm.error.value,/起止时间/)
  vm.batchId.value='9007199254740993';vm.grantForm.validFrom='2026-11-01T10:00';vm.grantForm.validUntil='2026-11-02T10:00'
  await vm.issue();assert.equal(calls[0][2].batchId,'9007199254740993');assert.equal(calls[0][2].expectedMemberVersion,2)
  assert.equal(Object.hasOwn(calls[0][2],'grantType'),false)
})

test('limited college identity is never presented as a school member manager',()=>{
  const {vm,props}=page();props.ctx.currentRole.baseRoleCode='COLLEGE_ADMIN'
  assert.equal(vm.allowed.value,false)
})

async function actualContextProjection(server){
  const source=fs.readFileSync(new URL('../src/modules/internship/api/internship.api.js',import.meta.url),'utf8')
  const body=source.match(/async getContext\(\) \{([\s\S]*?)\r?\n  },\r?\n\r?\n  getDashboardSummary/)[1]
  const dependencies={...contextConstants,
    request:async path=>path==='/auth/me'?{tenantId:'77',realName:'合成负责人'}:server,
    shouldTryReal:()=>true,currentUserFromToken:()=>({userType:'SCHOOL_ADMIN'}),
    setRbacLoadFailed:()=>{},setModuleAccessHealth:()=>{},setModuleEntitlements:()=>{},setPermissionPatterns:()=>{},
    allowByPatterns:(patterns,code)=>Array.isArray(patterns)&&matchPermission(patterns,code),isWriteCode:()=>true,
    clone:value=>JSON.parse(JSON.stringify(value)),ok:data=>({code:0,data})}
  return (await new Function(...Object.keys(dependencies),`return {async getContext(){${body}}}`)(...Object.values(dependencies)).getContext()).data
}

test('actual getContext preserves custom school role authority and scope metadata without granting college or view-only access',async()=>{
  const server={permissionPatterns:['internship.enterprise.manage'],currentRole:{roleCode:'CUSTOM_OWNER',baseRoleCode:'SCHOOL_ADMIN',roleName:'学校实习负责人',contextId:'custom-role-18',permissionVersion:'u1-r3'}}
  const context=await actualContextProjection(server)
  assert.equal(context.currentRole.roleCode,'CUSTOM_OWNER');assert.equal(context.currentRole.baseRoleCode,'SCHOOL_ADMIN')
  assert.equal(context.currentRole.contextId,'custom-role-18');assert.equal(context.currentRole.permissionVersion,'u1-r3')
  assert.equal(page({},context).vm.allowed.value,true)
  const college=await actualContextProjection({...server,currentRole:{...server.currentRole,baseRoleCode:'COLLEGE_ADMIN'}})
  assert.equal(page({},college).vm.allowed.value,false)
  const readonly=await actualContextProjection({...server,permissionPatterns:['internship.enterprise.view']})
  assert.equal(page({},readonly).vm.allowed.value,false)
  const next=await actualContextProjection({...server,currentRole:{...server.currentRole,permissionVersion:'u1-r4'}})
  assert.notEqual(context.ctxKey,next.ctxKey)
})
