import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {decisionVersion,nodePermission,sameDecision,sameDecisionOutcome,matchesDecisionResult} from '../src/modules/academicAffairs/views/parallel-c/status-change-review.js'
import {gradeError} from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
import {TYPE_LABEL,STATUS_LABEL,NODE_LABEL,CHANGE_FLOW_NODES,TYPE_PAGE_META,statusColor} from '../src/modules/academicAffairs/constants/status-change.js'
import {ACADEMIC_STUDENT_STATUS_LABELS} from '../src/modules/academicAffairs/config/academicStudentLabels.js'
const dir=new URL('../src/modules/academicAffairs/views/',import.meta.url)
const source=name=>readFileSync(new URL(name,dir),'utf8')
const names=['AaStatusChangeListView.vue','AaStatusChangeTypedListView.vue','AaStatusChangeEffectiveView.vue','AaStatusChangeApprovalView.vue','AaStatusChangeDetailView.vue','parallel-c/StatusChangeReview.vue']
const initial={changeId:'9007199254740993',studentId:'S1',realName:'甲',changeType:'SUSPEND',fromStatus:'REGISTERED',toStatus:'SUSPENDED',reason:'申请休学一年',status:'SUBMITTED',currentNode:'COUNSELOR_REVIEW',currentTaskId:'9007199254740994',version:1,decisionVersion:0,expectedStudentVersion:2,effectiveDate:'2099-09-01'}
const advanced={...initial,status:'IN_REVIEW',currentNode:'COLLEGE_REVIEW',currentTaskId:'9007199254740995',version:2,decisionVersion:1}
const ok=data=>({code:0,data})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function mount(name,api={},extra={}){
 const script=source(name).match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/components\s*:\s*\{[^}]*\},?/,'').replace('export default','return')
 const deps={api,academicAffairsApi:api,statusChangeConvenienceApi:{listMaterials:async()=>ok({items:[]})},currentUserFromToken:()=>({}),matchPermission:(patterns,permission)=>patterns.includes('*')||patterns.includes(permission),TYPE_LABEL,STATUS_LABEL,NODE_LABEL,CHANGE_FLOW_NODES,TYPE_PAGE_META,statusColor,ACADEMIC_STUDENT_STATUS_LABELS,gradeError,decisionVersion,nodePermission,sameDecision,sameDecisionOutcome,matchesDecisionResult,...extra}
 const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),events=[]
 const vm={...component.data(),ctx:{currentRole:{},dataScope:{},permissionPatterns:['*']},change:{...initial},identity:'I1',readerIdentity:'I1',$route:{params:{id:initial.changeId},meta:{changeType:'SUSPEND'}},$router:{push(){}},$emit:(...args)=>events.push(args)}
 for(const [key,value] of Object.entries(component.methods))vm[key]=value.bind(vm)
 for(const [key,value] of Object.entries(component.computed||{}))if(!['identity','readerIdentity'].includes(key))Object.defineProperty(vm,key,{get:()=>value.call(vm)})
 return {vm,events,component}
}
for(const name of names)test(`${name}模板编译`,()=>{const {descriptor,errors}=parse(source(name));assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:name,id:'status'}).errors,[])})
test('版本0有效，缺失/空/不安全整数不默认0；未知节点和草稿不给审核动作',()=>{
 assert.equal(decisionVersion(initial),0);for(const value of [null,undefined,'',false,1.5,Number.MAX_SAFE_INTEGER+1])assert.equal(decisionVersion({decisionVersion:value}),null)
 assert.equal(nodePermission({...initial,status:'DRAFT'}),'');assert.equal(nodePermission({...initial,currentNode:'UNKNOWN'}),'')
})
test('冻结原版本和长ID，POST后GET匹配正式结果才确认；重复点击只写一次',async()=>{
 let reads=0,writes=0,args;const gate=deferred();const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(++reads<=2?initial:advanced),reviewStatusChange:async(...values)=>{writes++;args=values;await gate.promise;return ok(advanced)}})
 await vm.ask('APPROVE');const task=vm.submit();await vm.submit();gate.resolve();await task
 assert.deepEqual(args,[initial.changeId,'APPROVE','',0]);assert.equal(writes,1);assert.equal(vm.receipt.verified,true);assert.equal(vm.pending,null)
})
test('缺少版本只读原申请，必须再次确认，不自动POST',async()=>{let writes=0;const {vm,events}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(initial),reviewStatusChange:async()=>{writes++}});vm.change.decisionVersion=null;await vm.ask('APPROVE');await vm.submit();assert.equal(writes,0);assert.equal(vm.command,null);assert.ok(events.some(e=>e[0]==='updated'))})
test('确认后版本/任务/原学籍或计划日期变化，不提交旧决定',async()=>{
 for(const changed of [{decisionVersion:1},{currentTaskId:'different'},{fromStatus:'WITHDRAWN'},{effectiveDate:'2099-10-01'}]){let writes=0;const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok({...initial,...changed}),reviewStatusChange:async()=>{writes++}});await vm.ask('APPROVE');await vm.submit();assert.equal(writes,0);assert.match(vm.error,/已变化/);assert.equal(vm.command,null)}
})
test('409保留父组件原因、取消旧确认；不以新版本自动重放',async()=>{
 let writes=0;const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(initial),reviewStatusChange:async()=>{writes++;return {code:409001}}});vm.reason='请补充诊断证明';await vm.ask('RETURN');await vm.submit();await vm.submit();assert.equal(writes,1);assert.equal(vm.reason,'请补充诊断证明');assert.equal(vm.confirmVisible,false);assert.equal(vm.pending,null)
})
test('HTTP成功但正式状态未变，保留未决；手动核对只GET',async()=>{
 let writes=0;const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(initial),reviewStatusChange:async()=>{writes++;return ok(advanced)}});await vm.ask('APPROVE');await vm.submit();await vm.verify();await vm.ask('APPROVE');await vm.submit();assert.equal(writes,1);assert.equal(vm.receipt.verified,false);assert.ok(vm.pending)
})
test('超时即使读到同方向结果也不冒认本人意见回执',async()=>{
 let reads=0,writes=0;const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(++reads<=2?initial:advanced),reviewStatusChange:async()=>{writes++;throw new Error('timeout')}});await vm.ask('APPROVE');await vm.submit();await vm.verify();assert.equal(writes,1);assert.equal(vm.receipt.verified,false);assert.match(vm.receipt.label,/审批中/)
})
test('终审待生效和已生效各按正式状态确认，未来日期不自行改成生效',async()=>{
 for(const status of ['APPROVED_PENDING_EFFECTIVE','EFFECTIVE']){const before={...initial,currentNode:'AA_OFFICE_FINAL'},after={...before,status,decisionVersion:1,version:2,currentTaskId:'',currentNode:status==='EFFECTIVE'?'AA_OFFICE_FINAL':''};let reads=0;const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(++reads<=2?before:after),reviewStatusChange:async()=>ok(after)});vm.change=before;await vm.ask('APPROVE');await vm.submit();assert.equal(vm.receipt.verified,true);if(status==='APPROVED_PENDING_EFFECTIVE')assert.match(vm.receipt.label,/当前学籍尚未改变/)}
})
test('立即生效终审允许服务端生成生效时间，ACK 与正式记录秒级取整差异仍按同一决定核对',async()=>{
 const before={...initial,currentNode:'AA_OFFICE_FINAL',effectiveDate:null}
 const ack={...before,status:'EFFECTIVE',decisionVersion:1,currentTaskId:'',effectiveDate:'2026-09-09T16:32:31Z'}
 const formal={...ack,effectiveDate:'2026-09-09T16:32:32Z'}
 let reads=0
 const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(++reads<=2?before:formal),reviewStatusChange:async()=>ok(ack)})
 vm.change=before;await vm.ask('APPROVE');await vm.submit()
 assert.equal(vm.receipt.verified,true);assert.equal(vm.pending,null)
})
test('通过不能用退回或额外流转版本确认；退回保留原节点仍是正式合法结果',()=>{
 assert.equal(matchesDecisionResult(initial,'APPROVE',{...advanced,status:'RETURNED'}),false);assert.equal(matchesDecisionResult(initial,'APPROVE',{...advanced,decisionVersion:2}),false);assert.equal(matchesDecisionResult(initial,'RETURN',{...initial,status:'RETURNED',decisionVersion:1,currentTaskId:''}),true)
})
test('写后403清意见、原回执并通知父页清私有对象',async()=>{
 let reads=0;const {vm,events}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>++reads===1?ok(initial):{code:403002,bizCode:'NO_DATA_SCOPE'},reviewStatusChange:async()=>ok(advanced)});vm.reason='私有原因';await vm.ask('APPROVE');await vm.submit();assert.equal(vm.reason,'');assert.equal(vm.receipt,null);assert.equal(vm.pending,null);assert.ok(events.some(e=>e[0]==='denied'))
})
test('身份切换后旧POST和finally不污染新身份对象或解除新忙碌',async()=>{
 const gate=deferred();const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(initial),reviewStatusChange:()=>gate.promise});await vm.ask('APPROVE');const pending=vm.submit();await Promise.resolve();vm.identity='I2';vm.invalidate();vm.reason='新身份原因';vm.saving=true;gate.resolve(ok(advanced));await pending;assert.equal(vm.reason,'新身份原因');assert.equal(vm.saving,true);assert.equal(vm.receipt,null)
})
test('没有当前节点权限不能进入确认或写入',async()=>{const {vm}=mount('parallel-c/StatusChangeReview.vue');vm.ctx.permissionPatterns=['academicAffairs.statusChange.officeReview'];await vm.ask('APPROVE');assert.equal(vm.command,null)})
test('所有审批动作在系统内确认前重新读取同一申请和正式材料；无材料也明确回执',async()=>{
 const calls=[];const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(initial)},{statusChangeConvenienceApi:{listMaterials:async id=>{calls.push(id);return ok({items:[]})}}})
 await vm.ask('APPROVE')
 assert.deepEqual(calls,[initial.changeId]);assert.equal(vm.confirmVisible,true);assert.match(vm.evidenceText,/未绑定材料/);assert.match(vm.materialReceipt(vm.command.evidence),/未绑定材料/)
})
test('正式材料读取失败不打开确认框，也不会提交审批命令',async()=>{
 let writes=0;const {vm}=mount('parallel-c/StatusChangeReview.vue',{getStatusChange:async()=>ok(initial),reviewStatusChange:async()=>{writes++}},{statusChangeConvenienceApi:{listMaterials:async()=>({code:503001,message:'timeout'})}})
 await vm.ask('APPROVE');await vm.submit()
 assert.equal(vm.confirmVisible,false);assert.equal(vm.command,null);assert.equal(writes,0);assert.match(vm.error,/材料/)
})
for(const name of ['AaStatusChangeListView.vue','AaStatusChangeTypedListView.vue','AaStatusChangeEffectiveView.vue','AaStatusChangeApprovalView.vue'])test(`${name}旧读取/异常/收尾不污染新筛选；保留服务器total`,async()=>{
 const old=deferred();let count=0;const {vm}=mount(name,{getStatusChanges:async()=>++count===1?old.promise:ok({list:[advanced],total:61})});const pending=vm.load();await vm.load();old.reject({code:403002,bizCode:'NO_DATA_SCOPE'});await pending;assert.equal(vm.rows[0].currentNode,'COLLEGE_REVIEW');assert.equal(vm.total??vm.pagination.total,61);assert.equal(vm.error,'');assert.equal(vm.loading,false)
})
test('生效队列按正式状态服务端分页，不把待生效混作已生效',async()=>{let query;const {vm}=mount('AaStatusChangeEffectiveView.vue',{getStatusChanges:async q=>{query=q;return ok({list:[],total:0})}});vm.phase='APPROVED_PENDING_EFFECTIVE';await vm.load();assert.equal(query.status,'APPROVED_PENDING_EFFECTIVE');assert.equal(query.pageSize,20)})
test('详情核心读取不自动拉材料；路由切换丢弃旧材料与迟到下载',async()=>{
 const gate=deferred();let lists=0,urls=0;const {vm}=mount('AaStatusChangeDetailView.vue',{getStatusChange:async()=>ok(initial)},{statusChangeConvenienceApi:{listMaterials:async()=>{lists++;return ok({items:[]})}},fileSdk:{metadata:()=>gate.promise,authorizedUrl:async()=>{urls++}}});await vm.load();assert.equal(lists,0);vm.materials=[{fileId:'F1'}];const pending=vm.openFile(vm.materials[0],'preview');vm.$route.params.id='new';vm.clear();gate.resolve({allowedActions:['preview']});await pending;assert.equal(urls,0);assert.deepEqual(vm.materials,[])
})
test('详情403清旧姓名/材料，打印前读取失败不打开窗口',async()=>{
 let opens=0;const {vm}=mount('AaStatusChangeDetailView.vue',{getStatusChange:async()=>({code:403002,bizCode:'NO_DATA_SCOPE'})},{window:{open(){opens++}}});vm.change={...initial};vm.materials=[{fileId:'private'}];await vm.print();assert.equal(opens,0);assert.equal(vm.change,null);assert.deepEqual(vm.materials,[])
})
