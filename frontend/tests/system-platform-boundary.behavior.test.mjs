import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { matchPermission } from '../src/config/navPlan.js'

const root=new URL('../src/modules/system/views/',import.meta.url)
const read=name=>parse(fs.readFileSync(new URL(name+'.vue',root),'utf8')).descriptor
function forms(api){
  const env={businessFormsApi:api,ref:value=>({value}),reactive:value=>value,onMounted:()=>{}}
  vm.runInNewContext(read('SystemBusinessFormsView').scriptSetup.content.replace(/^import .*$/gm,'')+'\nglobalThis.view={loadDefinitions,definitions,versions,selected,loadError,loadDenied,loading,previewVersion};',env)
  return env.view
}
function storage(api={}){
  const env={fileStorageGovernanceApi:api,ModulePageShell:{},matchPermission,toast:{success(){},warning(){},error(){}}}
  vm.runInNewContext(read('SystemFileStorageGovernanceView').script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const c=env.component,s={...c.data(),ctx:{permissionPatterns:['systemAdmin.*']}}
  for(const [k,v] of Object.entries(c.methods))s[k]=v.bind(s)
  for(const [k,v] of Object.entries(c.computed))Object.defineProperty(s,k,{get:v.bind(s)})
  return s
}

function integration(api={}){
  const env={systemApi:api,matchPermission,toast:{success(){},error(){}}}
  for(const name of ['ModulePageShell','ModuleToolbar','DataTable','StatusTag','LoadingState','ErrorState','EmptyState','AppButton','AppDrawer','AppTextarea','FormFields'])env[name]={}
  vm.runInNewContext(read('SystemIntegrationView').script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const c=env.component,s={...c.data(),ctx:{permissionPatterns:['systemAdmin.integration.manage']}}
  for(const [k,v] of Object.entries(c.methods))s[k]=v.bind(s)
  for(const [k,v] of Object.entries(c.computed))Object.defineProperty(s,k,{get:v.bind(s)})
  return s
}

test('failed form definition reads clear previous actions and remain errors, not empty success',async()=>{
  const s=forms({definitions:async()=>{throw Object.assign(Error('当前身份无权限'),{httpStatus:403})}})
  s.selected.value={id:'old'};s.versions.value=[{versionId:'old'}]
  await s.loadDefinitions()
  assert.equal(s.loadError.value,'当前身份无权限');assert.equal(s.selected.value,null)
  assert.equal(s.versions.value.length,0);assert.equal(s.loading.value,false)
  assert.equal(s.loadDenied.value,true)
  const empty=forms({definitions:async()=>[]});await empty.loadDefinitions()
  assert.equal(empty.loadError.value,'');assert.equal(empty.definitions.value.length,0)
})

test('failed or incomplete storage reads cannot report no problems and zero usage',async()=>{
  const s=storage({overview:async()=>({})})
  await s.load();assert.match(s.error,/不完整/);assert.match(s.conclusion,/读取失败/)
  assert.equal(s.effectiveLimitText,'未取得')
})

test('storage presents server-authoritative effective limit and its source',()=>{
  const s=storage();s.usage={commercialStorageLimitBytes:50*1024**3,quotaBytes:100*1024**3,effectiveTotalLimitBytes:50*1024**3,effectiveTotalLimitSources:['PLATFORM_COMMERCIAL']}
  assert.equal(s.effectiveLimitText,'50.00 吉比字节');assert.equal(s.effectiveLimitSourceText,'平台商业上限')
  delete s.usage.effectiveTotalLimitBytes;assert.equal(s.effectiveLimitText,'未取得')
})

test('view-only file governance cannot dispatch quota, retention, cleanup or legal hold writes',async()=>{
  let calls=0
  const s=storage({saveQuota:async()=>{calls++},savePolicy:async()=>{calls++},cleanup:async()=>{calls++},setLegalHold:async()=>{calls++}})
  s.ctx.permissionPatterns=['systemAdmin.fileGovernance.view']
  await s.saveQuota();await s.savePolicy();await s.runCleanup(true);await s.setHold(true)
  assert.equal(calls,0)
})

test('affected boundary pages compile',()=>{
  for(const name of ['SystemBusinessFormsView','SystemFileStorageGovernanceView','SystemModuleFeatureView','SystemIntegrationView']){
    const d=read(name);assert.deepEqual(compileTemplate({source:d.template.content,filename:name,id:name}).errors,[])
  }
})

test('integration permissions alone cannot make a failed capability read look authorized',async()=>{
  const s=integration({listIntegrations:async()=>({code:403,message:'接口能力未开通'}),listSyncJobs:async()=>({code:403,message:'接口能力未开通'})})
  await s.load();s.openForm(null)
  assert.equal(s.canManage,true);assert.equal(s.accessVerified,false);assert.equal(s.form.open,false)
  assert.equal(s.toolbarActions[0].disabled,true);assert.equal(s.syncFailureText,'未取得')
})

test('successful empty integration reads are verified and editing preserves an existing nonstandard auth type',async()=>{
  const s=integration({listIntegrations:async()=>({code:0,data:{list:[]}}),listSyncJobs:async()=>({code:0,data:{list:[]}})})
  await s.load();assert.equal(s.accessVerified,true);assert.equal(s.rows.length,0)
  s.openForm({id:'old',name:'已有连接',endpoint:'https://example.invalid',authType:'LEGACY_AUTH'})
  assert.equal(s.form.value.authType,'LEGACY_AUTH');assert.equal(s.form.value.credential,'')
  assert.ok(s.authTypeOptions.some(x=>x.value==='LEGACY_AUTH'))
  assert.equal(s.authTypeLabel('TOKEN'),'令牌认证')
})
