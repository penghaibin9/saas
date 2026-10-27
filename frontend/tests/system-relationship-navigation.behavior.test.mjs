import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {systemRelationshipReturnTo,relationshipObjectDestination} from '../src/utils/systemRelationshipNavigation.js'
const base=new URL('../src/modules/system/views/',import.meta.url)
function view(file,api={}){
  const {descriptor}=parse(readFileSync(new URL(file,base),'utf8'))
  const env={systemApi:api,schoolIamApi:{},toast:{error:()=>{}},roleDisplayLabel:row=>row.roleName||'角色',
    contextFingerprint:ctx=>JSON.stringify(ctx),relationshipObjectDestination}
  for(const name of ['ModulePageShell','ModuleToolbar','DataTable','StatusTag','LoadingState','ErrorState','EmptyState','AppConfirmDialog','AppDrawer','AccountCandidatePicker','AppRemoteSelect'])env[name]={}
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const c=env.component;const state={...c.data(),ctx:{}}
  for(const [key,fn] of Object.entries(c.methods))state[key]=fn.bind(state)
  for(const [key,fn] of Object.entries(c.computed||{}))Object.defineProperty(state,key,{get:fn.bind(state)})
  return {state,descriptor}
}
test('zero objects, bounded samples and complete checks have different conclusions',()=>{
  const {state}=view('SystemBusinessRelationView.vue')
  state.issues=[{relationType:'T',total:0,scanned:0}]
  assert.match(state.emptyResult('T'),/尚无/)
  state.issues=[{relationType:'T',total:2001,scanned:2000,truncated:true}]
  assert.match(state.emptyResult('T'),/抽查.*未覆盖/)
  state.issues=[{relationType:'T',total:20,scanned:20,truncated:false}]
  assert.equal(state.emptyResult('T'),'本次检查未发现缺口')
})
test('unscanned quality is not a perfect or zero score, and closed issues remain read only',async()=>{
  let writes=0
  const {state}=view('SystemMasterDataView.vue',{verifyMasterDataIssue:()=>{writes++}})
  state.domains=[{qualityScore:null}];assert.equal(state.worstScore,'未取得');assert.equal(state.scoreTone(null),'default')
  state.domains.push({qualityScore:92});assert.equal(state.worstScore,92)
  state.ask('resolve',{status:'VERIFIED'});await state.doVerify({status:'VERIFIED'})
  assert.equal(state.dialogOpen,false);assert.equal(writes,0)
  assert.equal(state.issueDestination({ruleCode:'ORG_DUPLICATE_CODE',objectType:'CLASS',objectId:'123'}),'')
  assert.equal(state.issueDestination({ruleCode:'CLASS_MISSING_COUNSELOR',objectType:'CLASS',objectId:'123'}),'/admin/campus-service/classes/123')
})
test('object destinations preserve independent batches and reject external or malformed navigation',()=>{
  const source='/admin/system/role-assignments?view=relations&relationUserId=2'
  const gd=relationshipObjectDestination({route:{path:'/admin/graduation/students/7',query:{batchId:'11'}}},source)
  const internship=relationshipObjectDestination({route:{path:'/admin/internship/students/7',query:{batchId:'22'}}},source)
  assert.notEqual(gd.path,internship.path);assert.equal(gd.query.batchId,'11');assert.equal(internship.query.batchId,'22')
  assert.equal(gd.query.returnTo,source)
  assert.equal(relationshipObjectDestination({route:{path:'https://outside.invalid'}},source),null)
  assert.equal(relationshipObjectDestination({route:{path:'/admin/graduation/students/7',query:{batchId:'wrong'}}},source),null)
  for(const raw of ['//outside.invalid','https://outside.invalid','/admin/system/master-data-evil'])assert.equal(systemRelationshipReturnTo(raw),'')
})
test('late object detail cannot overwrite a newer relation, even when numeric IDs match',async()=>{
  const pending=[]
  const {state}=view('SystemRoleAssignmentView.vue',{listBusinessIdentityObjects:()=>new Promise(resolve=>pending.push(resolve))})
  const a={identityType:'GD_MENTOR',subjectKey:'mentor:1'},b={identityType:'INTERNSHIP_ADVISOR',subjectKey:'user:1'}
  const first=state.loadObjects(a,1),second=state.loadObjects(b,1)
  pending[1]({code:0,data:{list:[{label:'实习对象'}],total:1}});await second
  pending[0]({code:0,data:{list:[{label:'毕设对象'}],total:1}});await first
  assert.equal(state.objectPanel.row,b);assert.equal(state.objectPanel.items[0].label,'实习对象')
})
test('business relationships do not expose fixed-role cleanup actions',()=>{
  const {state}=view('SystemRoleAssignmentView.vue')
  state.ctx={permissionPatterns:['systemAdmin.user.assign']};state.tab='identities'
  assert.deepEqual(Array.from(state.toolbarActions,item=>item.key),['refresh'])
  state.tab='members';assert.ok(state.toolbarActions.some(item=>item.key==='sweep'))
})
test('relationship, quality and five direct destination templates compile',()=>{
  const files=['system/views/SystemBusinessRelationView.vue','system/views/SystemMasterDataView.vue','system/views/SystemRoleAssignmentView.vue',
    'studentAffairs/views/class/ClassProfileView.vue','academicAffairs/views/AaTaskDetailView.vue','academicAffairs/views/AaRosterDetailView.vue',
    'graduation/views/GraduationStudentDetailView.vue','internship/views/InternshipStudentDetailView.vue']
  for(const file of files){const {descriptor}=parse(readFileSync(new URL('../src/modules/'+file,import.meta.url),'utf8'))
    assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:file,id:file}).errors,[])}
})
