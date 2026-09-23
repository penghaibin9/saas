import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { gradeError, gradeStatusLabel, gradeQueueState, gradeTaskDestination } from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'
const names = ['AaTranscriptView', 'AaGradeOverviewView', 'AaGradeFailListView', 'AaGradeExceptionView', 'AaGradeAuditView']
const sources = Object.fromEntries(names.map(name => [name, readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')]))
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b }); return {promise,resolve,reject} }
const gradeRow = gradeId => ({ gradeId: String(gradeId), term: '2026-1', academicIdentity: { termCode: '2026-1', status: 'RESOLVED' } })
const transcript = (studentId, items = [], page = 1, pageSize = 30) => ({ studentId, page, pageSize, total: items.length, identityCoverage: 'PAGE', historicalIdentityComplete: true, items })
const exceptionRow = (recordId, gradeTaskId) => ({ recordId: String(recordId), gradeTaskId: String(gradeTaskId), studentId: '301', studentName: '测试学生', teacherAuthorityReady: true, teacherKeys: [], teacherNames: [] })
const auditRow = id => ({ id: String(id), bizType: 'AA_GRADE_TASK' })
function mount(name, api = {}, notices = []) {
  const script = sources[name].match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import [\s\S]*? from ['"][^'"\n]+['"]\s*\n/g,'').replace(/ {2}components: \{[\s\S]*?\},/,'').replace('export default','return')
  const options = new Function('academicAffairsApi','toast','currentUserFromToken','gradeError','gradeStatusLabel','EXCEPTION_FLAG_LABEL','exceptionFlagColor','gradeQueueState','gradeTaskDestination',script)(api,{success: m=>notices.push(m),error:m=>notices.push(m)},()=>({}),gradeError,gradeStatusLabel,{ABSENT:'缺考'},()=> 'warning',gradeQueueState,gradeTaskDestination)
  const vm = { $route:{path:'/test',fullPath:'/test',query:{}}, ctx:{currentRole:{},dataScope:{}}, identityKey:'identity-A' }
  Object.assign(vm,options.data.call(vm))
  for (const [key,method] of Object.entries(options.methods)) vm[key]=method.bind(vm)
  for (const [key,getter] of Object.entries(options.computed || {})) if (key!=='identityKey') Object.defineProperty(vm,key,{get:()=>getter.call(vm)})
  vm.$options=options
  vm.$router = {
    push: r => notices.push(r),
    replace: async r => {
      const query = r.query || {}
      vm.$route = { path: r.path || vm.$route.path, query, fullPath: `${r.path || vm.$route.path}?${new URLSearchParams(query)}` }
      options.watch?.routeKey?.call(vm)
    }
  }
  return vm
}
for (const name of names) test(`${name} 完整模板可编译`,()=>{
 const {descriptor,errors}=parse(sources[name]);assert.deepEqual(errors,[])
 assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:name+'.vue',id:name}).errors,[])
})
test('成绩单旧成功、异常和 finally 均不能覆盖新学生',async()=>{
 const a=deferred(),b=deferred();const vm=mount('AaTranscriptView',{getTranscript:id=>id==='101'?a.promise:b.promise})
 vm.studentId='101';const first=vm.load();vm.onStudentChange('102',[{label:'乙'}]);assert.equal(vm.loading,true)
 a.reject(new Error('old'));await first;assert.equal(vm.loading,true);assert.equal(vm.error,'')
 b.resolve({code:0,data:transcript('102',[gradeRow('2')])});await Promise.resolve();await Promise.resolve();assert.equal(vm.data.items[0].gradeId,'2')
})
test('清空学生选择清除旧成绩、用途和导出状态',()=>{
 const vm=mount('AaTranscriptView');vm.data={items:[{}]};vm.exportPurpose='旧学生用途';vm.exporting=true
 vm.onStudentChange('',[]);assert.equal(vm.data,null);assert.equal(vm.exportPurpose,'');assert.equal(vm.exporting,false)
})
test('未知成绩结果和缺失来源不能落为不及格或普通修读',()=>{
 const vm=mount('AaTranscriptView');assert.equal(vm.passLabel(null),'结果待核对');assert.equal(vm.passLabel('FAIL'),'不及格');assert.equal(vm.sourceLabel(null),'来源待核对')
})
test('导出快速点击仅一次，切换学生后旧文件与提示均丢弃',async()=>{
 const q=deferred(),notices=[];let calls=0;const vm=mount('AaTranscriptView',{exportTranscript:()=>{calls++;return q.promise}},notices)
 vm.studentId='101';vm.data={items:[{}]};vm.pagination.total=1;vm.exportPurpose='用于本次核对';const first=vm.doExport();await vm.doExport();vm.onStudentChange('',[])
 q.resolve({code:0,data:{}});await first;assert.equal(calls,1);assert.deepEqual(notices,[]);assert.equal(vm.exporting,false)
})
test('成绩单导出 403 清空旧学生明细与用途',async()=>{
 const vm=mount('AaTranscriptView',{exportTranscript:async()=>({code:403001})});vm.studentId='101';vm.data={items:[{}]};vm.pagination.total=1;vm.exportPurpose='用于本次核对';await vm.doExport()
 assert.equal(vm.data,null);assert.equal(vm.exportPurpose,'');assert.match(vm.error,/无权/)
})
for (const [name,api] of [['AaGradeFailListView','getFailList'],['AaGradeExceptionView','getExceptionList'],['AaGradeAuditView','getGradeAudit']]) {
 test(`${name} 旧分页异常不污染新分页，403清除旧数据`,async()=>{
  const a=deferred(),b=deferred();const vm=mount(name,{[api]:p=>p.page===1?a.promise:b.promise})
  const first=vm.load();vm.pagination.page=2;const second=vm.load();a.reject(new Error('old'));await first;assert.equal(vm.loading,true);assert.equal(vm.error,'')
  b.resolve({code:403001});await second;assert.equal(vm.loading,false);assert.deepEqual(vm.rows,[]);assert.equal(vm.pagination.total,0);assert.match(vm.error,/无权/)
 })
 test(`${name} 身份切换立即清除旧列表，旧成功不能回灌`,async()=>{
  const q=deferred(),next=deferred();let calls=0;const vm=mount(name,{[api]:()=>++calls===1?q.promise:next.promise});const first=vm.load();vm.rows=[{id:'old-visible'}];vm.identityKey='identity-B';vm.$options.watch.identityKey.call(vm);assert.deepEqual(vm.rows,[]);q.resolve({code:0,data:{list:[{id:'old'}],total:1}});await first;assert.deepEqual(vm.rows,[]);assert.equal(vm.loading,true)
  const nextRow=name==='AaGradeExceptionView'?exceptionRow('11','21'):name==='AaGradeAuditView'?auditRow('11'):{id:'new',gradeId:'new'}
  next.resolve({code:0,data:{list:[nextRow],total:1}});await Promise.resolve()
  assert.equal(name==='AaGradeExceptionView'?vm.rows[0].recordId:vm.rows[0].id,name==='AaGradeExceptionView'?'11':name==='AaGradeAuditView'?'11':'new')
 })
}
test('成绩总览首屏只读取一页正式任务，分析点击后才加载',async()=>{
 const calls=[];const vm=mount('AaGradeOverviewView',{getGradeTasks:async p=>{calls.push(p);return {code:0,data:{list:[],total:0}}},getGradeAnalysis:async()=>{calls.push('analysis');return {code:0,data:{rows:[]}}}})
 await vm.$options.created.call(vm);assert.equal(calls.length,1);assert.equal(calls[0].pageSize,20);assert.equal(vm.showAnalysis,false)
 vm.toggleAnalysis();await Promise.resolve();assert.equal(calls[1],'analysis');assert.equal(vm.pct(null),'待核对')
})

test('成绩队列刷新恢复学期、状态、课程和页码，查询条件传给服务端', async () => {
 const calls=[]; const vm=mount('AaGradeOverviewView',{getGradeTasks:async p=>{calls.push(p);return {code:0,data:{list:[],total:0}}}})
 vm.$route.query={term:'2026-2027-1',status:'RETURNED',keyword:'实践',page:'3'}
 await vm.restoreTaskQuery()
 assert.deepEqual(calls,[{term:'2026-2027-1',status:'RETURNED',keyword:'实践',page:3,pageSize:20}])
 assert.equal(vm.taskStatus,'RETURNED');assert.equal(vm.taskPage,3);assert.equal(vm.taskKeyword,'实践')
})

test('任务入口使用服务端动作并保留大整数对象和来源队列', () => {
 const routes=[];const vm=mount('AaGradeOverviewView',{},routes);vm.academicFlow={captureReturn:()=> 'saved-position'}
 vm.openTask({gradeTaskId:'90071992547409937',status:'ACADEMIC_REVIEW',allowedActions:['VIEW','PUBLISH']})
 assert.equal(routes[0].path,'/admin/academic-affairs/grade-publish');assert.equal(routes[0].query.taskId,'90071992547409937');assert.equal(routes[0].query.returnToken,'saved-position')
 assert.equal(gradeTaskDestination({status:'SUBMITTED',allowedActions:['VIEW','COLLEGE_REVIEW']}).page,'grade-college-review')
 assert.equal(gradeTaskDestination({status:'PUBLISHED',allowedActions:['VIEW','ARCHIVE']}).label,'查看正式成绩')
 assert.equal(gradeTaskDestination({status:'RETURNED',allowedActions:['VIEW','INPUT']}).label,'修改并重交')
 assert.equal(gradeTaskDestination({status:'ACADEMIC_REVIEW',allowedActions:['VIEW']}).page,'grade-entry')
})

test('非法成绩查询不请求后端，旧请求不能覆盖新筛选', async () => {
 const pending=deferred();let calls=0;const vm=mount('AaGradeOverviewView',{getGradeTasks:()=>{calls++;return pending.promise}})
 const first=vm.restoreTaskQuery();vm.$route.query={status:['INPUTTING','PUBLISHED']};await vm.restoreTaskQuery()
 pending.resolve({code:0,data:{list:[{gradeTaskId:'old'}],total:1}});await first
 assert.equal(calls,1);assert.deepEqual(vm.tasks,[]);assert.match(vm.taskError,/查询条件无效/)
})
test('总览分析筛选变化作废旧读取与导出上下文',async()=>{
 const q=deferred();const vm=mount('AaGradeOverviewView',{getGradeAnalysis:()=>q.promise});const first=vm.load();vm.term='new';vm.clearAnalysis();q.resolve({code:0,data:{total:999}});await first;assert.equal(vm.data.total,undefined);assert.equal(vm.loading,false)
})
test('成绩异常使用正式任务标识下钻',()=>{
 const routes=[];const vm=mount('AaGradeExceptionView',{},routes);vm.goTask({gradeTaskId:'90071992547409937'});assert.equal(routes[0].query.taskId,'90071992547409937')
})
