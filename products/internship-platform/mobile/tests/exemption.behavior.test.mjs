import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source=fs.readFileSync(new URL('../src/pages/student-internship/exemption/index.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*/gm,'').replace('export default','return')
const row={id:'900719925474099301',version:3,status:'REJECTED',applicationType:'EXEMPTION',exemptionType:'FURTHER_STUDY',exemptionDestination:'合成升学学校',exemptionReason:'合成录取后申请免实习',evidenceFileId:'901'}
function page(overrides={}){
 let generation=1
 const calls=[],api={studentInternshipApplicationSave:async body=>{calls.push(body);return {...row,...body,version:4,status:'DRAFT'}},studentInternshipApplicationSubmit:async(id,body)=>{calls.push({id,...body});return {...row,version:5,status:'PENDING_REVIEW'}},studentInternshipApplications:async()=>[row],studentApi:{getInternship:async()=>({batchId:'10',recordId:'11',statusText:'PREPARING'})},fileSdk:{metadata:async fileId=>({fileId,readyForBusiness:true,fileName:'证明.pdf'})},chooseSingleFile:async()=>({name:'新证明.pdf'}),uploadBusinessFile:async()=>({fileId:'902',readyForBusiness:false}),studentInternshipApplicationWithdraw:async()=>{},toast:()=>{},currentSessionGeneration:()=>generation,formatDateTime:value=>value||'—',...overrides}
 const component=new Function(...Object.keys(api),source)(...Object.values(api)),vm={...component.data()}
 for(const [name,fn] of Object.entries(component.methods))vm[name]=fn.bind(vm)
 for(const [name,fn] of Object.entries(component.computed))Object.defineProperty(vm,name,{get:()=>fn.call(vm)})
 vm.context={batchId:'10',internshipId:'11'};vm.recordStatus='PREPARING';vm.pageState='ready'
 return {vm,calls,hide:()=>component.onHide.call(vm),show:()=>component.onShow.call(vm),logout:()=>generation++}
}
test('手机免实习扫描未就绪不保存，刷新后沿退回原单提交',async()=>{
 let ready=false
 const p=page({fileSdk:{metadata:async fileId=>({fileId,readyForBusiness:ready})}});p.vm.fill(row)
 await p.vm.submit();assert.equal(p.calls.length,0);assert.equal(p.vm.form.exemptionReason,row.exemptionReason)
 ready=true;await p.vm.submit();assert.equal(p.calls[0].id,row.id);assert.equal(p.calls[0].expectedVersion,3);assert.equal(p.calls[1].expectedVersion,4)
})
test('手机保存成功后提交失败保留新草稿编号，冲突核对不覆盖旧输入',async()=>{
 const p=page({studentInternshipApplicationSubmit:async()=>{throw {status:409,message:'原单已变化'}},studentInternshipApplications:async()=>[{...row,version:9,exemptionReason:'另一端写入的原因说明'}]});p.vm.fill(row)
 p.vm.form.exemptionReason='本端补正输入仍须保留';await p.vm.submit();assert.equal(p.vm.application.version,4);assert.equal(p.vm.conflict,true)
 await p.vm.reread();assert.equal(p.vm.latest.version,9);assert.equal(p.vm.application.version,4);assert.equal(p.vm.form.exemptionReason,'本端补正输入仍须保留')
 await p.vm.adoptLatest();assert.equal(p.vm.application.version,9);assert.equal(p.vm.form.exemptionReason,'另一端写入的原因说明')
})
test('手机错材料编号及过期上传不能覆盖原佐证',async()=>{
 const p=page({fileSdk:{metadata:async()=>({fileId:'other',readyForBusiness:true})}});p.vm.fill(row);await p.vm.submit();assert.equal(p.calls.length,0);assert.match(p.vm.errorMessage,/编号不一致/)
 let resolve;const late=page({uploadBusinessFile:()=>new Promise(r=>resolve=r)});late.vm.fill(row)
 const upload=late.vm.chooseEvidence();await new Promise(r=>setImmediate(r));late.hide();resolve({fileId:'late',readyForBusiness:true});await upload;assert.equal(late.vm.form.evidenceFileId,row.evidenceFileId)
})
test('手机离页保存迟到不得续交，换会话加载迟到不得回填',async()=>{
 let resolve;const p=page({studentInternshipApplicationSave:()=>new Promise(r=>resolve=r)});p.vm.fill(row)
 const submit=p.vm.submit();await new Promise(r=>setImmediate(r));p.hide();resolve({...row,version:4});await submit;assert.equal(p.calls.length,0);assert.equal(p.vm.application.version,3)
 let dashboard;const late=page({studentApi:{getInternship:()=>new Promise(r=>dashboard=r)}});const load=late.vm.load();late.logout();dashboard({batchId:'other',recordId:'other',status:'PREPARING'});await load;assert.equal(late.vm.context.batchId,'10')
})
test('手机待审核、历史及已上岗免实习不能再次提交',async()=>{
 for(const scenario of [{status:'PENDING_REVIEW'},{status:'APPROVED'},{historyMode:true},{recordStatus:'ONBOARD'},{destinationType:'EXEMPTED'}]){
  const p=page();p.vm.fill({...row,status:scenario.status||row.status});Object.assign(p.vm,Object.fromEntries(Object.entries(scenario).filter(([key])=>key!=='status')));await p.vm.submit();assert.equal(p.calls.length,0)
 }
})

test('手机真实适配后的实习状态可继续退回原单，重新打开不丢字段',async()=>{
 const p=page();await p.vm.load();assert.equal(p.vm.recordStatus,'PREPARING');assert.equal(p.vm.editable,true);assert.equal(p.vm.evidenceReady,true);assert.equal(p.vm.form.exemptionDestination,row.exemptionDestination)
})

test('手机初始加载离开后重进恢复原批次，不误入空上下文补正',async()=>{
 const p=page();p.vm.context={};p.vm.pageState='loading';p.hide();p.show();await new Promise(r=>setImmediate(r));assert.equal(p.vm.context.batchId,'10');assert.equal(p.vm.pageState,'ready');assert.equal(p.vm.application.id,row.id)
})
