import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {gradeError} from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
const source=readFileSync(new URL('../src/modules/academicAffairs/views/AaMakeupStudentView.vue',import.meta.url),'utf8')
const candidate={gradeId:'1000000000000063602',courseId:'10',courseName:'课程甲',courseCode:'C1',courseVersion:1,attemptNo:1,score:50}
const options=()=>({code:0,data:{retakeOptions:[{...candidate}],exemptionOptions:[{...candidate}],identityDebtCount:0}})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function mount(api={},identity={},files={},userType='STUDENT'){
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/ {2}components: \{[^\n]+\},/,'').replace('export default','return')
 const component=new Function('api','gradeIdentityApi','academicStatusLabel','currentUserFromToken','fileSdk','gradeError',script)(api,{myMakeupOptions:async()=>options(),...identity},s=>s,()=>({userType}),files,gradeError)
 const vm={...component.data(),ctx:{},identityKey:'I1'};for(const [key,value] of Object.entries(component.methods))vm[key]=value.bind(vm);for(const [key,value] of Object.entries(component.computed))if(key!=='identityKey')Object.defineProperty(vm,key,{get:()=>value.call(vm)})
 vm.options=options().data;vm.form.gradeId=candidate.gradeId;return vm
}
test('本人补重免申请模板可编译',()=>{const {descriptor,errors}=parse(source);assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'AaMakeupStudentView.vue',id:'student-makeup'}).errors,[])})
test('重修保留长ID字符串，正式本人记录确认后才清草稿',async()=>{
 let payload;const vm=mount({retakeApply:async body=>{payload=body;return {code:0,data:{applyId:'R1'}}},retakeMy:async()=>({code:0,data:{items:[{applyId:'R1',reason:'申请补修',status:'SUBMITTED'}]}})})
 vm.form.reason='申请补修';vm.openConfirm();await vm.submitApply();assert.equal(payload.gradeId,candidate.gradeId);assert.equal(typeof payload.gradeId,'string');assert.equal(vm.receipt.verified,true);assert.equal(vm.form.reason,'')
})
test('申请前候选消失不写旧成绩，保留理由',async()=>{
 let writes=0;const vm=mount({retakeApply:async()=>{writes++}},{myMakeupOptions:async()=>({code:0,data:{retakeOptions:[]}})});vm.form.reason='需重修';vm.openConfirm();await vm.submitApply();assert.equal(writes,0);assert.equal(vm.form.reason,'需重修');assert.match(vm.formError,/已变化/)
})
test('响应丢失即使存在同名申请也保持未决，不能自动重放',async()=>{
 let writes=0;const vm=mount({retakeApply:async()=>{writes++;throw new Error('timeout')},retakeMy:async()=>({code:0,data:{items:[{applyId:'other',courseName:'课程甲',reason:'',status:'SUBMITTED'}]}})})
 vm.openConfirm();await vm.submitApply();await vm.submitApply();await vm.verifyApply();assert.equal(writes,1);assert.equal(vm.receipt.verified,false);assert.ok(vm.pending)
})
test('正式回读403清除本人记录、材料和申请草稿',async()=>{
 const vm=mount({retakeApply:async()=>({code:0,data:{applyId:'R1'}}),retakeMy:async()=>({code:403001})});vm.form.reason='私有理由';vm.materials=[{fileId:'F1'}];vm.rows=[{applyId:'old'}];vm.openConfirm();await vm.submitApply();assert.deepEqual(vm.rows,[]);assert.deepEqual(vm.materials,[]);assert.equal(vm.form.reason,'');assert.equal(vm.receipt,null)
})
test('教师身份不能调用学生本人申请',async()=>{
 let writes=0;const vm=mount({retakeApply:async()=>{writes++}}, {},{},'TEACHER');vm.openConfirm();await vm.submitApply();assert.equal(vm.canSubmit,false);assert.equal(writes,0)
})
test('免修材料沿既有选填合同，附带材料提交前重新核对安全状态',async()=>{
 let writes=0;const vm=mount({exemptionApply:async()=>{writes++}}, {},{metadata:async()=>({readyForBusiness:false})});vm.tab='exemption';vm.form.courseId='10';assert.equal(vm.canSubmit,true);vm.materials=[{fileId:'F1',readyForBusiness:false}];assert.equal(vm.canSubmit,false);vm.materials=[{fileId:'F1',readyForBusiness:true}];vm.openConfirm();await vm.submitApply();assert.equal(writes,0);assert.equal(vm.pending,null);assert.equal(vm.materials.length,1)
})
test('身份切换后迟到文件上传不读取元数据也不回灌',async()=>{
 const q=deferred();let metadata=0,cancel=0;const vm=mount({}, {},{upload:()=>({promise:q.promise,cancel(){cancel++}}),metadata:async()=>{metadata++;return {}}});vm.tab='exemption';const upload=vm.pickMaterial({target:{files:[{name:'材料.pdf',size:20}],value:'x'}});vm.identityKey='I2';vm.invalidate();q.resolve({fileId:'old'});await upload;assert.equal(metadata,0);assert.equal(cancel,1);assert.deepEqual(vm.materials,[])
})
test('超大文件在上传前拒绝',async()=>{let uploads=0;const vm=mount({}, {},{upload:()=>{uploads++}});vm.tab='exemption';await vm.pickMaterial({target:{files:[{size:11*1024*1024}],value:''}});assert.equal(uploads,0);assert.match(vm.formError,/10MB/)})
test('切tab后旧申请读取的catch/finally不覆盖新页',async()=>{
 const q=deferred(),b=deferred();const vm=mount({retakeMy:()=>q.promise,exemptionMy:()=>b.promise});const old=vm.reload();vm.invalidate();vm.tab='exemption';const next=vm.reload();q.reject({code:403001});await old;assert.equal(vm.loading,true);assert.equal(vm.readError,'');b.resolve({code:0,data:{items:[{exemptionId:'E1'}]}});await next;assert.equal(vm.rows[0].exemptionId,'E1')
})
