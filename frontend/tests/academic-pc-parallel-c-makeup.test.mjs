import * as makeupEvidence from '../src/modules/academicAffairs/views/parallel-c/makeup-evidence.js'
import test from 'node:test'
import { setImmediate } from 'node:timers'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { gradeError } from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
const source=readFileSync(new URL('../src/modules/academicAffairs/views/AaMakeupConsoleView.vue',import.meta.url),'utf8')
const list=(...rows)=>({code:0,data:{list:rows,total:rows.length}})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function testRuntime(){const entries=new Map();return {crypto:globalThis.crypto,sessionStorage:{getItem:key=>entries.get(key)??null,setItem:(key,value)=>entries.set(key,String(value)),removeItem:key=>entries.delete(key)}}}
function mount(api={},runtime=testRuntime()){
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/ {2}components: \{[\s\S]*?\n {2}\},/,'').replace('export default','return')
 const options=new Function('api','academicStatusLabel','currentUserFromToken','gradeError','matchPermission',...Object.keys(makeupEvidence),'globalThis',script)(api,s=>s,()=>({}),gradeError,(patterns,key)=>patterns.includes('*')||patterns.includes(key),...Object.values(makeupEvidence),runtime)
 const vm={...options.data(),ctx:{currentRole:{},dataScope:{},permissionPatterns:['*']},identityKey:'I1',$route:{query:{},path:'/makeup'},$router:{replace(){}}}
 for(const [key,value] of Object.entries(options.methods))vm[key]=value.bind(vm)
 for(const [key,value] of Object.entries(options.computed))if(key!=='identityKey')Object.defineProperty(vm,key,{get:()=>value.call(vm)})
 return vm
}
const retakeFacts={applicationVersion:0,sourceGradeState:'RESOLVED',sourceEvidenceHash:'a'.repeat(64),allowedActions:['ENROLL','APPROVE','REJECT']}
const exemptionFacts={exemptionVersion:0,evidenceState:'VALID',evidenceFiles:[],resultGradeState:'NOT_GENERATED',allowedActions:['APPROVE','RETURN','REJECT']}
const batch={batchId:'101',batchName:'补考批次',status:'PUBLISHED'}
const record={makeupId:'M1',acadStudentId:'S1',originGradeId:'G1',studentName:'学生甲',courseName:'课程甲',status:'PENDING_EXAM',finalScore:null}
test('补考控制台完整模板可编译',()=>{const {descriptor,errors}=parse(source);assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'AaMakeupConsoleView.vue',id:'c-makeup'}).errors,[])})
for(const kind of ['makeup','clearance']){
 test(`${kind}空白分不变0，真实0分可保存并回读`,async()=>{
  let writes=0,saved=false,payload;const vm=mount({score:async(_id,n)=>{writes++;payload=n;saved=true;return {code:0}},batchRecords:async()=>list({...record,...(saved?{status:'SCORED',finalScore:0}:{})}),clearanceRecords:async()=>list({...record,...(saved?{status:'SCORED',finalScore:0}:{})}),listBatches:async()=>list(batch)})
  const prefix=kind==='makeup'?'mk':'cr';vm.tab=kind;vm[prefix+'Batch']={...batch};vm[prefix+'Rows']=[{...record}];vm[prefix+'Scores']={M1:''}
  await vm.submitScore(kind,record);assert.equal(writes,0);assert.match(vm.detailError,/空白/)
  vm[prefix+'Scores'].M1=0;await vm.submitScore(kind,record);assert.equal(writes,1);assert.equal(payload,0);assert.equal(vm[prefix+'Rows'][0].finalScore,0);assert.equal(vm.writeReceipt.verified,true)
 })
 test(`${kind}写后GET403清除对象、草稿和未决回执`,async()=>{
  let reads=0;const read=async()=>++reads===1?list(record):{code:403001};const vm=mount({score:async()=>({code:0}),batchRecords:read,clearanceRecords:read})
  const prefix=kind==='makeup'?'mk':'cr';vm.tab=kind;vm[prefix+'Batch']={...batch};vm[prefix+'Rows']=[record];vm[prefix+'Scores']={M1:70};vm.batchForm.batchName='私有批次'
  await vm.submitScore(kind,record);assert.equal(vm[prefix+'Batch'],null);assert.deepEqual(vm[prefix+'Rows'],[]);assert.deepEqual(vm[prefix+'Scores'],{});assert.equal(vm.batchForm.batchName,'');assert.ok(vm.pendingWrite?.recovered);assert.equal(vm.pendingWrite.reply,undefined);assert.equal(vm.writeReceipt.verified,false);assert.match(vm.error,/无权/)
 })
}
test('超时保留分数草稿和未决状态，重复点击与只读核对均不重放POST',async()=>{
 let writes=0;const vm=mount({score:async()=>{writes++;throw new Error('timeout')},batchRecords:async()=>list(record)})
 vm.mkBatch={...batch};vm.mkRows=[record];vm.mkScores.M1=75
 await vm.submitMakeupScore(record);await vm.submitMakeupScore(record);await vm.verifyWrite();assert.equal(writes,1);assert.equal(vm.mkScores.M1,75);assert.equal(vm.writeReceipt.verified,false);assert.ok(vm.pendingWrite)
})
test('写入前对象已评分则409保留草稿，不发POST',async()=>{
 let writes=0;const vm=mount({score:async()=>{writes++},batchRecords:async()=>list({...record,status:'SCORED',finalScore:80})})
 vm.mkBatch={...batch};vm.mkScores.M1=75;await vm.submitMakeupScore(record);assert.equal(writes,0);assert.equal(vm.mkScores.M1,75);assert.equal(vm.pendingWrite,null);assert.match(vm.error,/已变化/)
})
test('快速切换名单后旧response/catch/finally不污染新批次',async()=>{
 const a=deferred(),b=deferred();const vm=mount({batchRecords:id=>id==='A'?a.promise:b.promise})
 const old=vm.openMakeupRecords({...batch,batchId:'A'});const next=vm.openMakeupRecords({...batch,batchId:'B'})
 a.reject({code:403001});await old;assert.equal(vm.mkLoading,true);assert.equal(vm.mkBatch.batchId,'B');assert.equal(vm.error,'')
 b.resolve(list({...record,makeupId:'new'}));await next;assert.equal(vm.mkLoading,false);assert.equal(vm.mkRows[0].makeupId,'new')
})
test('身份变化使迟到写响应失效，不回读旧名单',async()=>{
 let reads=0;const q=deferred();const vm=mount({batchRecords:async()=>{reads++;return list(record)},score:()=>q.promise})
 vm.mkBatch={...batch};vm.mkScores.M1=75;const writing=vm.submitMakeupScore(record);await new Promise(r=>setImmediate(r));vm.identityKey='I2';vm.resetScope();q.resolve({code:0});await writing
 assert.equal(reads,1);assert.equal(vm.writeReceipt,null);assert.deepEqual(vm.mkRows,[])
})
test('重修必须选择真实教学任务，编班状态从GET确认',async()=>{
 let body,writes=0;const row={...retakeFacts,applyId:'501',status:'APPROVED',studentName:'甲',courseName:'乙'}
 const vm=mount({retakeApplies:async()=>list({...row,status:writes?'ENROLLED':'APPROVED',applicationVersion:writes?1:0,enrollment:writes?{teachingTaskId:'1000000000000063602',rosterCoverage:'FROZEN_AT_ENROLLMENT'}:null}),retakeEnroll:async(id,target)=>{writes++;body={id,target};return {code:0,data:{applyId:id,status:'ENROLLED',applicationVersion:1,teachingTaskRef:target}}}})
 vm.tab='retake';vm.rows=[row];vm.enrollRetake('501');await vm.submitRetake();assert.equal(writes,0)
 vm.teachingTaskRef='1000000000000063602';await vm.submitRetake();assert.deepEqual(body,{id:'501',target:'1000000000000063602'});assert.equal(vm.writeReceipt.status,'ENROLLED')
})
test('缓考合流响应成功但正式目标未变，保持待核实',async()=>{
 let writes=0;const row={deferId:'701',nextBatchRef:null,studentName:'甲',courseName:'乙'};const vm=mount({deferredPool:async()=>list(row),mergeDeferred:async()=>{writes++;return {code:0,data:{merged:true}}}})
 vm.tab='deferred';vm.openMerge(row);vm.mergeBatchId='101';await vm.submitMerge();await vm.submitMerge();assert.equal(writes,1);assert.equal(vm.writeReceipt.verified,false);assert.equal(vm.mergeBatchId,'101')
})
test('纳入确认冻结来源成绩与批次，只传正式身份字段',async()=>{
 let body,bid;const candidate={gradeId:'G1',acadStudentId:'S1',identityReady:true,studentName:'甲',courseName:'乙'}
 const vm=mount({listBatches:async()=>list({...batch,status:'ARRANGED'}),enroll:async(id,p)=>{bid=id;body=p;return {code:0}},batchRecords:async()=>list(record)})
 vm.mkBatch={...batch,status:'ARRANGED'};vm.enrollCandidate(candidate);candidate.gradeId='changed';await vm.onConfirm()
 assert.equal(bid,'101');assert.deepEqual(body,{gradeId:'G1',acadStudentId:'S1'});assert.equal(vm.writeReceipt.verified,true)
})
test('没有管理权限即使手动调用也不能录分或建批次',async()=>{
 let writes=0;const vm=mount({score:async()=>{writes++},createBatch:async()=>{writes++}});vm.ctx.permissionPatterns=[];vm.mkBatch=batch;vm.mkScores.M1=75;vm.batchForm.batchName='测试';await vm.submitScore('makeup',record);await vm.submitBatch();assert.equal(writes,0)
})
test('名单和候选只请求当前分页，旧候选返回不影响新页',async()=>{
 const a=deferred();const calls=[];const vm=mount({makeupPending:p=>{calls.push(p);return p.page===1?a.promise:Promise.resolve(list({gradeId:'new',identityReady:true}))}})
 vm.mkBatch={...batch,termCode:'2026-1'};const old=vm.loadMakeupCandidates(1);await vm.loadMakeupCandidates(2);a.resolve(list({gradeId:'old'}));await old
 assert.equal(vm.mkCandidates[0].gradeId,'new');assert.equal(vm.candidatePagination.page,2);assert.ok(calls.every(p=>p.pageSize===20&&p.termCode==='2026-1'))
})

test('超时后当前评分变化仍不能证明原命令成功，保留草稿与未决引用',async()=>{
 let saved=false;const vm=mount({score:async()=>{throw new Error('timeout')},batchRecords:async()=>list({...record,...(saved?{status:'SCORED',finalScore:75}:{})})})
 vm.mkBatch={...batch};vm.mkRows=[{...record}];vm.mkScores.M1=75;await vm.submitMakeupScore(record);saved=true;await vm.verifyWrite()
 assert.equal(vm.mkRows[0].finalScore,null);assert.equal(vm.mkScores.M1,75);assert.equal(vm.writeReceipt.verified,false);assert.ok(vm.pendingWrite)
})
test('审核409保留父组件原因草稿，不关闭确认或虚报成功',async()=>{
 const row={...retakeFacts,applyId:'501',status:'SUBMITTED',studentName:'甲',courseName:'乙'};const vm=mount({retakeApplies:async()=>list(row),retakeReview:async()=>({code:409001})})
 vm.tab='retake';vm.rows=[row];vm.reject('retakeReview','501');vm.reasonDialog.reason='请重新核对课程';await vm.onReasonConfirm()
 assert.equal(vm.reasonDialog.visible,true);assert.equal(vm.reasonDialog.reason,'请重新核对课程');assert.equal(vm.pendingWrite,null);assert.match(vm.error,/已变化/)
})

test('免修RETURN按正式SUBMITTED节点和原因确认，不能等待不存在的RETURNED',async()=>{
 let written=false;const reason='请补充对应课程证明',before={...exemptionFacts,exemptionId:'601',status:'COLLEGE_REVIEW',currentNode:'COLLEGE_REVIEW',studentName:'甲',courseName:'乙'}
 const vm=mount({exemptionApplies:async()=>list(written?{...before,status:'SUBMITTED',currentNode:'SUBMITTED',returnReason:reason,exemptionVersion:1}:before),exemptionReview:async()=>{written=true;return {code:0,data:{exemptionId:before.exemptionId,status:'SUBMITTED',currentNode:'SUBMITTED',returnReason:reason,exemptionVersion:1}}}})
 vm.tab='exemption';await vm.processReview('exemptionReview','601','RETURN',reason,before);assert.equal(vm.writeReceipt.verified,true);assert.equal(vm.writeReceipt.status,'SUBMITTED');assert.equal(vm.pendingWrite,null)
})
for(const after of [{status:'SUBMITTED',currentNode:'SUBMITTED'},{status:'UNKNOWN_NEXT',currentNode:'UNKNOWN_NEXT'},{status:'ACADEMIC_REVIEW',currentNode:'SUBMITTED'}])test(`免修APPROVE回读${after.status}/${after.currentNode}不能猜作成功`,async()=>{
 let written=false;const before={...exemptionFacts,exemptionId:'601',status:'COLLEGE_REVIEW',currentNode:'COLLEGE_REVIEW'}
 const vm=mount({exemptionApplies:async()=>list(written?{...before,...after}:before),exemptionReview:async()=>{written=true;return {code:0}}})
 vm.tab='exemption';await vm.processReview('exemptionReview','601','APPROVE','',before);assert.equal(vm.writeReceipt.verified,false);assert.ok(vm.pendingWrite)
})
test('免修APPROVE只接受对应正式下一状态与节点，终审节点应清空',()=>{
 const vm=mount();assert.equal(vm.reviewResultMatches('exemption','APPROVE','COLLEGE_REVIEW','',{status:'ACADEMIC_REVIEW',currentNode:'ACADEMIC_REVIEW'}),true)
 assert.equal(vm.reviewResultMatches('exemption','APPROVE','ACADEMIC_REVIEW','',{status:'APPROVED',currentNode:null}),false)
 assert.equal(vm.reviewResultMatches('exemption','APPROVE','ACADEMIC_REVIEW','',{status:'APPROVED',currentNode:null,resultGradeState:'RESOLVED',resultGrade:{gradeId:'901'}}),true)
 assert.equal(vm.reviewResultMatches('exemption','APPROVE','ACADEMIC_REVIEW','',{status:'APPROVED',currentNode:'ACADEMIC_REVIEW'}),false)
})
test('打开另一批次后取消旧纳入确认，不能POST旧批次',async()=>{
 let writes=0;const vm=mount({batchRecords:async()=>list(),enroll:async()=>{writes++}})
 vm.mkBatch={...batch,batchId:'A',status:'ARRANGED'};vm.enrollCandidate({gradeId:'G1',acadStudentId:'S1',identityReady:true});assert.equal(vm.confirmVisible,true)
 await vm.openMakeupRecords({...batch,batchId:'B'});await vm.onConfirm();assert.equal(writes,0);assert.equal(vm.pendingAction,null);assert.equal(vm.confirmVisible,false)
})

test('真实免修节点枚举有业务文案，未知节点仍待核对',()=>{
 const vm=mount();for(const node of ['SUBMITTED','TEACHER_REVIEW','COLLEGE_REVIEW','ACADEMIC_REVIEW'])assert.doesNotMatch(vm.nodeLabel(node),/待核对/)
 assert.match(vm.nodeLabel('UNKNOWN'),/待核对/)
})

test('免修退回的旧SUBMITTED回读原因不匹配时仍待核实',()=>{const vm=mount();assert.equal(vm.reviewResultMatches('exemption','RETURN','COLLEGE_REVIEW','本次补充课程证明',{status:'SUBMITTED',currentNode:'SUBMITTED',returnReason:'上次旧原因'}),false)})

test('办理后重读仍保持原申请选择，并展示退回业务语义',async()=>{
 const row={...exemptionFacts,exemptionId:'601',status:'SUBMITTED',currentNode:'SUBMITTED',returnReason:'请补充材料'};const vm=mount({exemptionApplies:async()=>list(row)})
 vm.tab='exemption';vm.activeApplication={exemptionId:'601'};await vm.reload();assert.equal(vm.activeApplication.exemptionId,'601');assert.match(vm.applicationStatus(vm.activeApplication),/已退回/)
})


test('重修审核超时后刷新以原命令回执恢复；后续编班不冒充原审核',async()=>{
 const runtime=testRuntime(),before={...retakeFacts,applyId:'501',status:'SUBMITTED'},reply={...before,status:'APPROVED',applicationVersion:1}
 let writes=0,settled=false,key=''
 const api={retakeApplies:async()=>list(settled?{...reply,status:'ENROLLED',applicationVersion:2}:before),
  retakeReview:async(_id,_action,_reason,_identity,commandKey)=>{writes++;key=commandKey;throw new Error('timeout')},
  commandReceipt:async(commandKey,operation)=>({code:0,data:{commandKey,operation,state:settled?'SUCCESS':'UNRESOLVED',result:settled?reply:null}})}
 const first=mount(api,runtime);first.tab='retake'
 await first.processReview('retakeReview','501','APPROVE','',before)
 assert.equal(writes,1);assert.ok(key);assert.equal(first.writeReceipt.verified,false)
 const restored=mount(api,runtime);restored.tab='retake';restored.restoreWrite();assert.ok(restored.pendingWrite?.recovered)
 settled=true;await restored.verifyWrite()
 assert.equal(writes,1);assert.equal(restored.writeReceipt.verified,true);assert.equal(restored.writeReceipt.status,'ENROLLED');assert.equal(restored.pendingWrite,null)
})

test('刷新后错误对象的原命令回执不能解锁重修操作',async()=>{
 const runtime=testRuntime(),before={...retakeFacts,applyId:'501',status:'SUBMITTED'}
 const first=mount({retakeApplies:async()=>list(before),retakeReview:async()=>{throw new Error('timeout')},commandReceipt:async(commandKey,operation)=>({code:0,data:{commandKey,operation,state:'UNRESOLVED',result:null}})},runtime)
 first.tab='retake';await first.processReview('retakeReview','501','APPROVE','',before)
 const restored=mount({commandReceipt:async(commandKey,operation)=>({code:0,data:{commandKey,operation,state:'SUCCESS',result:{...before,applyId:'502',status:'APPROVED',applicationVersion:1}}})},runtime)
 restored.tab='retake';restored.restoreWrite();await restored.verifyWrite()
 assert.ok(restored.pendingWrite);assert.equal(restored.writeReceipt.verified,false);assert.match(restored.error,/待核实/);assert.equal(restored.pendingWrite.acknowledged,false)
})
