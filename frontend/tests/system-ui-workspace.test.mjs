import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as w from '../src/modules/system/utils/workspaceContract.js'
const tree = [{ key: 'mod-system', label: '系统管理', children: [{ key: 'systemAdmin.user.view', label: '账号', path: '/admin/system/accounts/staff', children: [{ key: 'systemAdmin.user.import', label: '导入', children: [] }] }, {key:'systemAdmin.role.config',label:'角色配置',advanced:true,children:[]}] }]
const detail = { id: '301', type: 'CUSTOM', version: 0, scopeCode: 'COLLEGE', permissionCodes: ['systemAdmin.user.view', 'system.history'], readOnlyPreservedPermissions: [{ permissionCode:'system.history', label:'历史只读',editable:false}] }
test('approved role draft uses version zero and excludes readonly codes from editable choices', () => {
  const draft = w.makePermissionDraft(tree, detail, '301')
  assert.equal(draft.version, 0); assert.deepEqual(draft.menuKeys, ['systemAdmin.user.view']); assert.deepEqual(draft.buttonKeys, [])
})
test('permission payload preserves targets by omission and retains the existing adapter shape', () => {
  const args = w.permissionSaveArgs(w.makePermissionDraft(tree, detail, '301'), '本学期职责调整', w.newRequestId())
  assert.equal(args.expectedVersion,0); assert.ok(!Object.hasOwn(args,'scopeTarget')); assert.ok(!Object.hasOwn(args,'permissionCodes'))
  assert.deepEqual(args.menuKeys,['systemAdmin.user.view'])
})
test('missing detail, wrong role or invalid version cannot initialize editable state', () => {
  for(const value of [null, {...detail,id:'302'}, {...detail,version:null}, {...detail,version:-1}]) assert.throws(()=>w.makePermissionDraft(tree,value,'301'))
})
test('malformed or duplicate directory is rejected, not normalized to no permissions', () => {
  for(const value of [null,[{}],[{key:'module',children:[{key:'code'}]}],[...tree,...tree]]) assert.throws(()=>w.makePermissionDraft(value,detail,'301'))
})
test('readonly projection accepts server legacy codes but not saving them as new grants', () => {
  const draft=w.makeReadOnlyDraft(detail,'301');assert.equal(draft.menuKeys.length,2)
  assert.throws(()=>w.permissionSaveArgs(draft,'测试只读保存',w.newRequestId()))
})
test('button selection keeps existing parent semantics, unchecking parent removes its actions', () => {
  let draft=w.makePermissionDraft(tree,detail,'301');const [menu,button]=draft.groups[0].rows
  draft=w.changePermission(draft,button,true);assert.deepEqual(draft.buttonKeys,[button.key])
  draft=w.changePermission(draft,menu,false);assert.deepEqual(draft.buttonKeys,[])
  draft=w.changePermission(draft,button,true);assert.deepEqual(draft.buttonKeys,[])
})
test('capability safety rejects failed/stale impact and string booleans', () => {
  const args={canWrite:true,busy:false,item:{capabilityKey:'internship',version:0},enabled:false,impactState:'ready',impact:{capabilityKey:'internship'},contextMatches:true}
  assert.equal(w.capabilityCanConfirm(args),true)
  for(const change of [{impactState:'error'},{impact:{capabilityKey:'graduation'}},{contextMatches:false},{canWrite:false},{busy:true},{enabled:'false'}]) assert.equal(w.capabilityCanConfirm({...args,...change}),false)
})
test('unentitled or dependency-unready capabilities cannot be enabled', () => {
  const args={canWrite:true,busy:false,item:{version:1,entitled:false},enabled:true,contextMatches:true}
  assert.equal(w.capabilityCanConfirm(args),false)
  assert.equal(w.capabilityCanConfirm({...args,item:{version:1,entitled:true,dependencyUnmet:['x']}}),false)
})
test('late responses cannot replace a new context or newer request on the same channel', () => {
  const fence=w.createRequestFence(), a=fence.start('role'), other=fence.start('members'), b=fence.start('role')
  assert.equal(a(),false);assert.equal(other(),true);assert.equal(b(),true);fence.invalidate();assert.equal(b(),false);assert.equal(other(),false)
})
test('subject, tenant and permission revision are part of request identity', () => {
  const ctx={permissionActions:{effectiveAccess:{tenantId:'1',subjectId:'2',activeContextId:'role:3',permissionVersion:0}}}
  for(const change of [{tenantId:'2'},{subjectId:'4'},{activeContextId:'role:4'},{permissionVersion:1}]) assert.notEqual(w.contextFingerprint(ctx), w.contextFingerprint({permissionActions:{effectiveAccess:{...ctx.permissionActions.effectiveAccess,...change}}}))
})
test('page total is server total, never current page length', () => {
  assert.equal(w.paged({items:[{id:'1'}],total:250,page:2,pageSize:50}).total,250)
  assert.throws(()=>w.paged({items:[],page:1,pageSize:50}));assert.throws(()=>w.paged({list:[],total:0,page:1,pageSize:50}))
})
test('unknown counts remain unknown; zero is a real count',()=>{assert.equal(w.countLabel(null),'未取得');assert.equal(w.countLabel(undefined),'未取得');assert.equal(w.countLabel(0),'0')})
test('student selection submits the profile ID and never the account ID',()=>{
  assert.equal(w.accessResource({id:'91',studentId:'501',profileBound:true,name:'测试学生'},'INTERN_STUDENT').id,'501')
  assert.throws(()=>w.accessResource({id:'91'},'STUDENT'));assert.throws(()=>w.accessResource({id:'1',type:'CLASS'},'COLLEGE'))
})
test('menu preview never turns a background permission into a navigation entry',()=>{
  const groups=w.permissionGroups(tree)
  assert.deepEqual(w.visibleMenuPreview(groups,['systemAdmin.user.view','systemAdmin.role.config']).map(x=>x.key),['systemAdmin.user.view'])
})
test('only server action visibility and allowance open a mutation',()=>{
  assert.equal(w.actionAllowed({permissionActions:{a:{visible:true,allowed:true}}},'a'),true)
  for(const value of [{},{visible:false,allowed:true},{visible:true,allowed:false}]) assert.equal(w.actionAllowed({permissionActions:{a:value}},'a'),false)
})
test('same role does not suppress leave guard when changing from workbench to diagnostics',()=>{
  assert.equal(w.isRoleWorkspaceRoute({path:'/admin/system/iam',query:{surface:'diagnostics',roleId:'301'}}),false)
  assert.equal(w.isRoleWorkspaceRoute({path:'/admin/system/iam',query:{surface:'permissions',roleId:'301'}}),true)
})
const dir=new URL('../src/modules/system/components/workspace/',import.meta.url)
for(const file of fs.readdirSync(dir).filter(x=>x.endsWith('.vue'))){
  test(`Vue compiler accepts production workspace: ${file}`,()=>{
    const path=new URL(file,dir), source=fs.readFileSync(path,'utf8'), {descriptor,errors}=parse(source,{filename:file})
    assert.deepEqual(errors,[]);const script=compileScript(descriptor,{id:file})
    const result=compileTemplate({source:descriptor.template.content,filename:file,id:file,compilerOptions:{bindingMetadata:script.bindings}})
    assert.deepEqual(result.errors,[])
  })
}

for (const file of ['SystemRoleListView.vue', 'SystemIamWorkspaceView.vue', 'SystemModuleFeatureView.vue', 'SystemDataScopeView.vue']) {
  test(`Vue compiler accepts integrated production view: ${file}`, () => {
    const source = fs.readFileSync(new URL(`../src/modules/system/views/${file}`, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source, { filename: file })
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: file })
    const result = compileTemplate({ source: descriptor.template.content, filename: file, id: file, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [])
  })
}
