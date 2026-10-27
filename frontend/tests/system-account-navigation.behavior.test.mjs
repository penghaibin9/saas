import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {parse,compileTemplate} from '@vue/compiler-sfc'

const source=readFileSync(new URL('../src/modules/system/views/SystemUserListView.vue',import.meta.url),'utf8')
const {descriptor}=parse(source)
function setup(){
  const storage=new Map()
  const env={systemApi:{},contextFingerprint:ctx=>ctx.identity,
    sessionStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)},toast:{error:()=>{}}}
  for(const name of ['ModulePageShell','ModuleToolbar','AdvancedFilter','DataTable','StatusTag','LoadingState','ErrorState','EmptyState',
    'AppButton','AppDrawer','AppConfirmDialog','AppCheckboxGroup','AppSelect','FormFields','RoleScopeEditor','ExportDialog','PhoneGovernancePanel'])env[name]={}
  vm.runInNewContext(descriptor.script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm,'').replace('export default','globalThis.component ='),env)
  const component=env.component
  const state={ctx:{identity:'school-a:role-a',fieldColumns:{staffAccounts:[]}},$route:{meta:{accountType:'STAFF'},query:{}},accountType:'STAFF'}
  Object.assign(state,component.data.call(state))
  for(const [name,fn] of Object.entries(component.methods))state[name]=fn.bind(state)
  state.restoreQuery()
  return {env,state,component,storage}
}
test('completed query restores filters and page only for the same school and identity',async()=>{
  const {env,state,storage}=setup()
  env.systemApi.getUsers=async()=>({code:0,data:{list:[],total:31}})
  state.filters.keyword='D603-T001'; state.pagination.page=3
  await state.load()
  state.filters.keyword='';state.pagination.page=1;state.restoreQuery()
  assert.equal(state.filters.keyword,'D603-T001');assert.equal(state.pagination.page,3)
  state.ctx.identity='school-b:role-a';state.filters.keyword='';state.pagination.page=1;state.restoreQuery()
  assert.equal(state.filters.keyword,'');assert.equal(state.pagination.page,1)
  assert.equal(storage.size,1)
})
test('late list and detail responses cannot overwrite the latest selected account',async()=>{
  const {env,state}=setup();let oldList,oldDetail
  env.systemApi.getUsers=()=>new Promise(resolve=>{oldList=resolve})
  const pending=state.load()
  env.systemApi.getUsers=async()=>({code:0,data:{list:[{id:'new'}],total:1}})
  await state.load();oldList({code:0,data:{list:[{id:'old'}],total:8}});await pending
  assert.equal(state.rows[0].id,'new')
  env.systemApi.getUserDetail=()=>new Promise(resolve=>{oldDetail=resolve})
  const first=state.openDetail({id:'old'})
  env.systemApi.getUserDetail=async()=>({code:0,data:{id:'new'}})
  await state.openDetail({id:'new'});oldDetail({code:0,data:{id:'old'}});await first
  assert.equal(state.detail.data.id,'new')
})
test('context switch closes previous identity detail and clears selected accounts',()=>{
  const {state,component}=setup();state.detail={open:true,data:{id:'old'}};state.selected=['old'];state.load=()=>{}
  state.ctx.identity='school-a:role-b';component.watch.ctx.handler.call(state,state.ctx)
  assert.equal(state.detail.open,false);assert.equal(state.selected.length,0);assert.equal(state.pagination.page,1)
})
test('phone governance loads only on demand and account template compiles',()=>{
  const {state}=setup();assert.equal(state.detailPhoneOpen,false)
  assert.match(descriptor.template.content,/<PhoneGovernancePanel v-if="detailPhoneOpen"/)
  assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'SystemUserListView.vue',id:'account'}).errors,[])
})
test('assignment pagination preserves existing filters in one query string',async()=>{
  const api=readFileSync(new URL('../src/modules/system/api/system.api.js',import.meta.url),'utf8')
  const method=api.match(/  async listStaffAssignments\([\s\S]*?^  },/m)[0]
  let path
  const run=Function('request','ok','fail',`return ({${method}}).listStaffAssignments`)(async value=>{path=value;return {}},x=>x,x=>{throw Error(x)})
  await run({includeExpired:true,userId:'12',page:3,pageSize:20})
  const url=new URL(path,'http://localhost')
  assert.equal(url.searchParams.get('includeExpired'),'true');assert.equal(url.searchParams.get('page'),'3')
  assert.equal(url.searchParams.get('userId'),'12');assert.equal([...path].filter(x=>x==='?').length,1)
  const staff=parse(readFileSync(new URL('../src/modules/system/views/SystemStaffAffiliationView.vue',import.meta.url),'utf8')).descriptor
  assert.deepEqual(compileTemplate({source:staff.template.content,filename:'SystemStaffAffiliationView.vue',id:'staff'}).errors,[])
})
