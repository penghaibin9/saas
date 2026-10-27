import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { formatDateTime } from '../src/utils/dateUtils.js'
import { matchPermission } from '../src/config/navPlan.js'

const root=new URL('../src/modules/system/views/',import.meta.url)
function setup(name,api={}){
  const source=fs.readFileSync(new URL(name+'.vue',root),'utf8')
  const descriptor=parse(source).descriptor
  const env={systemApi:api,formatDateTime,matchPermission,contextFingerprint:()=>'',toast:{success(){},error(){}}}
  for(const name of ['ModulePageShell','LoadingState','ErrorState','EmptyState','StatusTag','AppButton','AppDrawer','SystemWorkspaceFrame'])env[name]={}
  vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.component='),env)
  const c=env.component,s={...c.data(),ctx:{permissionPatterns:['systemAdmin.*']}}
  for(const [k,v] of Object.entries(c.methods))s[k]=v.bind(s)
  for(const [k,v] of Object.entries(c.computed||{}))Object.defineProperty(s,k,{get:v.bind(s)})
  return s
}

test('calendar renders the UTC instant in school timezone and only names connected consumers',()=>{
  const s=setup('SystemAcademicCalendarView')
  assert.equal(s.fmt('2026-10-26T00:30:00Z','Asia/Shanghai'),'2026-10-26 08:30')
  s.consumers=[{moduleName:'教务中心',wired:true},{moduleName:'岗位实习中心',wired:false}]
  assert.equal(s.wiredModuleNames,'教务中心')
  assert.equal(s.academicStatusLabel('PUBLISHED'),'已发布')
})

test('failed closing evidence cannot look empty or submit a transition',async()=>{
  let writes=0
  const s=setup('SystemAcademicCalendarView',{getAcademicCalendarBlockers:async()=>({code:500,message:'读取失败'}),transitionAcademicCalendar:async()=>{writes++}})
  s.form.termId='1';s.form.target='CLOSING';s.form.reason='隔离结期验证原因'
  await s.loadBlockers('1');await s.submitTransition()
  assert.equal(s.form.blockersError,'读取失败');assert.equal(writes,0)
})

test('late calendar detail does not overwrite a different selected term',async()=>{
  let finish
  const old=new Promise(resolve=>{finish=resolve})
  const s=setup('SystemAcademicCalendarView',{getAcademicCalendarDetail:id=>id==='a'?old:Promise.resolve({code:0,data:{termId:id}})})
  const pending=s.openDetail({termId:'a'});await s.openDetail({termId:'b'})
  finish({code:0,data:{termId:'a'}});await pending
  assert.equal(s.detail.data.termId,'b')
})

test('saving a dictionary updates its original object when selection changes',async()=>{
  let finish
  const pending=new Promise(resolve=>{finish=resolve})
  const s=setup('SystemDictionariesView',{saveDictionary:()=>pending})
  s.dictionaries=[{code:'a',label:'甲',editable:true,items:[{code:'A',label:'甲',enabled:true}]},{code:'b',label:'乙',editable:true,items:[{code:'B',label:'乙',enabled:true}]}]
  s.selectedCode='a';const save=s.save();s.select('b')
  finish({code:0,data:{version:2,items:[{code:'A',label:'甲已保存',enabled:true}]}});await save
  assert.equal(s.dictionaries[0].items[0].label,'甲已保存')
  assert.equal(s.dictionaries[1].items[0].code,'B')
})

test('policy history read failure remains an error rather than no history',async()=>{
  const s=setup('SystemLoginPolicyView',{getConfigHistory:async()=>({code:500,message:'历史读取失败'})})
  await s.openHistory({configKey:'SEC_LOCK_MAX_FAIL',configName:'登录锁定'})
  assert.equal(s.history.error,'历史读取失败');assert.equal(s.history.loading,false)
  assert.equal(s.consumerLabel({configKey:'SEC_LOCK_MAX_FAIL'}),'登录失败计数与锁定')
  assert.equal(s.policyValue({configKey:'SEC_PHONE_LOGIN_ENABLED',value:0}),'已关闭')
  assert.equal(s.policyValue({configKey:'SEC_PHONE_LOGIN_ENABLED',value:null}),'未取得')
})

test('affected system pages compile',()=>{
  for(const name of ['SystemAcademicCalendarView','SystemDictionariesView','SystemLoginPolicyView']){
    const d=parse(fs.readFileSync(new URL(name+'.vue',root),'utf8')).descriptor
    assert.deepEqual(compileTemplate({source:d.template.content,filename:name,id:name}).errors,[])
  }
})

test('view-only contexts cannot open calendar changes or generic security policy edits',async()=>{
  let writes=0
  const calendar=setup('SystemAcademicCalendarView',{enrollAcademicCalendar:async()=>{writes++}})
  calendar.ctx.permissionPatterns=['systemAdmin.academicCalendar.view']
  calendar.openTransition({termId:'a'},'ACTIVE');await calendar.enroll({termId:'a'})
  assert.equal(calendar.form.open,false);assert.equal(writes,0)
  const policy=setup('SystemLoginPolicyView')
  policy.ctx.permissionPatterns=['systemAdmin.config.view']
  policy.openEdit({configKey:'SEC_LOCK_MAX_FAIL',schoolEditable:true,value:5})
  assert.equal(policy.edit.open,false)
})
