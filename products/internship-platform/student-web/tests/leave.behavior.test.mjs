import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, reactive, ref, watch } from 'vue'
import { INTERNSHIP_TABS as tabs } from '../src/platform/internshipNavigation.js'
import { scanState, scanFilesReady, refreshScanFiles } from '../src/services/fileScanState.js'
const ctx={hasData:true,batchId:'9007199254741001',recordId:'9007199254741002',status:'ONBOARD'}
const row={id:'9007199254741003',batchId:ctx.batchId,internshipId:ctx.recordId,version:3,status:'REJECTED',leaveType:'PERSONAL',startDate:'2026-10-07',endDate:'2026-10-07',reason:'原请假事由',reviewComment:'请补充情况',evidenceFileId:''}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function page(t,overrides={}) {
  let generation=1;const scope=effectScope(),calls=[],lifecycle={},notices=[]
  const {document,fileSdk={},portalApi={},fetchFileBlob=async()=>null,...extra}=overrides
  const api={leaves:async()=>({items:[row]}),leaveDetail:async()=>({...row,submissionHistory:[]}),
    applyLeave:async body=>{calls.push(['create',body]);return {...row,status:'PENDING',version:0}},
    resubmitLeave:async(id,body)=>{calls.push(['resubmit',id,body]);return {...row,status:'PENDING',version:4}},
    withdrawLeave:async(id,body)=>{calls.push(['withdraw',id,body]);return {...row,status:'WITHDRAWN',version:4}},
    returnLeave:async(id,body)=>{calls.push(['return',id,body]);return {...row,status:'RETURNED',version:4}},...extra}
  const deps={tabs,computed,reactive,ref,watch,onMounted:fn=>{lifecycle.mount=fn},onBeforeUnmount:fn=>{lifecycle.unmount=fn},
    useUiStore:()=>({notify:v=>notices.push(v)}),useSessionStore:()=>({user:{tenantId:'11',userId:'18'}}),
    useRoute:()=>({query:{}}),useRouter:()=>({replace(){},push(){}}),currentSessionGeneration:()=>generation,
    portalApi,document,fileSdk,fetchFileBlob,scanState,scanFilesReady,refreshScanFiles,systemPrompt(){},systemConfirm(){},internshipCoreApi:api}
  const script=parse(fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const names=['my','tab','busy','sourceStates','leaveForm','leaves','leaveReceipt','leaveError','returnDraft','leaveCanSubmit','submitLeave','uploadLeaveEvidence','withdrawLeave','openReturnLeave','confirmReturnLeave','resetSourceStates','fetchTabSource','loadTab','doCheckin','attendance']
  const optional=['leaveBase','leaveConflict','leaveDetail','leaveFile','openLeave','editLeave','rereadLeave','continueLeaveAfterConflict','leaveVisibilityChanged','downloadLeaveEvidence','refreshLeaveEvidence']
  const vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {'+names.join(',')+','+optional.map(n=>`${n}:typeof ${n}==='undefined'?undefined:${n}`).join(',')+'}')(...Object.values(deps)))
  t.after(()=>{lifecycle.unmount?.();scope.stop()})
  vm.my.value={...ctx};vm.tab.value='leave';vm.sourceStates.leave.status='data';vm.leaves.value=[row]
  return {vm,calls,notices,logout:()=>generation++}
}
function fill(vm){Object.assign(vm.leaveForm,{leaveType:'PERSONAL',startDate:row.startDate,endDate:row.endDate,reason:'保留补正事由',evidenceFileId:''})}
test('原单补正读取本人详情，固定原版本，同编号重交',async t=>{
  const {vm,calls}=page(t);await vm.editLeave({...row,version:1});vm.leaves.value=[{...row,version:9}]
  vm.leaveForm.reason='保留补正事由';await vm.submitLeave()
  assert.equal(calls[0][0],'resubmit');assert.equal(calls[0][1],row.id);assert.equal(calls[0][2].expectedVersion,3)
  assert.equal(calls[0][2].reason,'保留补正事由');assert.equal(vm.leaveReceipt.value.version,4)
})
test('冲突保留输入和原版本，回读后必须明确采用当前原单',async t=>{
  let latest=row;const sent=[];const {vm}=page(t,{leaveDetail:async()=>latest,resubmitLeave:async(id,body)=>{sent.push(body);throw {bizCode:'DATA_CONFLICT',status:409}}})
  await vm.editLeave(row);vm.leaveForm.reason='保留的补正内容';await vm.submitLeave();latest={...row,version:7};await vm.rereadLeave();await vm.submitLeave()
  assert.equal(sent.length,1);assert.equal(vm.leaveBase.value.version,3);assert.equal(vm.leaveForm.reason,'保留的补正内容')
  vm.continueLeaveAfterConflict();await vm.submitLeave();assert.equal(sent[1].expectedVersion,7)
})
test('其他实习详情不能回填或打开原单编辑',async t=>{
  const {vm,calls}=page(t,{leaveDetail:async()=>({...row,internshipId:'other'})});await vm.editLeave(row)
  assert.equal(vm.leaveBase.value,null);assert.equal(vm.leaveForm.reason,'');assert.equal(calls.length,0)
})
test('切换范围清除请假草稿、证明及原单，历史实习禁止写入',async t=>{
  const {vm,calls}=page(t);fill(vm);vm.leaveForm.evidenceFileId='old-file';vm.resetSourceStates()
  assert.equal(vm.leaveForm.reason,'');assert.equal(vm.leaveForm.evidenceFileId,'')
  vm.my.value={...ctx,historyMode:true};vm.sourceStates.leave.status='data';fill(vm);await vm.submitLeave();assert.equal(calls.length,0)
})
test('重叠列表读取及旧错误不得覆盖当前列表或读取状态',async t=>{
  const a=deferred(),b=deferred();let n=0;const {vm}=page(t,{leaves:()=>n++?b.promise:a.promise})
  const old=vm.loadTab('leave',true),fresh=vm.loadTab('leave',true);b.resolve({items:[{...row,reason:'当前数据'}]});await fresh
  a.reject(new Error('旧读取失败'));await old;assert.equal(vm.leaves.value[0].reason,'当前数据');assert.equal(vm.sourceStates.leave.status,'data')
})
test('迟到上传不绑定旧证明，也不能解除新操作锁',async t=>{
  const wait=deferred(),{vm,logout}=page(t,{fileSdk:{upload:()=>wait.promise}})
  const pending=vm.uploadLeaveEvidence({target:{files:[{name:'合成.png'}]}});logout();vm.resetSourceStates();vm.my.value={...ctx,batchId:'new'};vm.busy.value=true
  wait.resolve({fileId:'old',readyForBusiness:true});await pending;assert.equal(vm.leaveForm.evidenceFileId,'');assert.equal(vm.busy.value,true)
})
test('待扫描证明阻止提交，不能凭文件编号办理',async t=>{
  const {vm,calls}=page(t,{fileSdk:{upload:async()=>({fileId:'pending',readyForBusiness:false,statusText:'等待扫描'})}});fill(vm)
  await vm.uploadLeaveEvidence({target:{files:[{name:'合成.png'}]}});await vm.submitLeave();assert.equal(calls.length,0);assert.equal(vm.leaveForm.evidenceFileId,'')
})
test('迟到办理回执不清新草稿、不产生旧回执、不解新锁',async t=>{
  const wait=deferred(),{vm,logout}=page(t,{applyLeave:()=>wait.promise});fill(vm);const pending=vm.submitLeave()
  logout();vm.resetSourceStates();vm.my.value={...ctx,batchId:'other'};fill(vm);vm.busy.value=true;wait.resolve({...row,status:'PENDING',version:0});await pending
  assert.equal(vm.leaveReceipt.value,null);assert.equal(vm.leaveForm.reason,'保留补正事由');assert.equal(vm.busy.value,true)
})
test('原单提交成功后回读失败仍保留真实回执并阻止重复提交',async t=>{
  const {vm,calls}=page(t,{leaves:async()=>{throw new Error('读取失败')}});await vm.editLeave(row);await vm.submitLeave();await vm.submitLeave()
  assert.equal(vm.leaveReceipt.value.id,row.id);assert.equal(vm.sourceStates.leave.status,'error');assert.equal(calls.length,1)
})
test('列表回读使先前慢详情失效，不能将新状态覆盖回旧版本',async t=>{
  const wait=deferred(),{vm}=page(t,{leaveDetail:()=>wait.promise,leaves:async()=>({items:[{...row,status:'WITHDRAWN',version:4}]})})
  const pending=vm.openLeave(row);await vm.loadTab('leave',true);wait.resolve({...row,status:'PENDING'});await pending
  assert.equal(vm.leaves.value[0].status,'WITHDRAWN');assert.equal(vm.leaveDetail.value,null)
})
test('切批次后迟到证明下载不得触发保存',async t=>{
  const wait=deferred(),document={hidden:false,createElement(){throw new Error('不能创建旧下载链接')}}
  const {vm,logout}=page(t,{document,fetchFileBlob:()=>wait.promise});const pending=vm.downloadLeaveEvidence('123')
  logout();vm.resetSourceStates();wait.resolve({});await pending;assert.equal(vm.leaveError.value,'')
})
test('安全检查回读就绪后才绑定证明并发送申请',async t=>{
  const {vm,calls}=page(t,{fileSdk:{upload:async()=>({fileId:'123',status:'AVAILABLE',scanStatus:'PENDING',readyForBusiness:false}),metadata:async()=>({fileId:'123',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true})}})
  fill(vm);await vm.uploadLeaveEvidence({target:{files:[{name:'合成.png'}]}});assert.equal(vm.leaveCanSubmit.value,false)
  await vm.refreshLeaveEvidence();assert.equal(vm.leaveForm.evidenceFileId,'123');await vm.submitLeave();assert.equal(calls[0][1].fileId,'123')
})
test('安全检查回读返回其他证明时保留待处理材料并拒绝提交',async t=>{
  const {vm,calls}=page(t,{fileSdk:{upload:async()=>({fileId:'123',status:'AVAILABLE',scanStatus:'PENDING',readyForBusiness:false}),metadata:async()=>({fileId:'other',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true})}})
  fill(vm);await vm.uploadLeaveEvidence({target:{files:[{name:'合成.png'}]}});await vm.refreshLeaveEvidence();await vm.submitLeave()
  assert.equal(vm.leaveFile.value.fileId,'123');assert.equal(vm.leaveForm.evidenceFileId,'');assert.equal(vm.leaveForm.reason,'保留补正事由');assert.equal(calls.length,0)
})
test('只有日期和证明的草稿也不能被原单编辑覆盖',async t=>{
  let reads=0;const {vm}=page(t,{leaveDetail:async()=>{reads++;return row}});vm.leaveForm.startDate=row.startDate;vm.leaveForm.evidenceFileId='123'
  await vm.editLeave(row);assert.equal(reads,0);assert.equal(vm.leaveForm.evidenceFileId,'123');assert.equal(vm.leaveForm.startDate,row.startDate)
})
test('账号变化后的迟到详情不得显示或回填',async t=>{
  const wait=deferred(),{vm,logout}=page(t,{leaveDetail:()=>wait.promise});const pending=vm.editLeave(row);logout();wait.resolve(row);await pending
  assert.equal(vm.leaveDetail.value,null);assert.equal(vm.leaveBase.value,null);assert.equal(vm.leaveForm.reason,'')
})
test('补正、撤回和销假后已展开的原单均回读完整新版本',async t=>{
  for (const action of ['resubmit','withdraw','return']) {
    let latest={...row,status:action==='return'?'APPROVED':action==='withdraw'?'PENDING':'REJECTED'}
    const update=async()=>latest={...latest,version:4,status:action==='return'?'RETURNED':action==='withdraw'?'WITHDRAWN':'PENDING',submissionHistory:[{version:3}]}
    const {vm}=page(t,{leaveDetail:async()=>latest,leaves:async()=>({items:[latest]}),resubmitLeave:update,withdrawLeave:update,returnLeave:update})
    await vm.openLeave(latest)
    if(action==='resubmit'){await vm.editLeave(latest);await vm.submitLeave()}
    else if(action==='withdraw')await vm.withdrawLeave(latest)
    else{vm.openReturnLeave(latest);vm.returnDraft.note='合成返岗说明';await vm.confirmReturnLeave()}
    assert.equal(vm.leaveDetail.value.version,4,action);assert.equal(vm.leaveDetail.value.status,latest.status,action)
    assert.deepEqual(vm.leaveDetail.value.submissionHistory,[{version:3}],action);assert.equal(vm.busy.value,false)
  }
})
test('销假成功后的详情读取失败清除旧详情并保留真实回执',async t=>{
  let returned=false;const latest={...row,status:'APPROVED'}
  const {vm}=page(t,{leaveDetail:async()=>{if(returned)throw Error('读取失败');return latest},leaves:async()=>({items:[{...latest,status:'RETURNED',version:4}]}),returnLeave:async()=>{returned=true;return {...latest,status:'RETURNED',version:4}}})
  await vm.openLeave(latest);vm.openReturnLeave(latest);vm.returnDraft.note='合成返岗说明';await vm.confirmReturnLeave()
  assert.equal(vm.leaveReceipt.value.version,4);assert.equal(vm.leaveDetail.value,null);assert.equal(vm.busy.value,false);assert.match(vm.leaveError.value,/详情读取失败/)
})
test('销假成功后的列表读取失败也不能保留旧原单详情',async t=>{
  const latest={...row,status:'APPROVED'}, {vm}=page(t,{leaveDetail:async()=>latest,leaves:async()=>{throw Error('列表读取失败')}})
  await vm.openLeave(latest);vm.openReturnLeave(latest);vm.returnDraft.note='合成返岗说明';await vm.confirmReturnLeave()
  assert.equal(vm.leaveReceipt.value.version,4);assert.equal(vm.leaveDetail.value,null);assert.equal(vm.sourceStates.leave.status,'error');assert.equal(vm.busy.value,false)
})
test('返岗后电脑打卡使用正式本人接口和所选批次，回读同一实习',async t=>{
  const requests=[], reads=[]
  const script=fs.readFileSync(new URL('../src/services/portalApi.js',import.meta.url),'utf8').replace(/^import .*$/m,'').replace('export const portalApi','const portalApi').replace('export default portalApi','return portalApi')
  const portal=new Function('request',script)(async(path,options)=>{requests.push({path,options});return {id:'1',result:'NO_LOCATION'}})
  portal.internshipMy=async batch=>{reads.push(batch);return {...ctx,todayCheckin:{done:true}}}
  const {vm,notices}=page(t,{portalApi:portal,attendance:async received=>{assert.deepEqual(received,{batchId:ctx.batchId,internshipId:ctx.recordId});return {counts:{CHECKIN:1}}}})
  await vm.doCheckin()
  assert.equal(requests[0].path,'/mobile/internship/checkin?batchId='+ctx.batchId)
  assert.equal(requests[0].options.body.internshipId,ctx.recordId);assert.deepEqual(reads,[ctx.batchId])
  assert.equal(vm.attendance.value.counts.CHECKIN,1);assert.equal(vm.my.value.todayCheckin.done,true);assert.deepEqual(notices,['打卡已记录'])
})
test('账号变化后旧打卡回执不能回读或解开新操作锁',async t=>{
  const wait=deferred();let reads=0;const {vm,logout,notices}=page(t,{portalApi:{internshipCheckin:()=>wait.promise,internshipMy:async()=>{reads++;return ctx}}})
  const pending=vm.doCheckin();logout();vm.resetSourceStates();vm.busy.value=true;wait.resolve({id:'1'});await pending
  assert.equal(reads,0);assert.equal(vm.busy.value,true);assert.deepEqual(notices,[])
})
