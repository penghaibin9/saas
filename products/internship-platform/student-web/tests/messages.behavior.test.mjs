import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { ref, reactive, computed, watch, effectScope, nextTick } from 'vue'
import { INTERNSHIP_TAB_GROUPS } from '../src/platform/internshipNavigation.js'

const read=relative=>fs.readFileSync(new URL('../../' + relative,import.meta.url),'utf8')
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
const pageResult=(items=[],page=1,total=items.length)=>({items,page,total,hasMore:page*20<total})
const flush=async()=>{await nextTick();await Promise.resolve();await nextTick()}

function component(t,relative,api={}) {
  const session=reactive({user:{userId:'18',tenantId:'11',roleCode:'STUDENT'}})
  const route=reactive({path:'/messages',fullPath:'/messages',query:{}}),scope=effectScope(),events=[]
  let generation=1,unmount=[]
  const deps={ref,reactive,computed,watch,nextTick,onBeforeUnmount:fn=>unmount.push(fn),
    useSessionStore:()=>session,usePortalConfigStore:()=>({brand:{},config:{}}),useRoute:()=>route,
    useRouter:()=>({push(value){route.path=typeof value==='string'?value:value.path;route.fullPath=route.path},replace(value){route.path=value.path;route.query=value.query;route.fullPath=value.path+'?'+new URLSearchParams(value.query)}}),
    currentSessionGeneration:()=>generation,portalApi:{messages:async p=>pageResult([],p.page),messageCount:async()=>({unread:0}),...api},
    defineEmits:()=>()=>{},WORKSPACE_THEMES:[],normalizeTheme:v=>v||'blue',themeTokens:()=>({}),INTERNSHIP_TABS:[],INTERNSHIP_TAB_GROUPS,fileSdk:{},
    localStorage:{getItem:()=>null,setItem(){}},window:{addEventListener(){},removeEventListener(){},dispatchEvent:e=>events.push(e.type)}}
  const script=parse(read(relative)).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const names=relative.includes('MessagesView')?['employmentMessageVersion','messageAction','openBusiness','items','total','page','filter','hasMore','loading','error','detail','detailLoading','detailError','detailPanel','readBusy','readError','receipt','loadList','openMessage','markRead','applyFilter','changePage']:['unread','countError','messageTitle','reloadUnread','goMsg']
  const vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {'+names.join(',')+'}')(...Object.values(deps)))
  const close=()=>{unmount.forEach(fn=>fn());unmount=[];scope.stop()}
  t.after(close)
  return {vm,session,route,events,close,logout:()=>generation++}
}

test('候选消息页及原外壳模板、脚本可编译',()=>{
  for(const relative of ['student-web/src/views/MessagesView.vue','student-web/src/layouts/PortalLayoutV5.vue']){
    const source=read(relative),descriptor=parse(source,{filename:relative})
    assert.deepEqual(descriptor.errors,[]);compileScript(descriptor.descriptor,{id:relative})
    assert.deepEqual(compileTemplate({source:descriptor.descriptor.template.content,filename:relative,id:relative}).errors,[])
  }
})

test('就业核验通知标注本条原版本，不拿旧回执代表当前更正版',t=>{
  const {vm}=component(t,'student-web/src/views/MessagesView.vue')
  const message={actionKey:'student.internship.employment-registration',actionParams:{registrationId:'106',revisionNo:2}}
  vm.detail.value=message;assert.equal(vm.employmentMessageVersion.value,2)
  vm.detail.value={...message,actionParams:{...message.actionParams,revisionNo:4}};assert.equal(vm.employmentMessageVersion.value,4)
  for(const invalid of [{withdrawn:true},{expired:true},{actionKey:'unknown'},{actionParams:{revisionNo:'4'}},{actionParams:{revisionNo:true}}]){
    vm.detail.value={...message,...invalid};assert.equal(vm.employmentMessageVersion.value,null)
  }
})
test('周报消息只重建受限原单入口，过期撤回和不可信参数不跳转、不自动已读',t=>{
  const {vm,route}=component(t,'student-web/src/views/MessagesView.vue')
  const row={messageId:'1',readStatus:'UNREAD',actionKey:'student.internship.weekly-report',actionParams:{reportId:'9007199254741001',batchId:'9007199254741002',internshipId:'9007199254741003'},actionUrl:'https://invalid.example/private'}
  vm.detail.value=row;assert.deepEqual(vm.messageAction.value,{label:'查看周报原单',path:'/internship',query:{view:'report',reportType:'WEEKLY',reportId:'9007199254741001',batchId:'9007199254741002'}})
  vm.openBusiness();assert.equal(route.path,'/internship');assert.equal(vm.detail.value.readStatus,'UNREAD')
  for(const bad of [{expired:true},{withdrawn:true},{actionKey:'UNKNOWN_INTERNAL'},{actionParams:{...row.actionParams,reportId:'../other'}}]){vm.detail.value={...row,...bad};assert.equal(vm.messageAction.value,null)}
})

test('消息详情不自动已读，明确已读后回读列表并通知铃铛',async t=>{
  const reads=[],{vm,events}=component(t,'student-web/src/views/MessagesView.vue',{
    messages:async p=>pageResult([{messageId:'9007199254741001',title:'催交报告',readStatus:reads.length?'READ':'UNREAD'}],p.page),
    messageDetail:async id=>({messageId:id,title:'催交报告',contentPlain:'<script>仅文本</script>',readStatus:'UNREAD'}),
    readMessage:async id=>{reads.push(id);return {messageId:id,readStatus:'READ'}}})
  await flush();await vm.openMessage('9007199254741001');assert.deepEqual(reads,[])
  assert.equal(vm.detail.value.contentPlain,'<script>仅文本</script>')
  await vm.markRead();assert.deepEqual(reads,['9007199254741001']);assert.equal(vm.detail.value.readStatus,'READ')
  assert.equal(vm.items.value[0].readStatus,'READ');assert.deepEqual(events,['internship-message-read'])
})

test('查询保留阅读筛选并按服务端分页，失败不伪造空列表成功',async t=>{
  let fail=false;const calls=[],{vm,route}=component(t,'student-web/src/views/MessagesView.vue',{
    messages:async p=>{calls.push(p);if(fail)throw Error('读取失败');return pageResult([{messageId:'16'}],p.page,41)}})
  await flush();vm.filter.value='UNREAD';await vm.applyFilter();await flush()
  assert.equal(route.query.readStatus,'UNREAD');assert.equal(calls.at(-1).readStatus,'UNREAD')
  await vm.changePage(2);await flush();assert.equal(calls.at(-1).page,2);assert.equal(vm.total.value,41)
  fail=true;await vm.loadList();assert.equal(vm.error.value,'读取失败');assert.equal(vm.loading.value,false)
})

test('迟到列表和正文不能覆盖新学校或新消息，旧请求不解除新读取状态',async t=>{
  const oldList=deferred(),oldDetail=deferred();let listReads=0
  const {vm,session}=component(t,'student-web/src/views/MessagesView.vue',{
    messages:async p=>++listReads===1?oldList.promise:pageResult([{messageId:'new'}],p.page),
    messageDetail:id=>id==='old'?oldDetail.promise:Promise.resolve({messageId:id,readStatus:'UNREAD'})})
  session.user.tenantId='12';await flush();oldList.resolve(pageResult([{messageId:'old'}]));await flush()
  assert.equal(vm.items.value[0].messageId,'new')
  const old=vm.openMessage('old');await vm.openMessage('new');oldDetail.resolve({messageId:'old'});await old
  assert.equal(vm.detail.value.messageId,'new');assert.equal(vm.detailLoading.value,false)
})

test('已读失败保留正文，旧会话迟到结果不能改新身份状态或触发铃铛',async t=>{
  const wait=deferred(),{vm,logout,events}=component(t,'student-web/src/views/MessagesView.vue',{
    messageDetail:async id=>({messageId:id,readStatus:'UNREAD',contentPlain:'原消息'}),readMessage:()=>wait.promise})
  await flush();await vm.openMessage('16');const pending=vm.markRead();logout();vm.readBusy.value=true
  wait.resolve({messageId:'16',readStatus:'READ'});await pending
  assert.equal(vm.detail.value.readStatus,'UNREAD');assert.equal(vm.readBusy.value,true);assert.deepEqual(events,[])
  const failed=component(t,'student-web/src/views/MessagesView.vue',{messageDetail:async id=>({messageId:id,readStatus:'UNREAD',contentPlain:'原消息'}),readMessage:async()=>{throw Error('保存失败')}})
  await flush();await failed.vm.openMessage('16');await failed.vm.markRead()
  assert.equal(failed.vm.detail.value.contentPlain,'原消息');assert.equal(failed.vm.detail.value.readStatus,'UNREAD');assert.equal(failed.vm.readError.value,'保存失败')
})

test('铃铛真实计数、消息导航、错误及迟到响应隔离',async t=>{
  const wait=deferred();let reads=0,fail=false
  const {vm,session,route}=component(t,'student-web/src/layouts/PortalLayoutV5.vue',{
    messageCount:async()=>++reads===1?wait.promise:fail?Promise.reject(Error('计数失败')):{unread:2}})
  session.user.userId='19';await flush();wait.resolve({unread:99});await flush();assert.equal(vm.unread.value,2)
  vm.goMsg();assert.equal(route.path,'/messages')
  fail=true;await vm.reloadUnread();assert.equal(vm.unread.value,null);assert.equal(vm.countError.value,true)
})

test('点击消息立即聚焦并滚动到正文加载区，读取失败仍显示在该区',async t=>{
  const wait=deferred(),calls=[],{vm}=component(t,'student-web/src/views/MessagesView.vue',{messageDetail:()=>wait.promise})
  await flush();vm.detailPanel.value={focus:()=>calls.push('focus'),scrollIntoView:options=>calls.push(options)}
  const pending=vm.openMessage('16');await flush()
  assert.equal(vm.detailLoading.value,true);assert.deepEqual(calls,['focus',{block:'start'}])
  wait.reject(Error('正文读取失败'));await pending
  assert.equal(vm.detailLoading.value,false);assert.equal(vm.detailError.value,'正文读取失败')
})


test('志愿消息沿原组与零版本进入结果，不采纳外部地址或不可信参数',t=>{
  const {vm,route}=component(t,'student-web/src/views/MessagesView.vue')
  const row={actionKey:'student.internship.volunteer-result',actionParams:{groupId:'9007199254740993',groupVersion:0},actionUrl:'https://invalid.example'}
  vm.detail.value=row;assert.deepEqual(vm.messageAction.value,{path:'/internship/volunteer-result',query:{groupId:'9007199254740993',groupVersion:'0'},label:'查看志愿原单'});vm.openBusiness();assert.equal(route.path,'/internship/volunteer-result')
  for(const bad of [{expired:true},{withdrawn:true},{actionParams:{groupId:'1',groupVersion:-1}},{actionParams:{groupId:['1','2'],groupVersion:'0'}}]){vm.detail.value={...row,...bad};assert.equal(vm.messageAction.value,null)}
})
