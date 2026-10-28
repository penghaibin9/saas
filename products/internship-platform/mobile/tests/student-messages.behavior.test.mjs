import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
const id='9007199254740993123'
const message={messageId:id,title:'周报缺交提醒',summary:'应交两篇',contentPlain:'业务事实和学校附言',readStatus:'UNREAD',requireAck:true}
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
test('手机收件箱复用本人消息接口，编号保持字符串',async()=>{
  const calls=[]
  const source=fs.readFileSync(new URL('../src/services/studentApi.js',import.meta.url),'utf8').replace(/^import[^\n]*\n/gm,'').replace('export const studentApi','const studentApi').replace('export default studentApi','return studentApi')
  const api=new Function('realRequest','realDownload','internship',source)(async(...args)=>{calls.push(args)},()=>{},{})
  await api.getMessages(2);await api.getMessage(id);await api.readMessage(id)
  assert.deepEqual(calls,[[`/mobile/me/messages?page=2&pageSize=20`],[`/mobile/me/messages/${id}`],[`/mobile/me/messages/${id}/read`,{method:'POST'}]])
  await api.getMessages(1,'UNREAD');assert.equal(calls.at(-1)[0],'/mobile/me/messages?page=1&pageSize=20&readStatus=UNREAD')
})

test('已登记的消息动作以字符串编号准确打开原单，过期和未知动作不可跳转',()=>{
  const p=page();const params={reportId:id,batchId:'9007199254740993124',internshipId:'9007199254740993125',weekNo:'2'}
  p.vm.detail={...message,actionKey:'student.internship.weekly-report',actionParams:params};p.vm.openBusiness()
  assert.equal(p.links[0],'/pages/student/weekly-report/index?reportId='+id+'&batchId='+params.batchId+'&internshipId='+params.internshipId+'&weekNo=2')
  for(const extra of [{expired:true},{withdrawn:true},{actionKey:'unregistered'},{actionParams:{...params,reportId:'javascript:bad'}},{actionParams:{...params,batchId:'0'}}]){p.vm.detail={...message,actionKey:'student.internship.weekly-report',actionParams:params,...extra};p.vm.openBusiness();assert.equal(p.links.length,1)}
  p.vm.detail={actionKey:'student.internship.volunteer-result',actionParams:{groupId:id,groupVersion:0}};assert.match(p.vm.messageAction.path,/groupVersion=0$/)
})

test('返回同一收件箱保留页码，切换账号才重置筛选和页码',async()=>{
  const calls=[],p=page({getMessages:async(page,status)=>{calls.push([page,status]);return {items:[],total:60,page,hasMore:false}}})
  p.vm.page=3;p.vm.readFilter='UNREAD';p.component.onHide.call(p.vm);await p.component.onShow.call(p.vm)
  await Promise.resolve();assert.deepEqual(calls.at(-1),[3,'UNREAD']);p.switchAccount();await p.component.onShow.call(p.vm);await Promise.resolve();assert.deepEqual(calls.at(-1),[1,''])
})
function page(overrides={}){
  let generation=1,readCalls=0
  const api={getMessages:async page=>({items:[message],total:1,page,hasMore:false}),getMessage:async()=>({...message}),readMessage:async value=>{readCalls++;assert.equal(value,id);return {messageId:id,readStatus:'READ'}},...overrides}
  const source=fs.readFileSync(new URL('../src/pages/student-internship/messages/index.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const links=[]
  const component=new Function('studentApi','currentSessionGeneration','normalizeError','uni','go',script)(api,()=>generation,()=>({pageState:'error',text:'读取失败，请重试'}),{pageScrollTo(){}},path=>links.push(path))
  const vm={...component.data(),$nextTick:async()=>{}}
  for(const [name,fn] of Object.entries(component.methods))vm[name]=(...args)=>fn.apply(vm,args)
  for(const [name,fn] of Object.entries(component.computed))Object.defineProperty(vm,name,{get:()=>fn.call(vm)})
  return {vm,api,component,links,switchAccount:()=>generation++,readCalls:()=>readCalls}
}
test('打开正文不自动已读，主动已读保留确认要求和精确编号',async()=>{
  const p=page();await p.vm.load();await p.vm.openMessage(id);assert.equal(p.readCalls(),0);assert.equal(p.vm.detail.readStatus,'UNREAD')
  await p.vm.markRead();assert.equal(p.readCalls(),1);assert.equal(p.vm.detail.readStatus,'READ');assert.equal(p.vm.items[0].readStatus,'READ');assert.equal(p.vm.detail.requireAck,true)
  await p.vm.markRead();assert.equal(p.readCalls(),1)
})
test('已读失败保留未读，重复点击不重复写入',async()=>{
  const wait=deferred();let calls=0;const p=page({readMessage:()=>{calls++;return wait.promise}});await p.vm.load();await p.vm.openMessage(id)
  const pending=p.vm.markRead();await p.vm.markRead();assert.equal(calls,1);wait.resolve({messageId:'other',readStatus:'READ'});await pending
  assert.equal(p.vm.detail.readStatus,'UNREAD');assert.equal(p.vm.items[0].readStatus,'UNREAD');assert.equal(p.vm.readError,'读取失败，请重试')
})
test('切换身份和隐藏页面丢弃迟到列表、正文及已读回执',async()=>{
  const list=deferred(),p=page({getMessages:()=>list.promise});const pending=p.vm.load();p.switchAccount();list.resolve({items:[message],total:1,page:1});await pending;assert.deepEqual(p.vm.items,[])
  const detail=deferred(),q=page({getMessage:()=>detail.promise});await q.vm.load();const opening=q.vm.openMessage(id);q.vm.pause();detail.resolve(message);await opening;assert.equal(q.vm.detail,null)
  const read=deferred(),r=page({readMessage:()=>read.promise});await r.vm.load();await r.vm.openMessage(id);const marking=r.vm.markRead();r.vm.pause();r.switchAccount();read.resolve({messageId:id,readStatus:'READ'});await marking;assert.equal(r.vm.detail,null);assert.deepEqual(r.vm.items,[])
})
test('翻页只采用最新请求，失败不能显示为空数据',async()=>{
  const old=deferred(),p=page({getMessages:page=>page===1?old.promise:Promise.resolve({items:[],total:20,page:2,hasMore:false})});const pending=p.vm.load();await p.vm.load(2);old.resolve({items:[message],total:21,page:1,hasMore:true});await pending
  assert.equal(p.vm.page,2);assert.deepEqual(p.vm.items,[])
  p.api.getMessages=async()=>{throw Error('private raw error')};await p.vm.load(2);assert.equal(p.vm.state,'error');assert.equal(p.vm.error,'读取失败，请重试')
})
