import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeFileReadiness, refreshFileReadiness } from '../src/services/fileReadiness.mjs'
const ctx={hasBatch:true,batchId:'9007199254741001',recordId:'9007199254741002',statusText:'ONBOARD'}
const row={id:'9007199254741003',batchId:ctx.batchId,internshipId:ctx.recordId,version:3,status:'REJECTED',leaveType:'PERSONAL',startDate:'2026-10-07',endDate:'2026-10-07',reason:'原请假事由',reviewComment:'请补充情况',evidenceFileId:''}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function page(extra={}) {
  let generation=1;const calls=[],notices=[],modals=[]
  const deps={currentSessionGeneration:()=>generation,normalizeError:()=>({text:'操作未完成，请核对后重试'}),normalizeFileReadiness,refreshFileReadiness,
    toast:text=>notices.push(text),uni:{stopPullDownRefresh(){},showModal:options=>modals.push(options)},
    studentApi:{getInternship:async()=>({...ctx})},studentInternshipLeaves:async()=>({items:[row]}),studentInternshipLeaveDetail:async()=>({...row,submissionHistory:[]}),
    studentInternshipLeaveApply:async body=>{calls.push(['create',body]);return {...row,version:0,status:'PENDING'}},
    studentInternshipLeaveResubmit:async(id,body)=>{calls.push(['resubmit',id,body]);return {...row,version:4,status:'PENDING'}},
    studentInternshipLeaveWithdraw:async(id,body)=>{calls.push(['withdraw',id,body]);return {...row,version:4,status:'WITHDRAWN'}},
    studentInternshipLeaveReturn:async(id,body)=>{calls.push(['return',id,body]);return {...row,version:4,status:'RETURNED'}},
    chooseSingleFile:async()=>null,uploadBusinessFile:async()=>null,fileSdk:{},...extra}
  const script=fs.readFileSync(new URL('../src/pages/student-internship/leave/index.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm=component.data()
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:fn.bind(vm)})
  vm.context={...ctx,internshipId:ctx.recordId};vm.pageState='ready';vm.list=[row]
  return {vm,component,calls,notices,modals,logout:()=>generation++}
}
function fill(vm){Object.assign(vm.form,{leaveType:'PERSONAL',startDate:row.startDate,endDate:row.endDate,reason:'保留补正事由',fileId:''});vm.formVisible=true}

test('销假列表按真实导师确认事实区分待核实、已办结及未知',()=>{
  const {vm,calls}=page()
  assert.equal(vm.leaveStage({...row,status:'RETURNED',returnAcknowledged:false}).label,'待导师核实返岗')
  assert.equal(vm.leaveStage({...row,status:'RETURNED',returnAcknowledged:true}).label,'销假办结')
  assert.equal(vm.leaveStage({...row,status:'RETURNED'}).label,'返岗确认待核对')
  assert.match(vm.leaveStage({...row,status:'APPROVED'}).next,/返岗后/);assert.equal(calls.length,0)
})

test('独立退回补正状态从原单原版本重交',async()=>{
  const returned={...row,status:'NEEDS_REVISION'}
  const {vm,calls}=page({studentInternshipLeaveDetail:async()=>returned})
  await vm.edit(returned);vm.form.reason='已按要求补充具体事由';await vm.submit()
  assert.equal(calls[0][0],'resubmit');assert.equal(calls[0][1],row.id);assert.equal(calls[0][2].expectedVersion,row.version)
  assert.equal(vm.statusLabel('NEEDS_REVISION'),'已退回，请补正');assert.equal(vm.statusLabel('REJECTED'),'已驳回')
})
test('详情提供原版本，补正同编号并保留教师意见分离',async()=>{
  const {vm,calls}=page();await vm.edit({...row,version:1});vm.list=[{...row,version:9}];vm.form.reason='保留补正事由';await vm.submit()
  assert.equal(calls[0][0],'resubmit');assert.equal(calls[0][1],row.id);assert.equal(calls[0][2].expectedVersion,3);assert.equal(calls[0][2].reason,'保留补正事由');assert.equal(vm.receipt.version,4)
})
test('冲突回读不自动覆盖草稿与版本，明确核对才继续',async()=>{
  let latest=row;const sent=[];const {vm}=page({studentInternshipLeaveDetail:async()=>latest,studentInternshipLeaveResubmit:async(id,body)=>{sent.push(body);throw {bizCode:'DATA_CONFLICT'}}})
  await vm.edit(row);vm.form.reason='保留补正文字';await vm.submit();latest={...row,version:7};await vm.reread();await vm.submit()
  assert.equal(sent.length,1);assert.equal(vm.editing.version,3);assert.equal(vm.form.reason,'保留补正文字');vm.continueAfterConflict();await vm.submit();assert.equal(sent[1].expectedVersion,7)
})
test('无权详情不能回填，历史模式不得发送任何写入',async()=>{
  const {vm,calls}=page({studentInternshipLeaveDetail:async()=>({...row,batchId:'other'})});await vm.edit(row);assert.equal(vm.editing,null)
  vm.context.historyMode=true;fill(vm);await vm.submit();vm.withdraw({...row,status:'PENDING'});vm.openReturn({...row,status:'APPROVED'});assert.equal(calls.length,0);assert.equal(vm.returnDraft.id,'')
})
test('旧列表失败不能覆盖返回页面后的成功读取',async()=>{
  const old=deferred();let n=0;const {vm,component}=page({studentInternshipLeaves:()=>n++?Promise.resolve({items:[{...row,reason:'新列表'}]}):old.promise})
  const pending=vm.loadList();await Promise.resolve();component.onHide.call(vm);vm.hidden=false;await vm.loadList();old.reject(new Error('旧读取失败'));await pending
  assert.equal(vm.list[0].reason,'新列表');assert.equal(vm.pageState,'ready')
})
test('文件选择期间离开页面，旧选择不能启动上传',async()=>{
  const wait=deferred();let uploads=0;const {vm,component}=page({chooseSingleFile:()=>wait.promise,uploadBusinessFile:async()=>{uploads++;return {fileId:'old'}}});fill(vm)
  const pending=vm.chooseEvidence();component.onHide.call(vm);wait.resolve({name:'合成.png'});await pending;assert.equal(uploads,0)
})
test('旧上传回执不能绑定新表单或解新上传锁',async()=>{
  const wait=deferred(),{vm,component}=page({chooseSingleFile:async()=>({name:'合成.png'}),uploadBusinessFile:()=>wait.promise});fill(vm)
  const pending=vm.chooseEvidence();await Promise.resolve();component.onHide.call(vm);vm.hidden=false;vm.form={...vm.form,fileId:'new',reason:'新草稿'};vm.uploading=true
  wait.resolve({fileId:'old',readyForBusiness:true});await pending;assert.equal(vm.form.fileId,'new');assert.equal(vm.uploading,true)
})
test('撤回确认框冻结原版本并拒绝其他上下文旧确认',async()=>{
  const {vm,calls,modals,component}=page();vm.withdraw({...row,status:'PENDING'});vm.list=[{...row,version:9}];await modals[0].success({confirm:true});assert.equal(calls[0][2].expectedVersion,3)
  vm.withdraw({...row,status:'PENDING'});component.onHide.call(vm);await modals[1].success({confirm:true});assert.equal(calls.length,1)
})
test('证明等待扫描时禁止提交，不能用编号冒充安全就绪',async()=>{
  const {vm,calls}=page({chooseSingleFile:async()=>({name:'合成.png'}),uploadBusinessFile:async()=>({fileId:'pending',readyForBusiness:false})});fill(vm);await vm.chooseEvidence();await vm.submit();assert.equal(calls.length,0);assert.equal(vm.form.fileId,'')
})
test('迟到销假回执不得清新说明、产生旧回执或解新锁',async()=>{
  const wait=deferred(),{vm,component}=page({studentInternshipLeaveReturn:()=>wait.promise});vm.openReturn({...row,status:'APPROVED'});vm.returnDraft.note='已返岗';const pending=vm.submitReturn()
  component.onHide.call(vm);vm.hidden=false;vm.returnDraft={id:'new',note:'新说明',version:8};vm.submitting=true;wait.resolve({...row,status:'RETURNED'});await pending
  assert.equal(vm.returnDraft.note,'新说明');assert.equal(vm.receipt,null);assert.equal(vm.submitting,true)
})
test('原单重交成功但回读失败仍显示真实回执，禁止再次重交',async()=>{
  const {vm,calls}=page({studentInternshipLeaves:async()=>{throw new Error('回读失败')}});await vm.edit(row);await vm.submit();await vm.submit();assert.equal(vm.receipt.id,row.id);assert.equal(vm.pageState,'error');assert.equal(calls.length,1)
})
test('新列表使旧详情失效，不会把已撤回状态覆回待审批',async()=>{
  const wait=deferred(),{vm}=page({studentInternshipLeaveDetail:()=>wait.promise,studentInternshipLeaves:async()=>({items:[{...row,status:'WITHDRAWN',version:4}]})})
  const pending=vm.openDetail(row);await vm.loadList();wait.resolve({...row,status:'PENDING'});await pending
  assert.equal(vm.list[0].status,'WITHDRAWN');assert.equal(vm.detail,null)
})
test('当前原单已进入待审批时，核对按钮不能采用新版重交',async()=>{
  let latest=row;const calls=[];const {vm}=page({studentInternshipLeaveDetail:async()=>latest,studentInternshipLeaveResubmit:async(id,body)=>{calls.push(body);throw {bizCode:'DATA_CONFLICT'}}})
  await vm.edit(row);await vm.submit();latest={...row,status:'PENDING',version:7};await vm.reread();vm.continueAfterConflict();await vm.submit()
  assert.equal(calls.length,1);assert.equal(vm.editing.version,3);assert.equal(vm.conflict,true)
})
test('真实安全转换与回读完成后才允许绑定证明提交',async()=>{
  const {vm,calls}=page({chooseSingleFile:async()=>({name:'合成.png'}),uploadBusinessFile:async()=>({fileId:'123',status:'AVAILABLE',scanStatus:'PENDING',readyForBusiness:false}),fileSdk:{metadata:async()=>({fileId:'123',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true})}})
  fill(vm);await vm.chooseEvidence();await vm.submit();assert.equal(calls.length,0);await vm.refreshEvidence();assert.equal(vm.form.fileId,'123')
  await vm.submit();assert.equal(calls[0][1].fileId,'123')
})
test('安全回读错误保留证明和正文，不能继续提交',async()=>{
  const {vm,calls}=page({chooseSingleFile:async()=>({name:'合成.png'}),uploadBusinessFile:async()=>({fileId:'123',status:'AVAILABLE',scanStatus:'PENDING',readyForBusiness:false}),fileSdk:{metadata:async()=>{throw new Error('读取失败')}}})
  fill(vm);await vm.chooseEvidence();await vm.refreshEvidence();await vm.submit();assert.equal(vm.pendingEvidence.fileId,'123');assert.equal(vm.form.fileId,'');assert.equal(vm.form.reason,'保留补正事由');assert.equal(calls.length,0)
})
test('只有日期和证明的草稿也不能被其他原单编辑清除',async()=>{
  let reads=0;const {vm}=page({studentInternshipLeaveDetail:async()=>{reads++;return row}});vm.form.startDate=row.startDate;vm.form.fileId='123';vm.formVisible=false
  await vm.edit(row);assert.equal(reads,0);assert.equal(vm.form.startDate,row.startDate);assert.equal(vm.form.fileId,'123')
})
test('账号变化后的迟到原单详情不回填',async()=>{
  const wait=deferred(),{vm,logout}=page({studentInternshipLeaveDetail:()=>wait.promise});const pending=vm.edit(row);logout();wait.resolve(row);await pending
  assert.equal(vm.detail,null);assert.equal(vm.editing,null);assert.equal(vm.form.reason,'')
})
test('补正、撤回和销假后已展开的原单均回读完整新版本',async()=>{
  for(const action of ['resubmit','withdraw','return']){
    let latest={...row,status:action==='return'?'APPROVED':action==='withdraw'?'PENDING':'REJECTED'}
    const update=async()=>latest={...latest,version:4,status:action==='return'?'RETURNED':action==='withdraw'?'WITHDRAWN':'PENDING',submissionHistory:[{version:3}]}
    const {vm,modals}=page({studentInternshipLeaveDetail:async()=>latest,studentInternshipLeaves:async()=>({items:[latest]}),studentInternshipLeaveResubmit:update,studentInternshipLeaveWithdraw:update,studentInternshipLeaveReturn:update})
    await vm.openDetail(latest)
    if(action==='resubmit'){await vm.edit(latest);await vm.submit()}
    else if(action==='withdraw'){vm.withdraw(latest);await modals[0].success({confirm:true})}
    else{vm.openReturn(latest);vm.returnDraft.note='合成返岗说明';await vm.submitReturn()}
    assert.equal(vm.detail.version,4,action);assert.equal(vm.detail.status,latest.status,action)
    assert.deepEqual(vm.detail.submissionHistory,[{version:3}],action);assert.equal(vm.submitting,false)
  }
})
test('销假成功后的详情读取失败清除旧详情并保留真实回执',async()=>{
  let returned=false;const latest={...row,status:'APPROVED'}
  const {vm}=page({studentInternshipLeaveDetail:async()=>{if(returned)throw Error('读取失败');return latest},studentInternshipLeaves:async()=>({items:[{...latest,status:'RETURNED',version:4}]}),studentInternshipLeaveReturn:async()=>{returned=true;return {...latest,status:'RETURNED',version:4}}})
  await vm.openDetail(latest);vm.openReturn(latest);vm.returnDraft.note='合成返岗说明';await vm.submitReturn()
  assert.equal(vm.receipt.version,4);assert.equal(vm.detail,null);assert.equal(vm.submitting,false);assert.match(vm.formError,/详情读取失败/)
})
test('销假成功后的列表读取失败也不能保留旧原单详情',async()=>{
  const latest={...row,status:'APPROVED'}, {vm}=page({studentInternshipLeaveDetail:async()=>latest,studentInternshipLeaves:async()=>{throw Error('列表读取失败')}})
  await vm.openDetail(latest);vm.openReturn(latest);vm.returnDraft.note='合成返岗说明';await vm.submitReturn()
  assert.equal(vm.receipt.version,4);assert.equal(vm.detail,null);assert.equal(vm.pageState,'error');assert.equal(vm.submitting,false)
})
