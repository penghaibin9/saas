import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed,reactive,ref } from 'vue'
import { evaluationReturnPath,evaluationReturnTarget } from '../src/services/evaluationNavigation.js'

function login(api,redirect){
  const routes=[],route=reactive({query:{redirect},fullPath:'/login'}),watchers=[];let unmount
  const source=parse(fs.readFileSync(new URL('../src/views/EnterpriseLoginView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+'\nreturn {submit,form,loading,error,contexts,selectedMemberId}'
  const vm=new Function('computed','reactive','ref','watch','onBeforeUnmount','useRouter','useRoute','enterpriseAuthApi','getSelectedCampaignId','enterpriseRoleLabel','evaluationReturnTarget','evaluationReturnPath',source)(
    computed,reactive,ref,(_s,fn)=>watchers.push(fn),fn=>{unmount=fn},()=>({push:r=>routes.push(r)}),()=>route,api,()=>'',String,evaluationReturnTarget,evaluationReturnPath)
  return {vm,routes,unmount:()=>unmount(),route,watchers}
}
const target='/evaluations?tenantCode=fixture&campaignId=2&batchId=23&internshipId=9007199254740993'
test('QR login prefills its school and carries only the validated target into scope selection',async()=>{
  const {vm,routes}=login({login:async()=>{}},target)
  assert.equal(vm.form.tenantCode,'fixture');vm.form.loginName='mentor';vm.form.password='synthetic-only';await vm.submit()
  assert.equal(routes[0].path,'/campaign-select');assert.deepEqual(evaluationReturnTarget(routes[0].query.redirect),evaluationReturnTarget(target))
})
test('login has no arbitrary return URL and refuses to resume another school task',async()=>{
  const first=login({login:async()=>{}},'//outside.invalid/route');await first.vm.submit();assert.deepEqual(first.routes,['/campaign-select'])
  const second=login({login:async()=>{}},target);second.vm.form.tenantCode='other';await second.vm.submit();assert.deepEqual(second.routes,[]);assert.match(second.vm.error.value,/学校/)
})
test('multiple enterprise selection retains the same QR target after backend context-required response',async()=>{
  let attempts=0
  const {vm,routes}=login({login:async body=>{if(++attempts===1){const error=new Error('选择企业');error.bizCode='ENTERPRISE_CONTEXT_REQUIRED';error.details={contexts:[{memberId:'8',companyName:'合成企业',memberRole:'MENTOR'}]};throw error}assert.equal(body.memberId,'8')}},target)
  await vm.submit();assert.equal(routes.length,0);vm.selectedMemberId.value='8';await vm.submit()
  assert.equal(routes[0].path,'/campaign-select');assert.equal(evaluationReturnTarget(routes[0].query.redirect).query.internshipId,'9007199254740993')
})
test('repeated login is suppressed and late completion after leaving cannot navigate',async()=>{
  let finish,calls=0;const pending=new Promise(resolve=>{finish=resolve})
  const {vm,routes,unmount}=login({login:()=>{calls++;return pending}},target)
  const first=vm.submit();await vm.submit();assert.equal(calls,1);unmount();finish();await first;assert.deepEqual(routes,[])
})

test('reused login route follows the newly scanned student and school instead of the former target',async()=>{
  let finish;const pending=new Promise(resolve=>{finish=resolve});let calls=0
  const {vm,routes,route,watchers}=login({login:()=>++calls===1?pending:Promise.resolve()},target)
  const old=vm.submit()
  route.query.redirect='/evaluations?tenantCode=new-school&campaignId=5&batchId=6&internshipId=7'
  route.fullPath='/login?new-task';watchers[0]()
  assert.equal(vm.form.tenantCode,'new-school')
  finish();await old;assert.deepEqual(routes,[])
  await vm.submit();assert.equal(evaluationReturnTarget(routes[0].query.redirect).query.internshipId,'7')
})
