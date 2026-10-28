import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const batch='9007199254740993101',id='9007199254740993102'
const own={id,batchId:batch,internId:'9007199254740993103',version:0,status:'PENDING_STUDENT',renderedBody:'非约束合成正文',fileId:'9007199254740993104'}
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
function page(api={}){
  let generation=1;const calls=[],modals=[],files=[]
  const deps={studentApi:{getInternship:async()=>({batchId:batch,recordId:own.internId}),getInternshipAgreements:async()=>[own,{...own,id:'other',batchId:'other-batch'}],getInternshipAgreementDetail:async()=>({...own}),confirmInternshipAgreement:async(...args)=>{calls.push(args);return {...own,status:'PENDING_ENTERPRISE'}},...api},
    toast(){},currentSessionGeneration:()=>generation,openBusinessFile:async(...args)=>files.push(args),uni:{showModal:options=>modals.push(options)}}
  const source=fs.readFileSync(new URL('../src/pages/student-internship/agreement/index.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm=component.data()
  for(const [key,fn]of Object.entries(component.methods))vm[key]=fn.bind(vm)
  vm.requestedBatchId=batch
  return {vm,component,calls,modals,files,logout:()=>generation++}
}

test('协议按原批次筛选，打开和关闭详情保留原列表',async()=>{
  const p=page();await p.vm.loadList();assert.deepEqual(p.vm.list.map(x=>x.id),[id])
  p.vm.list=[own,{...own,id:'same-batch-second'}];await p.vm.openDetail(own);p.vm.closeDetail()
  assert.equal(p.vm.list.length,2);assert.equal(p.vm.requestedBatchId,batch)
})

test('协议列表按当前批次取本人原记录，拒绝错批次且大编号保持字符串',async()=>{
  const reads=[],p=page({getInternship:async selected=>{reads.push(['context',selected]);return{batchId:batch,recordId:own.internId}},getInternshipAgreements:async(...args)=>{reads.push(['agreements',...args]);return[own]}})
  await p.vm.loadList();assert.deepEqual(reads,[['context',batch],['agreements',batch,own.internId]])
  const q=page({getInternship:async()=>({batchId:'other',recordId:own.internId}),getInternshipAgreements:()=>assert.fail('wrong context')})
  await q.vm.loadList();assert.equal(q.vm.pageState,'error');assert.deepEqual(q.vm.list,[])
})

test('协议列表真实请求携带批次和原实习记录，不再读默认批次',async()=>{
  const source=fs.readFileSync(new URL('../src/services/internshipApi.js',import.meta.url),'utf8').replace(/^import[^\n]+/gm,'').replace(/export const /g,'const ')
  const urls=[],api=new Function('realRequest',source+';return {studentInternshipAgreements}')(url=>urls.push(url))
  await api.studentInternshipAgreements(batch,own.internId)
  const params=new URL(urls[0],'http://test').searchParams
  assert.equal(params.get('batchId'),batch);assert.equal(params.get('internshipId'),own.internId)
})

test('协议错批次和迟到会话读取不能显示为当前协议',async()=>{
  const p=page({getInternshipAgreementDetail:async()=>({...own,batchId:'foreign'})});await p.vm.openExactDetail(id)
  assert.equal(p.vm.pageState,'error');assert.equal(p.vm.detail,null)
  const wait=deferred(),q=page({getInternshipAgreements:()=>wait.promise});const reading=q.vm.loadList();q.logout();wait.resolve([own]);await reading;assert.deepEqual(q.vm.list,[])
})

test('协议确认冻结原单版本，切对象或离页后的旧确认不会发送命令',async()=>{
  const p=page();p.vm.detail={...own};p.vm.confirm();p.vm.detail.version=8;p.modals[0].success({confirm:true})
  assert.equal(p.calls[0][0],id);assert.equal(p.calls[0][1].expectedVersion,0);assert.equal(p.calls[0][1].batchId,batch)
  const q=page();q.vm.detail={...own};q.vm.openReject();q.component.onHide.call(q.vm);q.modals[0].success({confirm:true,content:'合成拒绝说明'});assert.equal(q.calls.length,0)
  const r=page();r.vm.detail={...own};r.vm.confirm();r.vm.detail={...own,id:'different'};r.modals[0].success({confirm:true});assert.equal(r.calls.length,0)
})

test('协议附件沿原文件编号授权打开，已办或旧会话不能误提交确认',async()=>{
  const p=page();p.vm.detail={...own,status:'EFFECTIVE'};p.vm.confirm();p.vm.openReject();assert.equal(p.modals.length,0)
  await p.vm.openAttachment();assert.deepEqual(p.files,[[own.fileId,'三方协议签署件']]);p.logout();await p.vm.openAttachment();assert.equal(p.files.length,1)
})
