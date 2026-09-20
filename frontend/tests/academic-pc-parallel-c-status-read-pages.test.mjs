import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {TYPE_LABEL,STATUS_LABEL,statusColor} from '../src/modules/academicAffairs/constants/status-change.js'
import {gradeError} from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
const source=name=>readFileSync(new URL('../src/modules/academicAffairs/views/'+name,import.meta.url),'utf8')
const initial={changeId:'C1'}
const ok=data=>({code:0,data})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function mount(name,api={},extra={}){
 const script=source(name).match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/components\s*:\s*\{[^}]*\},?/,'').replace('export default','return')
 const deps={api,academicAffairsApi:api,currentUserFromToken:()=>({}),matchPermission:(patterns,permission)=>patterns.includes('*')||patterns.includes(permission),TYPE_LABEL,STATUS_LABEL,statusColor,gradeError,...extra}
 const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),events=[]
 const vm={...component.data(),ctx:{currentRole:{},dataScope:{},permissionPatterns:['*']},change:{...initial},identity:'I1',readerIdentity:'I1',$route:{params:{id:initial.changeId},meta:{changeType:'SUSPEND'}},$router:{push(){}},$emit:(...args)=>events.push(args)}
 for(const [key,value] of Object.entries(component.methods))vm[key]=value.bind(vm)
 for(const [key,value] of Object.entries(component.computed||{}))if(!['identity','readerIdentity'].includes(key))Object.defineProperty(vm,key,{get:()=>value.call(vm)})
 return {vm,events,component}
}

for(const name of ['AaStatusChangeArchiveView.vue','AaStatusChangeStatsView.vue'])test(name+'模板编译',()=>{const {descriptor,errors}=parse(source(name));assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:name,id:'read'}).errors,[])})
test('归档只读当前筛选20条，失败不显示无在途或归档通过',async()=>{let query;const {vm}=mount('AaStatusChangeArchiveView.vue',{getStatusChanges:async q=>{query=q;return {code:500}}});await vm.load();assert.equal(query.pageSize,20);assert.equal(query.status,'EFFECTIVE');assert.match(vm.error,/读取失败/);assert.deepEqual(vm.rows,[]);assert.doesNotMatch(source('AaStatusChangeArchiveView.vue'),/可正常归档|已生效（可归档）/)})
test('归档快速切状态丢弃旧403及finally',async()=>{const gate=deferred();let calls=0;const {vm}=mount('AaStatusChangeArchiveView.vue',{getStatusChanges:async()=>++calls===1?gate.promise:ok({list:[{changeId:'R1',status:'RETURNED'}],total:42})});const pending=vm.load();vm.status='RETURNED';await vm.load();gate.resolve({code:403});await pending;assert.equal(vm.rows[0].status,'RETURNED');assert.equal(vm.total,42);assert.equal(vm.error,'')})
test('统计缺失保持待核对，真实0保留；待生效不加入已生效',async()=>{const {vm}=mount('AaStatusChangeStatsView.vue',{getStatusChangeStats:async()=>ok({total:0,effective:0,byStatus:[{key:'APPROVED_PENDING_EFFECTIVE',count:null}]})});await vm.load();assert.equal(vm.data.pending,null);assert.equal(vm.data.effective,0);assert.equal(vm.pendingEffective,null);vm.data.byStatus=[{key:'APPROVED_PENDING_EFFECTIVE',count:2}];assert.equal(vm.pendingEffective,2);assert.equal(vm.data.effective,0)})
test('统计首屏不拉明细，下钻冻结服务器筛选且20条分页',async()=>{let reads=0,query;const {vm}=mount('AaStatusChangeStatsView.vue',{getStatusChangeStats:async()=>ok({total:2}),getStatusChanges:async q=>{reads++;query=q;return ok({list:[],total:31})}});await vm.load();assert.equal(reads,0);vm.detailFilter={status:'APPROVED_PENDING_EFFECTIVE'};await vm.loadDetail();assert.deepEqual(query,{status:'APPROVED_PENDING_EFFECTIVE',page:1,pageSize:20});assert.equal(vm.detailTotal,31)})
test('统计刷新使旧明细无效，当前明细403清旧统计和名单',async()=>{const gate=deferred();const {vm}=mount('AaStatusChangeStatsView.vue',{getStatusChanges:()=>gate.promise,getStatusChangeStats:async()=>ok({total:3})});vm.loading=false;vm.detailFilter={status:'SUBMITTED'};const pending=vm.loadDetail();await vm.load();gate.resolve(ok({list:[initial],total:1}));await pending;assert.deepEqual(vm.detailRows,[]);assert.equal(vm.data.total,3);const other=mount('AaStatusChangeStatsView.vue',{getStatusChanges:async()=>({code:403})}).vm;other.data.total=99;other.detailFilter={status:'SUBMITTED'};await other.loadDetail();assert.equal(other.data.total,null);assert.equal(other.detailFilter,null);assert.match(other.error,/无权/)})
