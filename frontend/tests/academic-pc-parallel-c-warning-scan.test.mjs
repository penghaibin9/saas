import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileTemplate} from '@vue/compiler-sfc'
import {WARNING_LEVEL,WARNING_SOURCE,warningColor} from '../src/modules/academicAffairs/constants/grade-graduation.js'
import {gradeError} from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
const source=readFileSync(new URL('../src/modules/academicAffairs/views/AaWarningView.vue',import.meta.url),'utf8')
const ok=data=>({code:0,data}),denied={code:403002,bizCode:'NO_DATA_SCOPE'}
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
function mount(overrides={}){
 const rule={key:'warning_fail_threshold',label:'挂科门数',value:2};const api={getWarnings:async()=>ok({list:[],total:0}),scanWarnings:async()=>ok({created:0,updated:0}),getRules:async()=>ok({items:[{...rule}]}),...overrides}
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/components\s*:\s*\{[^}]*\},?/,'').replace('export default','return')
 const deps={academicAffairsApi:api,academicAffairsWarningApi:api,WARNING_LEVEL,WARNING_SOURCE,warningColor,gradeError,currentUserFromToken:()=>({}),matchPermission:patterns=>patterns.includes('*')}
 const component=new Function(...Object.keys(deps),script)(...Object.values(deps));const vm={ctx:{permissionPatterns:['*'],currentRole:{},dataScope:{}},identity:'I1',...component.data()}
 for(const [k,v] of Object.entries(component.methods))vm[k]=v.bind(vm)
 for(const [k,v] of Object.entries(component.computed))if(k!=='identity')Object.defineProperty(vm,k,{get:()=>v.call(vm)})
 return {vm,rule,api,component}
}
test('挂科预警页模板编译且无记录不等于全部风险排除',()=>{const {descriptor,errors}=parse(source);assert.deepEqual(errors,[]);assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'warning.vue',id:'warning'}).errors,[]);assert.match(source,/无记录不代表所有规则已扫描/);assert.doesNotMatch(source,/row\.sourceCode\s*}}/ )})
test('无规则管理权限不能执行扫描',async()=>{let calls=0;const {vm}=mount({getRules:async()=>{calls++},scanWarnings:async()=>{calls++}});vm.ctx.permissionPatterns=[];await vm.scan();await vm.confirmScan();assert.equal(calls,0);assert.equal(vm.command,null)})
test('扫描需先展示规则，确认后单次POST与正式列表GET，0计数保留',async()=>{let writes=0,reads=0;const gate=deferred();const {vm}=mount({scanWarnings:async()=>{writes++;await gate.promise;return ok({created:0,updated:0})},getWarnings:async()=>{reads++;return ok({list:[],total:0})}});await vm.scan();assert.equal(writes,0);assert.match(vm.confirmMessage,/阈值 2/);const task=vm.confirmScan();await vm.confirmScan();gate.resolve();await task;assert.equal(writes,1);assert.equal(reads,1);assert.equal(vm.receipt.verified,true);assert.match(vm.receipt.message,/新增 0 条/)})
test('确认后阈值变化不执行旧扫描',async()=>{let writes=0;const {vm,rule}=mount({scanWarnings:async()=>{writes++}});await vm.scan();rule.value=3;await vm.confirmScan();assert.equal(writes,0);assert.equal(vm.command,null);assert.equal(vm.pending,null);assert.match(vm.actionError,/变化/)})
test('扫描超时只读当前台账，不能凭空列表解除未决或自动重放',async()=>{let writes=0;const {vm}=mount({scanWarnings:async()=>{writes++;throw Error('timeout')}});await vm.scan();await vm.confirmScan();await vm.verify();await vm.scan();assert.equal(writes,1);assert.ok(vm.pending);assert.equal(vm.receipt.verified,false);assert.equal(vm.scanning,false)})
test('扫描回读复合403清旧学生和回执',async()=>{const {vm}=mount({getWarnings:async()=>denied});vm.rows=[{studentName:'旧学生'}];await vm.scan();await vm.confirmScan();assert.deepEqual(vm.rows,[]);assert.equal(vm.receipt,null);assert.equal(vm.pending,null);assert.equal(vm.scanning,false)})
test('切筛选旧失败和finally不污染新名单',async()=>{const gate=deferred();let calls=0;const {vm}=mount({getWarnings:async()=>++calls===1?gate.promise:ok({list:[{warningId:'W2',studentName:'乙'}],total:1})});const task=vm.load();vm.filters.level='HIGH';await vm.load();gate.resolve(denied);await task;assert.equal(vm.rows[0].warningId,'W2');assert.equal(vm.error,'');assert.equal(vm.loading,false)})
test('身份改变后旧扫描结果不能回灌',async()=>{const gate=deferred();let started;const ready=new Promise(r=>{started=r});const {vm}=mount({scanWarnings:async()=>{started();return gate.promise}});await vm.scan();const task=vm.confirmScan();await ready;vm.identity='I2';vm.clear();gate.resolve(ok({created:2,updated:1}));await task;assert.equal(vm.receipt,null);assert.deepEqual(vm.rows,[]);assert.equal(vm.scanning,false)})
