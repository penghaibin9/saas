import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'

const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function mount(t,api,contextPatch={}){
  const scope=effectScope(),handlers={},pushed=[],selectedCampaigns=[]
  const context=reactive({unreadMessages:1,recruitmentContextReady:true,campaign:{id:'7'},loadMessageCount:async()=>{context.unreadMessages=0},load:async()=>{},...contextPatch})
  const script=parse(fs.readFileSync(new URL('../src/views/EnterpriseMessagesView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+'\nreturn {load,openMessage,openAction,closeDetail,rows,total,page,readStatus,selected,error,detailError,actionError}'
  const vm=scope.run(()=>new Function('computed','onBeforeUnmount','ref','watch','useRouter','enterpriseInternshipApi','setSelectedCampaignId','useEnterpriseContextStore',script)(computed,fn=>{handlers.unmount=fn},ref,(source,fn,options)=>watch(source,fn,options),()=>({push:async value=>{pushed.push(value)}}),api,value=>selectedCampaigns.push(String(value)),()=>context))
  t.after(()=>{handlers.unmount();scope.stop()})
  return {vm,context,pushed,selectedCampaigns,handlers}
}

test('message list ignores a late response after the reading filter changes',async t=>{
  const first=deferred();let calls=0
  const {vm}=mount(t,{messages:()=>++calls===1?first.promise:Promise.resolve({items:[{messageId:'new'}],total:1})})
  await nextTick();vm.readStatus.value='UNREAD';await nextTick();await nextTick()
  first.resolve({items:[{messageId:'old'}],total:1});await nextTick()
  assert.equal(vm.rows.value[0].messageId,'new');assert.equal(vm.total.value,1)
})

test('opening an unread message explicitly records read state and refreshes the badge',async t=>{
  const calls=[]
  const api={messages:async()=>({items:[],total:0}),message:async id=>({messageId:id,readStatus:'UNREAD',title:'待补正'}),readMessage:async id=>{calls.push(id)}}
  const {vm,context}=mount(t,api)
  await nextTick();await nextTick()
  vm.rows.value=[{messageId:'12',readStatus:'UNREAD'}]
  await vm.openMessage(vm.rows.value[0])
  assert.deepEqual(calls,['12']);assert.equal(vm.selected.value.readStatus,'READ');assert.equal(vm.rows.value[0].readStatus,'READ');assert.equal(context.unreadMessages,0)
})

test('position action validates object ids, switches campaign and opens the original position',async t=>{
  const api={messages:async()=>({items:[],total:0})}
  const {vm,pushed,selectedCampaigns}=mount(t,api)
  vm.selected.value={actionKey:'enterprise.internship.position',actionParams:{positionId:'18',campaignId:'7'}}
  await vm.openAction()
  assert.deepEqual(selectedCampaigns,['7']);assert.deepEqual(pushed,[{path:'/positions/18/edit',query:{campaignId:'7'}}])
  vm.selected.value={actionKey:'enterprise.internship.position',actionParams:{positionId:'../18',campaignId:'7'}}
  await vm.openAction();assert.equal(pushed.length,1);assert.match(vm.actionError.value,/安全打开/)
})

test('expired campaign authority leaves the user in the inbox with an accurate error',async t=>{
  const api={messages:async()=>({items:[],total:0})}
  const {vm,pushed}=mount(t,api,{recruitmentContextReady:false,campaign:null})
  vm.selected.value={actionKey:'enterprise.internship.position',actionParams:{positionId:'18',campaignId:'9'}}
  await vm.openAction();assert.equal(pushed.length,0);assert.match(vm.actionError.value,/不能进入该招聘季/)
})

test('application result opens only the original candidate after rechecking campaign and role',async t=>{
  const {vm,pushed}=mount(t,{messages:async()=>({items:[],total:0})},{applicationViewAllowed:true})
  vm.selected.value={actionKey:'enterprise.internship.application',actionParams:{applicationId:'28',campaignId:'7'}}
  await vm.openAction()
  assert.deepEqual(pushed,[{path:'/applications/28',query:{campaignId:'7'}}])
  const denied=mount(t,{messages:async()=>({items:[],total:0})},{applicationViewAllowed:false})
  denied.vm.selected.value={actionKey:'enterprise.internship.application',actionParams:{applicationId:'28',campaignId:'7'}}
  await denied.vm.openAction();assert.equal(denied.pushed.length,0);assert.match(denied.vm.actionError.value,/没有查看学生申请/)
})

test('a late authority check cannot open an earlier message after selection changes',async t=>{
  const pending=deferred()
  const {vm,pushed}=mount(t,{messages:async()=>({items:[],total:0})},{load:()=>pending.promise,applicationViewAllowed:true})
  vm.selected.value={actionKey:'enterprise.internship.application',actionParams:{applicationId:'28',campaignId:'7'}}
  const work=vm.openAction();vm.selected.value={messageId:'different'};pending.resolve();await work
  assert.equal(pushed.length,0)
})

test('mobile detail can return to the list without changing message state',async t=>{
  const api={messages:async()=>({items:[],total:0})}
  const {vm}=mount(t,api)
  vm.selected.value={messageId:'18',readStatus:'READ'};vm.actionError.value='旧提示'
  vm.closeDetail()
  assert.equal(vm.selected.value,null);assert.equal(vm.actionError.value,'');assert.equal(vm.detailError.value,'')
  const source=fs.readFileSync(new URL('../src/views/EnterpriseMessagesView.vue',import.meta.url),'utf8')
  assert.match(source,/message-workspace\.detail-open \.message-list\{display:none\}/)
  assert.match(source,/返回消息列表/)
})

test('router, navigation and API expose one real enterprise inbox surface',()=>{
  const router=fs.readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8')
  const layout=fs.readFileSync(new URL('../src/layouts/EnterprisePortalLayout.vue',import.meta.url),'utf8')
  const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
  assert.match(router,/path: 'messages'.*EnterpriseMessagesView\.vue/)
  assert.match(layout,/to:'\/messages',label:'消息通知'/)
  for(const path of ['/messages`','/messages/count','/messages/${id}','/messages/${id}/read'])assert.ok(api.includes(path),path)
})
