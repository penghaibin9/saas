import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { INTERNSHIP_TABS as tabs } from '../src/platform/internshipNavigation.js'

const ctx = { hasData: true, batchId: '9007199254741001', recordId: '9007199254741002', status: 'READY' }
const original = { id: '9007199254741003', internId: ctx.recordId, batchId: ctx.batchId, status: 'PENDING_STUDENT', version: 3, enterpriseName: '协议自身企业', positionName: '协议自身岗位', renderedBody: '已保存正文\n<script>仍作为文本展示</script>' }
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b }); return { promise,resolve,reject } }
async function page(t, overrides = {}, confirm = async () => true) {
  let generation = 1, saved = { ...original }
  const calls=[],notices=[],lifecycle={},downloads=[],timers=[],blobs=[],scope=effectScope(),document={ hidden:false,
    body:{ appendChild:link => downloads.push(link) }, createElement:tag => ({ tag,click(){ this.clicked=true },remove(){ this.removed=true } }) }
  const api = { agreement:async id => { calls.push(['detail',id]); return {...saved} }, agreements:async () => [saved],
    confirmAgreement:async (id,body) => { calls.push(['confirm',id,body]); saved={...saved,version:4,status:body.action === 'REJECT' ? 'REJECTED' : 'PENDING_ENTERPRISE'}; return {...saved} },
    agreementPdf:async (id,body) => { calls.push(['pdf',id,body]); return { agreementId:id,agreementVersion:body.expectedVersion,batchId:ctx.batchId,internshipId:ctx.recordId,mediaType:'application/pdf',filename:'当前协议打印件.pdf',contentBase64:btoa('%PDF-1.4\nsynthetic unit bytes') } }, ...overrides }
  const deps={tabs,computed,reactive,ref,watch,onMounted:fn=>{lifecycle.mount=fn},onBeforeUnmount:fn=>{lifecycle.unmount=fn},
    useUiStore:()=>({notify:value=>notices.push(value)}),useSessionStore:()=>({user:{tenantId:'11',userId:'18'}}),
    useRoute:()=>({query:{}}),useRouter:()=>({replace(){},push(){}}),currentSessionGeneration:()=>generation,
    portalApi:{},fileSdk:{},scanState(){},scanFilesReady(){},refreshScanFiles(){},systemPrompt(){},systemConfirm:confirm,
    internshipCoreApi:api,document,URL:{createObjectURL:blob=>{blobs.push(blob);return 'blob:synthetic'},revokeObjectURL:url=>calls.push(['revoke',url])},setTimeout:fn=>{timers.push(fn);return 0}}
  const script=parse(fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const names=['my','tab','sourceStates','agreements','currentAction','activeAgreement','agreementDetail','agreementReading','agreementBusy','agreementReason','agreementError','agreementConflict','agreementReceipt','agreementCanAct','agreementCanPrint','agreementStatusText','openAgreement','confirmAgreement','printAgreement','resetSourceStates','selectTab']
  const vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {'+names.join(',')+'}')(...Object.values(deps)))
  t.after(()=>{lifecycle.unmount?.();scope.stop()}); vm.my.value={...ctx};vm.tab.value='agreement';vm.sourceStates.agreement.status='data';await nextTick()
  return {vm,calls,api,document,downloads,timers,blobs,notices,lifecycle,logout:()=>generation++}
}

test('打开指定正文后用本人已阅读版本提交，不能临时换成最新版',async t=>{
  const p=await page(t);await p.vm.openAgreement(original)
  assert.equal(p.vm.agreementDetail.value.renderedBody,original.renderedBody)
  assert.equal(p.vm.agreementDetail.value.enterpriseName,original.enterpriseName)
  p.api.agreement=async id=>{p.calls.push(['detail',id]);return {...original,status:'PENDING_ENTERPRISE',version:4}}
  await p.vm.confirmAgreement('CONFIRM')
  assert.deepEqual(p.calls.find(x=>x[0]==='confirm').slice(1),[original.id,{batchId:ctx.batchId,internshipId:ctx.recordId,action:'CONFIRM',reason:'',expectedVersion:3}])
  assert.equal(p.calls.filter(x=>x[0]==='detail').length,2)
  assert.equal(p.vm.agreementReceipt.value.readback,true);assert.equal(p.vm.agreementCanAct.value,false)
})

test('进入协议页重新读取预加载后的新下发，读取期间重复进入不重复请求',async t=>{
  const pending=deferred();let reads=0
  const p=await page(t,{agreements:context=>{assert.deepEqual(context,{batchId:ctx.batchId,internshipId:ctx.recordId});reads++;return pending.promise}})
  p.vm.sourceStates.agreement.status='empty'
  p.vm.selectTab('agreement');await nextTick();assert.equal(reads,1)
  p.vm.selectTab('agreement');await nextTick();assert.equal(reads,1)
  pending.resolve([original])
  for(let i=0;i<8;i++){await Promise.resolve();await nextTick()}
  assert.equal(p.vm.agreementDetail.value.id,original.id)
  assert.equal(p.vm.agreementCanAct.value,true)
})

test('冲突保留原正文、版本和原因，主动重读后才可再次提交',async t=>{
  const p=await page(t,{confirmAgreement:async()=>{throw {bizCode:'DATA_CONFLICT',message:'RAW_INTERNAL'}}})
  await p.vm.openAgreement(original);p.vm.agreementReason.value='请学校核实正文中的企业安排'
  await p.vm.confirmAgreement('REJECT');await p.vm.confirmAgreement('REJECT')
  assert.equal(p.vm.agreementDetail.value.version,3);assert.equal(p.vm.agreementDetail.value.renderedBody,original.renderedBody)
  assert.equal(p.vm.agreementConflict.value,true);assert.equal(p.vm.agreementCanAct.value,false)
  assert.equal(p.calls.filter(x=>x[0]==='detail').length,1);assert.ok(p.vm.agreementError.value.includes('原正文'));assert.ok(!p.vm.agreementError.value.includes('RAW_INTERNAL'))
  p.api.agreement=async()=>({...original,version:5,renderedBody:'学校修订后的正文'})
  await p.vm.openAgreement(original);assert.equal(p.vm.agreementDetail.value.version,5);assert.equal(p.vm.agreementCanAct.value,true)
  assert.equal(p.vm.agreementReason.value,'请学校核实正文中的企业安排')
})

test('缺正文、历史和未知状态不确认，弹框前锁定并拒绝迟到的跨账号操作',async t=>{
  const modal=deferred(),p=await page(t,{},()=>modal.promise)
  await p.vm.openAgreement({...original});p.vm.agreementDetail.value.renderedBody='';await p.vm.confirmAgreement('CONFIRM')
  p.vm.agreementDetail.value={...original,status:'RAW_UNKNOWN'};assert.equal(p.vm.agreementStatusText.value,'状态待学校核实');await p.vm.confirmAgreement('CONFIRM')
  p.vm.agreementDetail.value={...original};p.vm.my.value.historyMode=true;await p.vm.confirmAgreement('CONFIRM')
  p.vm.my.value.historyMode=false;const sending=p.vm.confirmAgreement('CONFIRM');assert.equal(p.vm.agreementBusy.value,true)
  await p.vm.confirmAgreement('CONFIRM');p.logout();modal.resolve(true);await sending
  assert.equal(p.calls.filter(x=>x[0]==='confirm').length,0)
})

test('正文与同单回读迟到时不能污染新批次，回读失败明确部分完成',async t=>{
  const pending=deferred(),p=await page(t,{agreement:()=>pending.promise})
  const opening=p.vm.openAgreement(original);p.vm.resetSourceStates();p.vm.my.value={...ctx,batchId:'other'}
  pending.resolve(original);await opening;assert.equal(p.vm.agreementDetail.value,null)
  const q=await page(t);q.vm.my.value={...ctx,eligibilityReview:{status:'QUALIFIED'},agreementStatus:'PENDING_STUDENT'}
  q.vm.agreements.value=[original];await q.vm.openAgreement(original);q.api.agreement=async()=>{throw Error('network')}
  await q.vm.confirmAgreement('CONFIRM');assert.equal(q.vm.agreementReceipt.value.readback,false)
  assert.equal(q.vm.agreementDetail.value.status,'PENDING_ENTERPRISE');assert.ok(q.vm.agreementError.value.includes('办理已提交'))
  assert.equal(q.vm.currentAction.value.title,'继续完成上岗准备')
  await q.vm.confirmAgreement('CONFIRM');assert.equal(q.calls.filter(x=>x[0]==='confirm').length,1)
})

test('打印件使用已打开版本并实际下载文件，错误归属响应不生成下载',async t=>{
  const p=await page(t);await p.vm.openAgreement(original);await p.vm.printAgreement()
  assert.deepEqual(p.calls.find(x=>x[0]==='pdf').slice(1),[original.id,{batchId:ctx.batchId,internshipId:ctx.recordId,expectedVersion:3}])
  assert.equal(p.downloads.length,1);assert.equal(p.downloads[0].download,'当前协议打印件.pdf');assert.ok(p.downloads[0].clicked&&p.downloads[0].removed)
  assert.equal(p.blobs[0].type,'application/pdf');assert.ok((await p.blobs[0].text()).startsWith('%PDF-'))
  p.timers[0]();assert.deepEqual(p.calls.at(-1),['revoke','blob:synthetic'])
  p.api.agreementPdf=async()=>({agreementId:'other'});await p.vm.printAgreement()
  assert.equal(p.downloads.length,1);assert.equal(p.vm.agreementConflict.value,true)
})

test('两份协议乱序或卸载后的响应不替换当前正文',async t=>{
  const a=deferred(),b=deferred(),other={...original,id:'9007199254741004'}
  const p=await page(t,{agreement:id=>id===original.id?a.promise:b.promise})
  const first=p.vm.openAgreement(original),second=p.vm.openAgreement(other)
  a.resolve(original);await first;assert.equal(p.vm.agreementReading.value,true);assert.equal(p.vm.agreementDetail.value,null)
  p.lifecycle.unmount();b.resolve(other);await second;assert.equal(p.vm.agreementDetail.value,null)
})

test('首屏待办按本记录最新回读结果更新，查看旧协议不能替换当前待办',async t=>{
  const p=await page(t);p.vm.my.value={...ctx,eligibilityReview:{status:'QUALIFIED'},agreementStatus:'NONE'}
  const old={...original,id:'9007199254741000',status:'REJECTED'}
  const read=p.api.agreement;p.api.agreement=async id=>id===old.id?old:read(id)
  p.vm.agreements.value=[{...original,batchId:'other'},original,old]
  await p.vm.openAgreement(old)
  assert.equal(p.vm.currentAction.value.title,'确认三方协议')
  p.vm.my.value.agreementStatus='PENDING_STUDENT'
  await p.vm.openAgreement(original);await p.vm.confirmAgreement('CONFIRM')
  assert.equal(p.vm.currentAction.value.title,'继续完成上岗准备')
  p.vm.activeAgreement.value=old;p.vm.agreementDetail.value=old
  assert.equal(p.vm.currentAction.value.title,'继续完成上岗准备')
  p.vm.sourceStates.agreement.status='error'
  assert.notEqual(p.vm.currentAction.value.title,'确认三方协议')
})
