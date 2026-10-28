import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { formatDateTime } from '../src/utils/format.js'

const pending={id:'9007199254740993003',internshipId:'9007199254740993002',consentType:'STUDENT',status:'PENDING',version:0,contentVersion:'合成正文第一版',contentHash:'saved-content-hash',contentSnapshot:'合成联调正文'}
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}

test('正文字号与阅读位置只影响阅读，不自动确认、不改正文或原版本',()=>{
  const p=page();p.vm.detail={...pending};p.vm.readFontSize=19
  p.component.onPageScroll.call(p.vm,{scrollTop:120});p.component.onReachBottom.call(p.vm)
  assert.equal(p.vm.readingEnd,true);assert.equal(p.vm.detail.version,pending.version);assert.equal(p.vm.detail.contentSnapshot,pending.contentSnapshot);assert.equal(p.vm.viewed,false);assert.deepEqual(p.calls,[])
  p.component.onPageScroll.call(p.vm,{scrollTop:0});assert.equal(p.vm.readingEnd,false);assert.equal(p.vm.readingScrolled,false)
})
function page(name='detail',api={}) {
  let generation=0,modal
  const calls=[],messages=[]
  const source=fs.readFileSync(new URL(`../src/pages/student-internship/consent/${name==='detail'?'detail.vue':'index.vue'}`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  const studentApi={getInternshipConsentDetail:async()=>({...pending}),viewInternshipConsent:async()=>({...pending,version:1,viewedAt:'2026-10-06'}),confirmInternshipConsent:async(id,body)=>{calls.push({id,body});return {...pending,status:'VALID',version:2}},...api}
  const deps={studentApi,studentInternshipConsents:api.list|| (async()=>[]),go:url=>calls.push(url),toast:text=>messages.push(text),getDeviceDigest:()=> 'synthetic-device',formatDateTime,currentSessionGeneration:()=>generation,normalizeError:e=>({pageState:e?.status===403?'forbidden':'error',text:'操作失败，请核对'}),uni:{showModal:opts=>{modal=opts},stopPullDownRefresh:()=>{}}}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data(),$nextTick:async()=>{}}
  for(const [name,fn]of Object.entries(component.methods))vm[name]=(...args)=>fn.apply(vm,args)
  for(const [name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:()=>fn.call(vm)})
  vm.id=pending.id;vm.batchId='9007199254740993001'
  return {vm,component,calls,messages,modal:()=>modal,switchAccount:()=>generation++}
}

test('正文显示后登记阅读，确认冻结同一原单的新版本与正文摘要',async()=>{
  let vm,current={...pending}
  const p=page('detail',{getInternshipConsentDetail:async()=>({...current}),viewInternshipConsent:async()=>{assert.equal(vm.state,'ready');assert.equal(vm.detail.contentSnapshot,pending.contentSnapshot);return {...pending,version:1,viewedAt:'2026-10-06'}},confirmInternshipConsent:async(id,body)=>{p.calls.push({id,body});current={...pending,status:'VALID',version:2,viewedAt:'2026-10-06'};return current}})
  vm=p.vm;await vm.load();vm.confirm();vm.confirm()
  assert.equal(vm.submitting,true)
  await p.modal().success({confirm:true})
  assert.deepEqual(p.calls,[{id:pending.id,body:{expectedVersion:1,contentVersion:pending.contentVersion,contentHash:pending.contentHash,deviceDigest:'synthetic-device'}}])
  assert.equal(vm.submitting,false)
  assert.equal(vm.detail.id,pending.id);assert.equal(vm.detail.status,'VALID');assert.equal(vm.detail.version,2)
  assert.equal(vm.detail.contentSnapshot,pending.contentSnapshot)
})

test('正文读取迟到且页面已隐藏，不登记阅读或回填旧正文',async()=>{
  const late=deferred();let views=0
  const p=page('detail',{getInternshipConsentDetail:()=>late.promise,viewInternshipConsent:async()=>{views++;return pending}})
  const loading=p.vm.load();p.component.onHide.call(p.vm);late.resolve(pending);await loading
  assert.equal(views,0);assert.equal(p.vm.detail,null);assert.equal(p.vm.viewed,false)
})

test('同一弹窗重复成功或失败回调不重复提交或提前解锁',async()=>{
  const writing=deferred();let writes=0
  const p=page('detail',{confirmInternshipConsent:()=>{writes++;return writing.promise}})
  await p.vm.load();p.vm.confirm();const modal=p.modal()
  const first=modal.success({confirm:true});await modal.success({confirm:true});modal.fail()
  assert.equal(writes,1);assert.equal(p.vm.submitting,true)
  writing.resolve({...pending,status:'VALID',version:2});await first;assert.equal(p.vm.submitting,false)
})

test('阅读登记未回读新版本前，两项写动作都不能发送',async()=>{
  const viewing=deferred();let writes=0
  const p=page('detail',{viewInternshipConsent:()=>viewing.promise,rejectInternshipConsent:async(id,body)=>{writes++;assert.equal(body.expectedVersion,1)}})
  const loading=p.vm.load();await Promise.resolve();await Promise.resolve()
  assert.equal(p.vm.state,'ready');p.vm.rejectReason='合成拒绝原因说明'
  p.vm.confirm();await p.vm.reject();assert.equal(p.modal(),undefined);assert.equal(writes,0)
  viewing.resolve({...pending,version:1,viewedAt:'2026-10-06'});await loading
  await p.vm.reject();assert.equal(writes,1)
})

for(const action of ['隐藏','换账号','换单据'])test(`${action}后旧确认弹窗不能发送请求`,async()=>{
  const p=page();await p.vm.load();p.vm.confirm()
  if(action==='隐藏')p.component.onHide.call(p.vm)
  if(action==='换账号')p.switchAccount()
  if(action==='换单据')p.vm.id='different-id'
  await p.modal().success({confirm:true})
  assert.equal(p.calls.length,0);assert.equal(p.messages.length,0)
})

test('数字业务冲突保留拒绝原因及原版本，不自动取新版并重试',async()=>{
  let reads=0
  const p=page('detail',{getInternshipConsentDetail:async()=>{reads++;return pending},rejectInternshipConsent:async()=>{throw {code:40900,bizCode:'DATA_CONFLICT'}}})
  await p.vm.load();p.vm.rejectReason='请重新核对合成实习安排';await p.vm.reject()
  assert.equal(reads,1);assert.equal(p.vm.detail.version,1);assert.equal(p.vm.rejectReason,'请重新核对合成实习安排')
  assert.equal(p.vm.viewed,false);assert.match(p.vm.actionError,/重新打开正文/);assert.equal(p.vm.submitting,false)
})

test('只读任务没有确认或拒绝请求，未知状态用中文说明',async()=>{
  for(const status of ['VALID','REVOKED','SUPERSEDED']){
    let rejects=0;const p=page('detail',{getInternshipConsentDetail:async()=>({...pending,status,viewedAt:'2026-10-06'}),rejectInternshipConsent:async()=>{rejects++}})
    await p.vm.load();p.vm.rejectReason='合成原因说明';p.vm.confirm();await p.vm.reject()
    assert.equal(p.modal(),undefined);assert.equal(rejects,0)
    assert.equal(p.vm.statusLabel('INTERNAL_UNKNOWN'),'状态待核对')
  }
})

test('列表隔离旧批次迟到响应，隐藏返回后重读，监护人不进入学生正文',async()=>{
  const first=deferred(),second=deferred();let n=0
  const p=page('list',{list:()=>++n===1?first.promise:second.promise})
  const a=p.vm.load();p.vm.batchId='new-batch';const b=p.vm.load()
  second.resolve([{...pending,id:'new'}]);await b;first.resolve([{...pending,id:'old'}]);await a
  assert.equal(p.vm.items[0].id,'new');p.vm.open({consentType:'GUARDIAN'});assert.equal(p.calls.length,0)
  p.vm.open({...p.vm.items[0],status:'VALID'})
  assert.equal(p.calls[0],'/pages/student-internship/consent/detail?id=new&batchId=new-batch')
  p.vm.open({...pending,status:'VALID'});assert.equal(p.calls.length,1)
  p.component.onHide.call(p.vm);p.component.onShow.call(p.vm);await Promise.resolve();await Promise.resolve()
  assert.equal(n,3);assert.equal(p.vm.statusLabel('INTERNAL_UNKNOWN'),'状态待核对')
  assert.ok(!p.vm.hint({status:'VALID',confirmedAt:'2026-10-05T23:20:41+00:00'}).includes('T'))
})
