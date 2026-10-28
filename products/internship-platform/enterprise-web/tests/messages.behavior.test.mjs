import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { requireDecimalId } from '../src/services/evaluationContext.js'

const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function mount(t,api,contextPatch={}){
  const scope=effectScope(),handlers={},pushed=[],selectedCampaigns=[],navigated=[]
  const context=reactive({scopeKey:'original-member',contextEpoch:1,unreadMessages:1,recruitmentContextReady:true,campaign:{id:'7'},loadMessageCount:async()=>{context.unreadMessages=0},load:async()=>{},...contextPatch})
  api={context:async campaignId=>({campaignId:String(campaignId),memberRole:'HR'}),...api}
  const script=parse(fs.readFileSync(new URL('../src/views/EnterpriseMessagesView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+'\nreturn {load,openMessage,openAction,closeDetail,rows,total,page,readStatus,selected,error,detailError,actionError}'
  const vm=scope.run(()=>new Function('computed','onBeforeUnmount','ref','watch','useRouter','enterpriseInternshipApi','useEnterpriseContextStore','requireDecimalId','hasEnterpriseAuth','window',script)(computed,fn=>{handlers.unmount=fn},ref,(source,fn,options)=>watch(source,fn,options),()=>({resolve:value=>{pushed.push(value);return {href:contextPatch.routeHref||`/enterprise${value.path}?campaignId=${value.query.campaignId}`}}}),api,()=>context,requireDecimalId,()=>context.loggedIn!==false,{location:{href:'http://localhost:5422/enterprise/messages',origin:'http://localhost:5422',assign:href=>navigated.push(href)}}))
  t.after(()=>{handlers.unmount();scope.stop()})
  return {vm,context,pushed,selectedCampaigns,navigated,handlers}
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
  const {vm,pushed,selectedCampaigns,navigated}=mount(t,api)
  vm.selected.value={actionKey:'enterprise.internship.position',actionParams:{positionId:'18',campaignId:'7'}}
  await vm.openAction()
  assert.deepEqual(selectedCampaigns,[]);assert.deepEqual(navigated,['/enterprise/positions/18/edit?campaignId=7']);assert.deepEqual(pushed,[{path:'/positions/18/edit',query:{campaignId:'7'}}])
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
  const {vm,pushed}=mount(t,{messages:async()=>({items:[],total:0}),context:()=>pending.promise},{applicationViewAllowed:true})
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

test('same and other authorized campaign actions navigate freshly without unloading the message during a context reload',async t=>{
  for(const campaignId of ['7','9']){
    let checks=0
    const {vm,pushed,navigated}=mount(t,{messages:async()=>({items:[],total:0}),context:async id=>{checks++;return {campaignId:id,memberRole:'HR'}}},{applicationViewAllowed:true,load:()=>{throw new Error('刷新上下文会卸载原页')}})
    vm.selected.value={actionKey:'enterprise.internship.application',actionParams:{applicationId:'9007199254740993111',campaignId}}
    await vm.openAction();assert.equal(checks,1)
    assert.deepEqual(navigated,[`/enterprise/applications/9007199254740993111?campaignId=${campaignId}`])
    assert.equal(pushed[0].query.campaignId,campaignId)
  }
})

test('failed authority, changed scope, logout and unmount cannot navigate an old message',async t=>{
  for(const change of ['failure','scope','epoch','logout','unmount','role','campaign']){
    const pending=deferred(),p=mount(t,{messages:async()=>({items:[],total:0}),context:()=>pending.promise},{applicationViewAllowed:true})
    p.vm.selected.value={actionKey:'enterprise.internship.application',actionParams:{applicationId:'28',campaignId:'7'}}
    const work=p.vm.openAction()
    if(change==='scope')p.context.scopeKey='another-member'
    if(change==='epoch')p.context.contextEpoch++
    if(change==='logout')p.context.loggedIn=false
    if(change==='unmount')p.handlers.unmount()
    if(change==='failure')pending.resolve(Promise.reject(new Error('授权已撤销')))
    else pending.resolve({campaignId:change==='campaign'?'9':'7',memberRole:change==='role'?'MENTOR':'HR'})
    await work;assert.equal(p.navigated.length,0,change)
  }
})

test('invalid ids, ended sessions and external destinations cannot navigate a message',async t=>{
  for(const patch of [{positionId:'0'},{positionId:Number.MAX_SAFE_INTEGER+1},{campaignId:'../7'},{positionId:'12345678901234567890'}]){
    let calls=0
    const {vm,navigated}=mount(t,{messages:async()=>({items:[],total:0}),context:async()=>{calls++;return {campaignId:'7'}}})
    vm.selected.value={actionKey:'enterprise.internship.position',actionParams:{positionId:'18',campaignId:'7',...patch}}
    await vm.openAction();assert.equal(calls,0);assert.equal(navigated.length,0)
  }
  let calls=0
  const ended=mount(t,{messages:async()=>({items:[],total:0}),context:async()=>{calls++}},{loggedIn:false})
  ended.vm.selected.value={actionKey:'enterprise.internship.position',actionParams:{positionId:'18',campaignId:'7'}}
  await ended.vm.openAction();assert.equal(calls,0);assert.match(ended.vm.actionError.value,/登录状态已失效/)
  const external=mount(t,{messages:async()=>({items:[],total:0})},{routeHref:'https://example.invalid/enterprise/positions/18/edit'})
  external.vm.selected.value={actionKey:'enterprise.internship.position',actionParams:{positionId:'18',campaignId:'7'}}
  await external.vm.openAction();assert.equal(external.navigated.length,0);assert.match(external.vm.actionError.value,/不属于当前系统/)
})

test('router, navigation and API expose one real enterprise inbox surface',()=>{
  const router=fs.readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8')
  const layout=fs.readFileSync(new URL('../src/layouts/EnterprisePortalLayout.vue',import.meta.url),'utf8')
  const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
  assert.match(router,/path: 'messages'.*EnterpriseMessagesView\.vue/)
  assert.match(layout,/to:'\/messages',label:'消息通知'/)
  for(const path of ['/messages`','/messages/count','/messages/${id}','/messages/${id}/read'])assert.ok(api.includes(path),path)
})
