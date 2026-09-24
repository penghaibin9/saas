import * as makeupEvidence from '../src/modules/academicAffairs/views/parallel-c/makeup-evidence.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {gradeError} from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
const names=['AaExemptionArchiveView','AaMakeupPrintView','AaMakeupStatsView']
const sources=Object.fromEntries(names.map(n=>[n,readFileSync(new URL(`../src/modules/academicAffairs/views/${n}.vue`,import.meta.url),'utf8')]))
const list=(...rows)=>({code:0,data:{list:rows,total:rows.length}})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function testRuntime(){const entries=new Map();return {crypto:globalThis.crypto,sessionStorage:{getItem:key=>entries.get(key)??null,setItem:(key,value)=>entries.set(key,String(value)),removeItem:key=>entries.delete(key)}}}
function mount(name,api={},base={},fileSdk={}){
 const script=sources[name].match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/ {2}components: \{[^\n]+\},/,'').replace('export default','return')
 const options=new Function('api','academicAffairsApi','academicStatusLabel','currentUserFromToken','gradeError','matchPermission','fileSdk',...Object.keys(makeupEvidence),'globalThis',script)(api,base,s=>s,()=>({}),gradeError,(patterns)=>patterns.includes('*'),fileSdk,...Object.values(makeupEvidence),testRuntime())
 const vm={...options.data(),ctx:{currentRole:{},dataScope:{},permissionPatterns:['*']},identityKey:'I1',$route:{params:{id:'B1'}},$nextTick:async()=>{}}
 for(const [key,value] of Object.entries(options.methods))vm[key]=value.bind(vm)
 for(const [key,value] of Object.entries(options.computed))if(key!=='identityKey')Object.defineProperty(vm,key,{get:()=>value.call(vm)})
 vm.options=options;return vm
}
for(const name of names)test(`${name}模板可编译`,()=>{const {descriptor,errors}=parse(sources[name]);assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:name+'.vue',id:name}).errors,[])})
const archivedRow=(archiveStatus='NOT_ARCHIVED')=>({exemptionId:'601',exemptionVersion:archiveStatus==='ARCHIVED'?1:0,evidenceManifestHash:null,course:{id:'88'},evidenceState:'VALID',evidenceFiles:[],studentName:'甲',courseName:'乙',status:'APPROVED',archiveStatus})
test('归档POST成功但正式状态未变，不能确认；只读恢复不重放',async()=>{
 let writes=0,done=false;const vm=mount('AaExemptionArchiveView',{archiveExemption:async()=>{writes++;return {code:0,data:{exemptionId:'601',archiveStatus:'ARCHIVED',exemptionVersion:1}}},archiveList:async()=>list(archivedRow(done?'ARCHIVED':'NOT_ARCHIVED'))})
 vm.rows=[archivedRow()];vm.confirmArchive(vm.rows[0]);await vm.markArchived();assert.equal(vm.receipt.verified,false);await vm.markArchived();done=true;await vm.verifyArchive();assert.equal(writes,1);assert.equal(vm.rows[0].archiveStatus,'ARCHIVED');assert.equal(vm.receipt.verified,true)
})
test('归档回读403清除旧材料/对象/回执',async()=>{
 let reads=0;const vm=mount('AaExemptionArchiveView',{archiveList:async()=>++reads===1?list(archivedRow()):{code:403001},archiveExemption:async()=>({code:0,data:{exemptionId:'601',archiveStatus:'ARCHIVED',exemptionVersion:1}})})
 vm.rows=[archivedRow()];vm.openMaterials({...archivedRow(),materialFiles:[{fileId:'F1',fileName:'私有'}]});vm.confirmArchive(archivedRow());await vm.markArchived();assert.deepEqual(vm.rows,[]);assert.deepEqual(vm.materialFiles,[]);assert.equal(vm.receipt.verified,false);assert.ok(vm.pending?.recovered);assert.equal(vm.materialsVisible,false)
})
test('归档未知状态或无归档权限不能提交',async()=>{const vm=mount('AaExemptionArchiveView');assert.equal(vm.canArchive({...archivedRow(),archiveStatus:null}),false);vm.ctx.permissionPatterns=[];assert.equal(vm.canArchive(archivedRow()),false)})
test('旧文件元数据返回时详情已关闭，不请求URL也不打开文件',async()=>{
 const q=deferred();let urls=0;const file={fileId:'F1',fileName:'材料',bindingStatus:'ACTIVE',isCurrent:true};const vm=mount('AaExemptionArchiveView',{}, {},{metadata:()=>q.promise,authorizedUrl:async()=>{urls++;return {}}})
 vm.openMaterials({...archivedRow(),evidenceFiles:[file]});const pending=vm.openFile(file,'preview');vm.closeMaterials();q.resolve({allowedActions:['preview']});await pending;assert.equal(urls,0);assert.equal(vm.fileBusy,false)
})
test('文件当前授权不允许下载，清理材料，不尝试签名地址',async()=>{
 let urls=0;const file={fileId:'F1',bindingStatus:'ACTIVE',isCurrent:true};const vm=mount('AaExemptionArchiveView',{}, {},{metadata:async()=>({allowedActions:[]}),authorizedUrl:async()=>{urls++}})
 vm.openMaterials({...archivedRow(),evidenceFiles:[file]});await vm.openFile(file,'download');assert.equal(urls,0);assert.deepEqual(vm.materialFiles,[]);assert.match(vm.error,/无权/)
})
test('打印批次切换后旧异常不盖住新名单',async()=>{
 const a=deferred(),b=deferred();const vm=mount('AaMakeupPrintView',{printData:id=>id==='A'?a.promise:b.promise},{getContext:async()=>({code:0,data:{tenantBrandConfig:{schoolName:'验证学校'}}})})
 vm.$route.params.id='A';const old=vm.load();vm.$route.params.id='B';const next=vm.load();a.reject({code:403001});await old;assert.equal(vm.loading,true);assert.equal(vm.error,'');b.resolve({code:0,data:{batchName:'新批次',students:[]}});await next;assert.equal(vm.data.batchName,'新批次')
})
test('打印403不保留上一批次学生',async()=>{
 const vm=mount('AaMakeupPrintView',{printData:async()=>({code:403001})},{getContext:async()=>({code:0,data:{}})});vm.data={batchName:'旧',students:[{studentName:'私有'}]};await vm.load();assert.deepEqual(vm.data.students,[]);assert.equal(vm.data.batchName,undefined);assert.match(vm.error,/无权/)
})
test('统计缺失值保持null，实际0保留',()=>{const vm=mount('AaMakeupStatsView');assert.equal(vm.cards[0].count,null);vm.stats={makeup:{count:0}};assert.equal(vm.cards[0].count,0);assert.equal(vm.cards[1].count,null)})
test('统计快速换维度旧response/finally不覆盖新读取',async()=>{
 const a=deferred(),b=deferred();const vm=mount('AaMakeupStatsView',{stats:p=>p.dimension==='course'?a.promise:b.promise});vm.filters.dimension='course';const old=vm.search();vm.filters.dimension='term';const next=vm.search();a.resolve({code:0,data:{makeup:{count:99}}});await old;assert.equal(vm.loading,true);b.resolve({code:0,data:{makeup:{count:2}}});await next;assert.equal(vm.cards[0].count,2)
})
test('统计下钻20分页，不自动拉其它条线',async()=>{
 const calls=[];const vm=mount('AaMakeupStatsView',{statsDetail:async p=>{calls.push(p);return list({applyId:'R1',status:'APPROVED'})}});vm.stats={};vm.loading=false;await vm.onDrill('retake',2);assert.deepEqual(calls.map(p=>[p.line,p.page,p.pageSize]),[['retake',2,20]]);assert.equal(vm.detailRows[0].rowKey,'R1')
})
test('导出冻结范围、防双击；身份失效后不下载旧文件',async()=>{
 const q=deferred();let writes=0;const vm=mount('AaMakeupStatsView',{exportStats:()=>{writes++;return q.promise}});vm.loading=false;vm.stats={};vm.filters.term='2026-1';vm.openExport();const pending=vm.doExport({reason:'统计核对'});await vm.doExport({reason:'再次'});vm.identityKey='I2';vm.invalidate();q.resolve({code:0,data:'不得下载'});await pending;assert.equal(writes,1);assert.equal(vm.exporting,false);assert.equal(vm.exportVisible,false)
})
