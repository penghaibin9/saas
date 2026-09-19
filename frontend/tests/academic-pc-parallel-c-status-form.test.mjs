import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {TYPE_LABEL,TYPE_PATH_SEGMENT,STATUS_LABEL,NODE_LABEL,CHANGE_FLOW_NODES} from '../src/modules/academicAffairs/constants/status-change.js'
import {ACADEMIC_STUDENT_STATUS_LABELS} from '../src/modules/academicAffairs/config/academicStudentLabels.js'
import {gradeError} from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
import {rememberStatusChangeRecovery,getStatusChangeRecovery,clearStatusChangeRecovery,clearStatusChangeRecoveryForTests} from '../src/modules/academicAffairs/views/parallel-c/status-change-recovery.js'
const source=name=>readFileSync(new URL('../src/modules/academicAffairs/views/'+name,import.meta.url),'utf8')
const ok=data=>({code:0,data}),scopeDenied={code:403002,bizCode:'NO_DATA_SCOPE'}
const student={studentId:'9007199254740993',realName:'甲',studentStatus:'REGISTERED',studentVersion:0,collegeId:'CO1',majorId:'M1',classId:'CLASS1'}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function mount(name,api={},extra={}){
 const script=source(name).match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/components\s*:\s*\{[^}]*\},?/,'').replace('export default','return')
 const deps={academicAffairsApi:api,currentUserFromToken:()=>({}),matchPermission:patterns=>patterns.includes('*'),TYPE_LABEL,TYPE_PATH_SEGMENT,STATUS_LABEL,NODE_LABEL,CHANGE_FLOW_NODES,ACADEMIC_STUDENT_STATUS_LABELS,gradeError,hasGroupPhrases:()=>false,rememberStatusChangeRecovery,getStatusChangeRecovery,clearStatusChangeRecovery,...extra}
 const component=new Function(...Object.keys(deps),script)(...Object.values(deps))
 const vm={ctx:{currentRole:{},dataScope:{},permissionPatterns:['*']},$route:{query:{},params:{id:'C1'}},$router:{push(){}},$nextTick:async()=>{},identity:'I1'}
 Object.assign(vm,component.data.call(vm));for(const [key,value] of Object.entries(component.methods))vm[key]=value.bind(vm)
 for(const [key,value] of Object.entries(component.computed||{}))if(key!=='identity')Object.defineProperty(vm,key,{get:()=>value.call(vm)})
 return {vm,component}
}
const form=(api={},extra={})=>{clearStatusChangeRecoveryForTests();const {vm}=mount('AaStatusChangeFormView.vue',api,extra);vm.form.studentId='9007199254740993';vm.applyStudent(student);return vm}
const formal=(body)=>({changeId:'C1',studentId:body.studentId,idempotencyKey:body.idempotencyKey,changeType:body.changeType,reason:body.reason,status:'SUBMITTED',effectiveDate:body.effectiveDate,toMajorId:body.toMajorId,toClassId:body.toClassId})
for(const name of ['AaStatusChangeFormView.vue','AaStatusChangePrintView.vue'])test(name+'模板编译',()=>{const {descriptor,errors}=parse(source(name));assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:name,id:'form'}).errors,[])})
test('缺岗位权限或学籍事实不能提交，不安全数字ID不转换冒认',()=>{const vm=form();assert.equal(vm.canSubmit,true);vm.ctx.permissionPatterns=[];assert.equal(vm.canSubmit,false);vm.ctx.permissionPatterns=['*'];vm.factsReady=false;assert.equal(vm.canSubmit,false);vm.factsReady=true;vm.form.studentId=Number.MAX_SAFE_INTEGER+1;assert.equal(vm.canSubmit,false)})
test('双击确认只写一次，原学生ID及幂等键不变，正式申请与空材料准确回读',async()=>{
 let writes=0,body;const gate=deferred();const vm=form({getRosterDetail:async()=>ok(student),getStatusChange:async()=>ok(formal(body))},{statusChangeConvenienceApi:{submit:async payload=>{writes++;body=payload;await gate.promise;return ok({changeId:'C1'})},listMaterials:async()=>ok({items:[]})}});vm.askSubmit();const pending=vm.submit();await vm.submit();gate.resolve();await pending;assert.equal(writes,1);assert.equal(body.studentId,'9007199254740993');assert.equal(body.idempotencyKey,vm.idempotencyKey);assert.equal(vm.receipt.verified,true);assert.equal(vm.form.currentStatus,'REGISTERED')
})
test('原学籍组织在确认后变化，阻止旧申请且保留原因',async()=>{let writes=0;const vm=form({getRosterDetail:async()=>ok({...student,majorId:'M2'})},{statusChangeConvenienceApi:{submit:async()=>{writes++}}});vm.form.reason='保留申请理由';vm.askSubmit();await vm.submit();assert.equal(writes,0);assert.equal(vm.form.reason,'保留申请理由');assert.match(vm.error,/已变化/);assert.equal(vm.command,null)})
test('初始读取和提交前回包必须属于所选学生，不能用乙的展示事实提交甲',async()=>{
 let writes=0
 const wrong={...student,studentId:'9007199254740994',realName:'乙'}
 const initial=form({getRosterDetail:async()=>ok(wrong)},{statusChangeConvenienceApi:{submit:async()=>{writes++}}});initial.resetCurrentStudentFacts();await initial.loadStudentOrgInfo();assert.equal(initial.factsReady,false);assert.notEqual(initial.form.name,'乙')
 const before=form({getRosterDetail:async()=>ok(wrong)},{statusChangeConvenienceApi:{submit:async()=>{writes++}}});before.askSubmit();await before.submit();assert.equal(writes,0);assert.equal(before.form.name,'甲');assert.match(before.error,/不一致|核对/)
})
test('上传未安全不能写，确认后重新核对安全状态',async()=>{let writes=0;const vm=form({getRosterDetail:async()=>ok(student)},{fileSdk:{metadata:async()=>({readyForBusiness:false})},statusChangeConvenienceApi:{submit:async()=>{writes++}}});vm.materialFiles=[{fileId:'F1',readyForBusiness:true}];vm.askSubmit();await vm.submit();assert.equal(writes,0);assert.equal(vm.pending,null)})
test('写超时按精确幂等键找到正式申请，不按同名猜且不自动重放',async()=>{let body,writes=0;const vm=form({getRosterDetail:async()=>ok(student),getStatusChanges:async()=>ok({list:[{...formal(body),idempotencyKey:'other'},formal(body)],total:2})},{statusChangeConvenienceApi:{submit:async payload=>{writes++;body=payload;throw Error('timeout')},listMaterials:async()=>ok({items:[]})}});vm.askSubmit();await vm.submit();await vm.submit();assert.equal(writes,1);assert.equal(vm.receipt.verified,true)})

test('未知提交每次最多查三页，手动从下一页按幂等键恢复而不重放',async()=>{
 let body,writes=0;const pages=[]
 const vm=form({getRosterDetail:async()=>ok(student),getStatusChanges:async q=>{pages.push(q.page);assert.equal(q.studentId,'9007199254740993');return ok({list:q.page===4?[formal(body)]:Array.from({length:20},(_,i)=>({changeId:`other-${q.page}-${i}`,idempotencyKey:'other'})),total:61})}},{statusChangeConvenienceApi:{submit:async payload=>{body=payload;writes++;throw Error('timeout')},listMaterials:async()=>ok({items:[]})}})
 vm.askSubmit();await vm.submit();assert.deepEqual(pages,[1,2,3]);assert.equal(vm.receipt.verified,false);await vm.verify();assert.deepEqual(pages,[1,2,3,4]);assert.equal(writes,1);assert.equal(vm.receipt.verified,true)
})
test('写超时查不到幂等键或正式材料缺失保持未决',async()=>{
 for(const absent of [true,false]){let body;const vm=form({getRosterDetail:async()=>ok(student),getStatusChanges:async()=>ok({list:absent?[]:[formal(body)],total:1})},{fileSdk:{metadata:async()=>({readyForBusiness:true})},statusChangeConvenienceApi:{submit:async payload=>{body=payload;throw Error('timeout')},listMaterials:async()=>ok({items:[]})}});vm.materialFiles=[{fileId:'F1',readyForBusiness:true}];vm.askSubmit();await vm.submit();assert.equal(vm.receipt.verified,false);assert.ok(vm.pending);assert.equal(vm.canSubmit,false)}
})
test('正式材料GET复合403清姓名、意见、目标和旧回执',async()=>{let body;const vm=form({getRosterDetail:async()=>ok(student),getStatusChange:async()=>ok(formal(body))},{statusChangeConvenienceApi:{submit:async payload=>{body=payload;return ok({changeId:'C1'})},listMaterials:async()=>scopeDenied}});vm.form.reason='私有原因';vm.askSubmit();await vm.submit();assert.equal(vm.form.studentId,'');assert.equal(vm.form.name,'');assert.equal(vm.form.reason,'');assert.equal(vm.receipt,null)})
test('403清除界面隐私但保留受理引用，重新取得原学生权限后按正式ID恢复',async()=>{
 let body,materialReads=0
 const vm=form({getRosterDetail:async id=>ok({...student,studentId:id}),getStatusChange:async id=>ok({...formal(body),changeId:id})},{statusChangeConvenienceApi:{submit:async payload=>{body=payload;return ok({changeId:'C1'})},listMaterials:async()=>++materialReads===1?scopeDenied:ok({items:[]})}})
 vm.form.reason='只在活动表单保存';vm.askSubmit();await vm.submit();assert.equal(vm.form.studentId,'');assert.equal(vm.form.reason,'');assert.equal(vm.receipt,null)
 vm.form.studentId='9007199254740993';await vm.loadStudentOrgInfo();assert.equal(vm.pending.id,'C1');assert.equal(vm.idempotencyKey,body.idempotencyKey);assert.equal(vm.form.reason,'');await vm.verify();assert.equal(vm.receipt.verified,true);assert.equal(vm.receipt.id,'C1')
})
test('未知结果切换甲乙再回甲仍使用原幂等键且禁止第二次POST',async()=>{
 let writes=0,body
 const vm=form({getRosterDetail:async id=>ok({...student,studentId:id,realName:id.endsWith('4')?'乙':'甲'}),getStatusChanges:async()=>ok({list:[],total:0})},{statusChangeConvenienceApi:{submit:async payload=>{writes++;body=payload;throw Error('timeout')}}})
 vm.askSubmit();await vm.submit();const originalKey=body.idempotencyKey;assert.equal(writes,1);assert.ok(vm.pending)
 vm.invalidate();vm.form.studentId='9007199254740994';vm.resetCurrentStudentFacts();await vm.loadStudentOrgInfo();assert.equal(vm.pending,null)
 vm.invalidate();vm.form.studentId='9007199254740993';vm.resetCurrentStudentFacts();await vm.loadStudentOrgInfo();assert.equal(vm.pending.body.idempotencyKey,originalKey);await vm.submit();assert.equal(writes,1)
})
test('换学生取消上传，旧上传完成不读取或附加旧材料',async()=>{const gate=deferred();let reads=0,cancels=0;const vm=form({getRosterDetail:async()=>ok({...student,studentId:'S2',realName:'乙'})},{fileSdk:{upload:()=>({promise:gate.promise,cancel(){cancels++}}),metadata:async()=>{reads++}}});const pending=vm.pickMaterial({target:{files:[{name:'证明'}],value:'x'}});vm.form.studentId='S2';vm.onStudentChange('S2',[{label:'乙'}]);gate.resolve({fileId:'old'});await pending;assert.equal(cancels,1);assert.equal(reads,0);assert.deepEqual(vm.materialFiles,[]);assert.equal(vm.materialUploadBusy,false)})
test('旧学生成功和finally不污染新学生事实',async()=>{const gate=deferred();let calls=0;const vm=form({getRosterDetail:async()=>++calls===1?gate.promise:ok({...student,studentId:'S2',realName:'乙'})});const pending=vm.loadStudentOrgInfo();vm.form.studentId='S2';vm.invalidate();await vm.loadStudentOrgInfo();gate.resolve(ok(student));await pending;assert.equal(vm.form.name,'乙');assert.equal(vm.loadingStudent,false)})
test('同专业班级服务端20条逐页读取，排除当前班级且保留长ID',async()=>{const queries=[];const vm=form({listClasses:async q=>{queries.push(q);return ok({list:[{id:q.page===1?'CLASS1':'9007199254740993',className:'新班'}],total:30})}});vm.form.changeType='TRANSFER_CLASS';await vm.loadTargetClasses();await vm.loadTargetClasses(true);assert.equal(queries[0].pageSize,20);assert.equal(queries[1].page,2);assert.deepEqual(vm.targetClassOptions.map(r=>r.id),['9007199254740993'])})
test('打印上下文403不得保留学生或打印；旧路由读取不回灌',async()=>{let prints=0;const {vm}=mount('AaStatusChangePrintView.vue',{getContext:async()=>scopeDenied,getStatusChange:async()=>ok({changeId:'C1',realName:'私有'})},{window:{print(){prints++}}});vm.change={changeId:'C1'};vm.loading=false;await vm.doPrint();assert.equal(prints,0);assert.equal(vm.change,null);assert.equal(vm.schoolName,'');const q=deferred();const other=mount('AaStatusChangePrintView.vue',{getContext:async()=>ok({}),getStatusChange:()=>q.promise}).vm;const pending=other.load();other.$route.params.id='C2';other.clear();q.resolve(ok({changeId:'C1',realName:'旧'}));await pending;assert.equal(other.change,null)})
