import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'

const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function mount(t,api,initial={}){
  const scope=effectScope(),handlers={},context=reactive({campaign:{id:'2'},contextMode:'RECRUITMENT',recruitmentContextReady:true,memberRole:'HR',...initial})
  const script=parse(fs.readFileSync(new URL('../src/views/EnterpriseHomeView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+'\nreturn {load,data,tasks,loading,error,campaignError}'
  const vm=scope.run(()=>new Function('computed','onBeforeUnmount','ref','watch','useEnterpriseContextStore','enterpriseInternshipApi',script)(computed,fn=>{handlers.unmount=fn},ref,(source,fn)=>watch(source,fn),()=>context,api))
  t.after(()=>{handlers.unmount();scope.stop()})
  return {vm,context,handlers}
}
test('home retries a failed dashboard without reporting an empty successful queue',async t=>{
  let fail=true
  const {vm}=mount(t,{campaigns:async()=>[],dashboard:async()=>{if(fail)throw new Error('读取失败');return {tasks:[{objectId:'7',title:'原岗位待补正'}]}}})
  await vm.load();assert.match(vm.error.value,/读取失败/);assert.equal(vm.data.value,null)
  fail=false;await vm.load();assert.equal(vm.error.value,'');assert.equal(vm.tasks.value[0].objectId,'7')
})
test('campaign change clears old tasks and a late old response cannot replace the new campaign',async t=>{
  const old=deferred();let calls=0
  const {vm,context}=mount(t,{campaigns:async()=>[],dashboard:()=>++calls===1?old.promise:Promise.resolve({tasks:[{objectId:'new'}]})})
  const pending=vm.load();context.campaign.id='3';await nextTick();await nextTick()
  old.resolve({tasks:[{objectId:'old'}]});await pending
  assert.equal(vm.tasks.value[0].objectId,'new');assert.equal(vm.loading.value,false)
})
test('collaboration-only context does not invoke recruitment and reports campaign read errors separately',async t=>{
  let calls=0
  const {vm}=mount(t,{dashboard:()=>{calls++;throw new Error('不应读取招聘')},campaigns:async()=>{throw new Error('历史读取失败')}},{recruitmentContextReady:false,contextMode:'INTERNSHIP_COLLAB'})
  await vm.load();assert.equal(calls,0);assert.equal(vm.error.value,'');assert.match(vm.campaignError.value,/历史读取失败/)
})
test('unmounted home ignores late dashboard results',async t=>{
  const response=deferred()
  const {vm,handlers}=mount(t,{campaigns:async()=>[],dashboard:()=>response.promise})
  const pending=vm.load();handlers.unmount();response.resolve({tasks:[{objectId:'old'}]});await pending
  assert.equal(vm.data.value,null)
})
