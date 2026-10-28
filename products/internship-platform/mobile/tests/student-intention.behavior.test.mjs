import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const context={batchId:'2673',internshipId:'722'}
const dto=(intention=null)=>({hasData:true,...context,intention,canEdit:!intention||intention.status!=='WITHDRAWN',canSubmit:!!intention&&['DRAFT','WITHDRAWN'].includes(intention.status),canWithdraw:intention?.status==='SUBMITTED',positions:[],positionsPage:1,positionsTotal:0,positionsHasMore:false})
function page(api={}){
  const source=fs.readFileSync(new URL('../src/pages/student-internship/intention/index.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...source.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,s])=>s.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  let generation=0,modal;const notices=[]
  const deps={studentApi:{getInternship:async()=>({hasBatch:true,batchId:'2673',recordId:'722'}),getInternshipIntention:async()=>dto(),...api},toast:text=>notices.push(text),currentSessionGeneration:()=>generation,formatDateTime:value=>value,normalizeError:error=>({text:error.message||'请求失败'}),uni:{showModal:options=>{modal=options}}}
  names.push('uni');const component=new Function(...names,source.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...names.map(name=>deps[name]??{}))
  const vm={...component.data()};for(const [key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn]of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  return{vm,component,notices,modal:()=>modal,switchAccount:()=>generation++}
}
test('意向未读取成功不能保存提交撤回，先解析指定本人批次再读取',async()=>{
  let writes=0;const calls=[]
  const p=page({getInternship:async batch=>{calls.push(['dashboard',batch]);return{batchId:'2673',recordId:'722',hasBatch:true}},getInternshipIntention:async(...args)=>{calls.push(['intention',...args]);throw Error('读取失败')},saveInternshipIntention:async()=>writes++,submitInternshipIntention:async()=>writes++,withdrawInternshipIntention:async()=>writes++})
  assert.equal(p.vm.canEdit,false);await p.vm.save();await p.vm.submit();p.vm.withdraw();assert.equal(writes,0)
  p.vm.requestedBatchId='2673';await p.vm.load();assert.deepEqual(calls,[['dashboard','2673'],['intention','2673','722',1]])
  assert.equal(p.vm.pageState,'error');assert.equal(p.vm.canEdit,false)
})
test('意向保存携带打开时版本，冲突保留正文原版本并须明确采用回读',async()=>{
  const original={id:'91',version:2,status:'DRAFT',preferredCity:'原城市',intentionNote:'旧内容'}
  let latest=original,sent
  const p=page({getInternshipIntention:async()=>dto(latest),saveInternshipIntention:async body=>{sent=body;throw{bizCode:'DATA_CONFLICT',message:'版本变化'}}})
  await p.vm.load();p.vm.form.intentionNote='未提交修改';await p.vm.save()
  assert.equal(sent.id,'91');assert.equal(sent.expectedVersion,2);assert.equal(sent.batchId,'2673');assert.equal(sent.internshipId,'722')
  assert.equal(p.vm.form.intentionNote,'未提交修改');assert.equal(p.vm.meta.intention.version,2);assert.ok(p.vm.conflict)
  latest={...original,version:3,intentionNote:'另一端内容'};await p.vm.rereadConflict()
  assert.equal(p.vm.form.intentionNote,'未提交修改');assert.equal(p.vm.meta.intention.version,2)
  p.vm.adoptLatest();assert.equal(p.vm.form.intentionNote,'未提交修改');assert.equal(p.vm.meta.intention.version,3)
})
test('意向读取和撤回确认在离页或换账号后不能作用于旧原单',async()=>{
  let resolve;const waiting=new Promise(done=>resolve=done)
  const p=page({getInternship:()=>waiting});const pending=p.vm.load();p.component.onHide.call(p.vm);resolve({batchId:'2673',recordId:'722'});await pending;assert.notEqual(p.vm.pageState,'ready')
  let writes=0;const q=page({getInternshipIntention:async()=>dto({id:'91',version:3,status:'SUBMITTED'}),withdrawInternshipIntention:async()=>writes++})
  await q.vm.load();q.vm.withdraw();q.switchAccount();await q.modal().success({confirm:true});assert.equal(writes,0)
})

test('意向提交沿保存返回的原单版本继续，不另取新版覆盖',async()=>{
  let reads=0;const sent=[]
  const p=page({getInternshipIntention:async()=>{reads++;return dto({id:'91',version:2,status:'DRAFT'})},saveInternshipIntention:async body=>{sent.push(['save',body]);return dto({id:'91',version:3,status:'DRAFT'})},submitInternshipIntention:async body=>{sent.push(['submit',body]);return dto({id:'91',version:4,status:'SUBMITTED'})}})
  await p.vm.load();p.vm.form.intentionNote='本人当前草稿';await p.vm.submit()
  assert.equal(sent[0][1].expectedVersion,2);assert.equal(sent[1][1].expectedVersion,3);assert.equal(sent[1][1].id,'91');assert.equal(reads,1)
  assert.equal(p.vm.meta.intention.version,4);assert.equal(p.vm.form.intentionNote,'本人当前草稿')
})

test('意向实际客户端四方法都使用明确上下文正式路由和写入版本',async()=>{
  const calls=[];const source=fs.readFileSync(new URL('../src/services/studentApi.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const studentApi','const studentApi').replace('export default studentApi','return studentApi')
  const api=new Function('realRequest','realDownload','internship',source)(async(path,options)=>{calls.push([path,options]);return{}},()=>{}, {})
  const body={...context,id:'91',expectedVersion:0}
  await api.getInternshipIntention('2673','722',2);await api.saveInternshipIntention(body);await api.submitInternshipIntention(body);await api.withdrawInternshipIntention(body)
  assert.equal(calls[0][0],'/mobile/internship/context/intention?batchId=2673&internshipId=722&page=2')
  assert.deepEqual(calls.slice(1).map(([path,options])=>[path,options.method,options.data]),[
    ['/mobile/internship/context/intention','PUT',body],['/mobile/internship/context/intention/submit','POST',body],['/mobile/internship/context/intention/withdraw','POST',body]])
})
