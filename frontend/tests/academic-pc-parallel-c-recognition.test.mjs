import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {gradeError} from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
const source=readFileSync(new URL('../src/modules/academicAffairs/views/AaGradeRecognitionView.vue',import.meta.url),'utf8')
const record={recognitionId:'101',studentId:'201',studentNo:'NO1',studentName:'甲',sourceCourseName:'原课程',sourceScore:80,sourceCredit:0,sourceOrigin:'原学校',targetCourseId:'1000000000000063602',targetCourseName:'目标课程',attachmentFileIds:[],reason:'认定依据',status:'SUBMITTED'}
const list=(...rows)=>({code:0,data:{list:rows,total:rows.length}})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
const flush=()=>new Promise(resolve=>setTimeout(resolve,0))
const successfulReceipt=result=>async(commandKey,operation)=>({code:0,data:{commandKey,operation,state:'SUCCESS',result}})
function mount(rawApi={},files={}){
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/ {2}components: \{[\s\S]*?\n {2}\},/,'').replace('export default','return')
 let commandNo=0
 const references=new Map()
 const identityRef=()=> 'test-identity'
 const findRef=()=>({ok:true,entry:rawApi.__recoveryEntry||null})
 const createRef=args=>{const commandKey=`00000000-0000-4000-8000-${String(++commandNo).padStart(12,'0')}`;const entry={...args,commandKey};references.set(commandKey,entry);return {ok:true,entry,existing:false}}
 const updateRef=(commandKey,_identity,patch)=>{const entry={...(references.get(commandKey)||{}),...patch};references.set(commandKey,entry);return {ok:true,entry}}
 const removeRef=commandKey=>{references.delete(commandKey);return {ok:true}}
 const api={...rawApi}
 api.getRecognition=async id=>{
   const response=rawApi.getRecognition?await rawApi.getRecognition(id):rawApi.listRecognitions?await rawApi.listRecognitions({recognitionId:String(id),page:1,pageSize:20}):{code:404}
   if(response?.code!==0)return response
   const data=response.data?.recognitionId?response.data:response.data?.list?.find(row=>String(row.recognitionId)===String(id))
   if(!data)return {code:404}
   return {code:0,data:{...data}}
 }
 api.getGradeCommandReceipt=rawApi.getGradeCommandReceipt||((commandKey,operation)=>({code:0,data:{commandKey,operation,state:'UNRESOLVED',result:null}}))
 const component=new Function('api','currentUserFromToken','matchPermission','fileSdk','gradeError','createGradeCommandReference','findGradeCommandReference','gradeCommandIdentityRef','removeGradeCommandReference','updateGradeCommandReference',script)(api,()=>({tenantId:'1',userId:'2',currentRoleCode:'ACADEMIC_ADMIN'}),(patterns)=>patterns.includes('*'),{metadata:async()=>({readyForBusiness:true}),...files},gradeError,createRef,findRef,identityRef,removeRef,updateRef)
 const vm={...component.data(),ctx:{currentRole:{},dataScope:{},permissionPatterns:['*']},identityKey:'I1',$route:{path:'/recognition',fullPath:'/recognition',query:{}}};for(const [key,value] of Object.entries(component.methods))vm[key]=value.bind(vm);for(const [key,value] of Object.entries(component.computed))if(key!=='identityKey')Object.defineProperty(vm,key,{get:()=>value.call(vm)})
 vm.$router={replace:async route=>{const query=route.query||{};vm.$route={path:route.path||vm.$route.path,query,fullPath:`${route.path||vm.$route.path}?${new URLSearchParams(query)}`};component.watch.routeKey.call(vm)}}
 return vm
}
const setupForm=vm=>{vm.openCreate();Object.assign(vm.form,record,{attachments:[]})}
test('认定完整模板可编译',()=>{const {descriptor,errors}=parse(source);assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'AaGradeRecognitionView.vue',id:'recognition'}).errors,[])})
test('代录拒绝空分/不及格，0学分和长目标ID原样传递',async()=>{
 let writes=0,payload;const vm=mount({submitRecognition:async body=>{writes++;payload=body;return {code:0,data:{recognitionId:record.recognitionId}}},getGradeCommandReceipt:successfulReceipt(record),listRecognitions:async()=>list(record)});setupForm(vm);vm.form.sourceScore='';await vm.submitCreate();assert.equal(writes,0);vm.form.sourceScore=59;await vm.submitCreate();assert.equal(writes,0);vm.form.sourceScore=80;await vm.submitCreate();assert.equal(payload.sourceCredit,0);assert.equal(payload.targetCourseId,record.targetCourseId);assert.equal(vm.receipt.verified,true)
})
test('教师无管理权限不能代录或审核',async()=>{let writes=0;const vm=mount({submitRecognition:async()=>{writes++},reviewRecognition:async()=>{writes++}});vm.ctx.permissionPatterns=[];vm.openCreate();assert.equal(vm.createVisible,false);await vm.review(record,'APPROVE','',1,'SUBMITTED');assert.equal(writes,0)})
test('审核前原分变化不写，不能只核对SUBMITTED状态',async()=>{
 let writes=0;const vm=mount({listRecognitions:async()=>list({...record,sourceScore:81}),reviewRecognition:async()=>{writes++}});await vm.review(record,'APPROVE','',1,'SUBMITTED');assert.equal(writes,0);assert.match(vm.error,/已变化/)
})
test('审核前材料绑定变化不写旧证据',async()=>{let writes=0;const vm=mount({listRecognitions:async()=>list({...record,attachmentFileIds:['new']}),reviewRecognition:async()=>{writes++}});await vm.review(record,'APPROVE','',1,'SUBMITTED');assert.equal(writes,0)})
test('POST成功但GET仍待审核，保留未决且不重放',async()=>{
 let writes=0;const vm=mount({listRecognitions:async()=>list(record),getGradeCommandReceipt:successfulReceipt({...record,status:'APPROVED'}),reviewRecognition:async()=>{writes++;return {code:0,data:{status:'APPROVED'}}}});await vm.review(record,'APPROVE','',1,'SUBMITTED');await vm.review(record,'APPROVE','',1,'SUBMITTED');await vm.verifyCommand();assert.equal(writes,1);assert.equal(vm.receipt.verified,false);assert.ok(vm.pending)
})
test('APPROVE回读REJECTED不能当作通过，未知状态也未决',async()=>{
 for(const status of ['REJECTED','UNKNOWN']){let written=false;const vm=mount({listRecognitions:async()=>list({...record,status:written?status:'SUBMITTED'}),getGradeCommandReceipt:successfulReceipt({...record,status:'APPROVED'}),reviewRecognition:async()=>{written=true;return {code:0}}});await vm.review(record,'APPROVE','',1,'SUBMITTED');assert.equal(vm.receipt.verified,false)}
})
test('驳回正式原因匹配才确认，409保留父组件原因',async()=>{
 const vm=mount({listRecognitions:async()=>list(record),reviewRecognition:async()=>({code:409001})});vm.openReject(record);vm.rejectReason='请补充原课程依据';await vm.submitReject();assert.equal(vm.rejectReason,'请补充原课程依据');assert.equal(vm.rejectVisible,true);assert.equal(vm.pending,null)
})
test('写后GET403清所有原课程分数、意见、材料和回执',async()=>{
 let reads=0;const vm=mount({listRecognitions:async()=>++reads===1?list(record):{code:403001},getGradeCommandReceipt:successfulReceipt({...record,status:'APPROVED'}),reviewRecognition:async()=>({code:0})});vm.rows=[record];vm.active=record;vm.evidenceFiles=[{fileId:'private'}];vm.form.reason='私有';await vm.review(record,'APPROVE','',1,'SUBMITTED');assert.deepEqual(vm.rows,[]);assert.equal(vm.active,null);assert.deepEqual(vm.evidenceFiles,[]);assert.equal(vm.form.reason,'');assert.equal(vm.pending,null)
})
test('换学生取消旧上传，迟到回调不加入新学生材料',async()=>{
 const q=deferred();let reads=0,cancel=0;const vm=mount({}, {upload:()=>({promise:q.promise,cancel(){cancel++}}),metadata:async()=>{reads++;return {}}});setupForm(vm);const pending=vm.onPickFile({target:{files:[{name:'证明',size:10}],value:'x'}});vm.form.studentId='S2';vm.onStudentChange('S2',[{raw:{studentNo:'NO2'}}]);q.resolve({fileId:'old'});await pending;assert.equal(reads,0);assert.equal(cancel,1);assert.deepEqual(vm.form.attachments,[]);assert.equal(vm.form.studentNo,'NO2');assert.equal(vm.uploading,false)
})
test('换目标课程使旧文件状态核对失效并解除忙碌',async()=>{
 const q=deferred();const vm=mount({}, {metadata:()=>q.promise});setupForm(vm);vm.form.attachments=[{fileId:'F1'}];const pending=vm.refreshFile(vm.form.attachments[0]);vm.form.targetCourseId='T2';vm.onTargetChange('T2',[{raw:{courseName:'新目标'}}]);q.resolve({fileId:'F1',readyForBusiness:true});await pending;assert.deepEqual(vm.form.attachments,[]);assert.equal(vm.uploading,false)
})
test('切申请作废旧审核确认，不能审批旧学生',async()=>{let writes=0;const vm=mount({getRecognition:async id=>({code:0,data:{...record,recognitionId:String(id)}}),listRecognitions:async()=>list(record),reviewRecognition:async()=>{writes++}});vm.approve(record);vm.selectRecord({...record,recognitionId:'102'});await vm.onConfirm();assert.equal(writes,0);assert.equal(vm.pendingAction,null)})
test('代录超时不以同名记录认成功，保留原表单',async()=>{
 let writes=0;const vm=mount({submitRecognition:async()=>{writes++;throw new Error('timeout')},listRecognitions:async()=>list(record)});setupForm(vm);await vm.submitCreate();await vm.submitCreate();await vm.verifyCommand();assert.equal(writes,1);assert.equal(vm.receipt.verified,false);assert.equal(vm.form.sourceScore,80)
})


test('真实403002与NO_DATA_SCOPE并列识别，材料拒绝清旧学生证据',async()=>{const vm=mount({}, {metadata:async()=>{throw {code:403002,bizCode:'NO_DATA_SCOPE'}}});vm.active={...record,attachmentFileIds:['private']};vm.rows=[vm.active];await vm.loadEvidence();assert.equal(vm.active,null);assert.deepEqual(vm.rows,[]);assert.match(vm.error,/无权/)})
test('认定503后GET他人同方向结果不能确认为本次审核',async()=>{let written=false,writes=0;const other={...record,status:'APPROVED',reviewedBy:'OTHER',reviewedAt:'2026-09-08T12:00:00'};const vm=mount({listRecognitions:async()=>list(written?other:record),reviewRecognition:async()=>{writes++;written=true;return {code:503001}}});await vm.review(record,'APPROVE','',1,'SUBMITTED');await vm.verifyCommand();assert.equal(writes,1);assert.equal(vm.receipt.verified,false);assert.equal(vm.writeBlocked,true)})
test('审核只按原ID精确回读，不扫描相似申请或其它分页',async()=>{let written=false;const exactReads=[],listReads=[],approved={...record,status:'APPROVED',reviewedBy:'A',reviewedAt:'now'};const vm=mount({getRecognition:async id=>{exactReads.push(String(id));return {code:0,data:written?approved:record}},listRecognitions:async query=>{listReads.push(query);return list({...approved,recognitionId:'999'})},getGradeCommandReceipt:successfulReceipt(approved),reviewRecognition:async()=>{written=true;return {code:0,data:approved}}});vm.pagination.page=2;await vm.review(record,'APPROVE','',2,'SUBMITTED');assert.deepEqual(exactReads,[record.recognitionId,record.recognitionId,record.recognitionId]);assert.equal(listReads.length,1);assert.equal(listReads[0].page,2);assert.equal(vm.receipt.verified,true)})
test('完整审核回执但GET永远另一ID：不虚报verified，且模板提供保持锁定的返回入口',async()=>{let written=false;const approved={...record,status:'APPROVED'};const vm=mount({getRecognition:async()=>({code:0,data:written?{...approved,recognitionId:'999'}:record}),listRecognitions:async()=>list(record),getGradeCommandReceipt:successfulReceipt(approved),reviewRecognition:async()=>{written=true;return {code:0,data:approved}}});vm.rows=[record];vm.active=record;await vm.review(record,'APPROVE','',1,'SUBMITTED');assert.equal(vm.receipt.verified,false);assert.equal(vm.receipt.acknowledged,true);assert.equal(vm.writeBlocked,true);assert.match(source,/data-testid="return-queue-with-lock"/);await vm.returnToQueueWithLock();assert.equal(vm.$route.query.recognitionId,undefined);assert.equal(vm.active,null);assert.equal(vm.rows.length,1);assert.match(vm.error,/保持|仍待核实/);assert.ok(vm.pending);assert.equal(vm.writeBlocked,true)})
test('代录正式内容未匹配时，返回队列关闭抽屉并保留可见队列与恢复锁',async()=>{const changed={...record,sourceScore:81};const vm=mount({submitRecognition:async()=>({code:0,data:{recognitionId:'101'}}),getGradeCommandReceipt:successfulReceipt(record),listRecognitions:async()=>list(changed)});setupForm(vm);vm.rows=[record];await vm.submitCreate();assert.equal(vm.receipt.verified,false);assert.equal(vm.receipt.acknowledged,true);assert.equal(vm.createVisible,true);await vm.returnToQueueWithLock();assert.equal(vm.createVisible,false);assert.equal(vm.active,null);assert.equal(vm.rows.length,1);assert.equal(vm.pending.queueOnly,true);assert.equal(vm.writeBlocked,true);assert.match(source,/error && !pending\?\.ack/);assert.match(source,/AppInlineAlert v-if="error" type="warning"/)})
test('已知回执核对结束后返回队列，保留原命令引用和异常说明',async()=>{const commandKey='00000000-0000-4000-8000-000000000099';const vm=mount({getGradeCommandReceipt:successfulReceipt({...record,status:'APPROVED'}),getRecognition:async()=>({code:0,data:{...record,recognitionId:'999'}}),listRecognitions:async()=>list(record)});const c={...vm.capture(),id:'101',kind:'review',commandKey,operation:'RECOGNITION_REVIEW',ack:null,row:record,action:'APPROVE',reason:'',page:1,status:'SUBMITTED',description:'原申请'};vm.pending=c;await vm.verifyCommand();assert.ok(c.ack);assert.equal(vm.checking,false);const previousError=vm.error;await vm.returnToQueueWithLock();assert.equal(vm.$route.query.recognitionId,undefined);assert.equal(vm.pending.commandKey,commandKey);assert.equal(vm.pending.queueOnly,true);assert.equal(vm.writeBlocked,true);assert.match(vm.error,/仍待核实/);assert.notEqual(vm.error,previousError)})
test('刷新后恢复代录回执，允许正式记录已进入合法后续审核状态',async()=>{const commandKey='00000000-0000-4000-8000-000000000101',formal={...record,status:'APPROVED'};const vm=mount({__recoveryEntry:{commandKey,operation:'RECOGNITION_SUBMIT',objectId:'101',page:1,status:'SUBMITTED'},getGradeCommandReceipt:successfulReceipt(record),getRecognition:async()=>({code:0,data:formal}),listRecognitions:async()=>list(formal)});vm.restoreWithRecovery();await flush();assert.equal(vm.receipt.verified,true);assert.equal(vm.receipt.commandStatus,'SUBMITTED');assert.equal(vm.receipt.status,'APPROVED');assert.equal(vm.pending,null)})
test('刷新后恢复通过回执，按回执内容与原ID正式记录双确认',async()=>{const commandKey='00000000-0000-4000-8000-000000000102',approved={...record,status:'APPROVED'};const vm=mount({__recoveryEntry:{commandKey,operation:'RECOGNITION_REVIEW',objectId:'101',page:1,status:'SUBMITTED'},getGradeCommandReceipt:successfulReceipt(approved),getRecognition:async()=>({code:0,data:approved}),listRecognitions:async()=>list(approved)});vm.restoreWithRecovery();await flush();assert.equal(vm.receipt.verified,true);assert.equal(vm.receipt.commandStatus,'APPROVED');assert.equal(vm.pending,null)})
test('刷新后恢复驳回回执，正式原因必须与持久结果一致',async()=>{const commandKey='00000000-0000-4000-8000-000000000103',rejected={...record,status:'REJECTED',reviewReason:'材料与原课程不一致'};const vm=mount({__recoveryEntry:{commandKey,operation:'RECOGNITION_REVIEW',objectId:'101',page:1,status:'SUBMITTED'},getGradeCommandReceipt:successfulReceipt(rejected),getRecognition:async()=>({code:0,data:rejected}),listRecognitions:async()=>list(rejected)});vm.restoreWithRecovery();await flush();assert.equal(vm.receipt.verified,true);assert.equal(vm.receipt.commandStatus,'REJECTED');assert.equal(vm.pending,null)})
test('恢复回执的命令或对象不匹配时保持锁定且不读成成功',async()=>{const commandKey='00000000-0000-4000-8000-000000000104';let exactReads=0;const vm=mount({__recoveryEntry:{commandKey,operation:'RECOGNITION_REVIEW',objectId:'101',page:1,status:'SUBMITTED'},getGradeCommandReceipt:async()=>({code:0,data:{commandKey,operation:'RECOGNITION_SUBMIT',state:'SUCCESS',result:{...record,status:'APPROVED'}}}),getRecognition:async()=>{exactReads++;return {code:0,data:{...record,status:'APPROVED'}}},listRecognitions:async()=>list(record)});vm.restoreWithRecovery();await flush();assert.equal(exactReads,0);assert.equal(vm.receipt.verified,false);assert.ok(vm.pending);assert.equal(vm.writeBlocked,true)})
