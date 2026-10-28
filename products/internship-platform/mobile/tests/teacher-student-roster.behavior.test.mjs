import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile,createSSRApp,h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { normalizeError,request } from './request-module.mjs'
import { normalizeFileReadiness } from '../src/services/fileReadiness.mjs'
const batch='9007199254740993001'
const rows=Array.from({length:23},(_,i)=>({id:String(9007199254740993100n+BigInt(i)),name:`合成学生${i+1}`,studentNo:`000${i+1}`,enterpriseName:'合成企业',batchId:batch}))
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
function page(kind='enterprise',options={}) {
  const source=fs.readFileSync(new URL(`../src/pages/teacher-internship/${kind==='enterprise'?'enterprise-eval':'internship-score'}/index.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  let generation=0;const reads=[],writes=[],permissions=new Set(['internship.student.view','internship.eval.enterprise.manage','internship.eval.enterprise.view','internship.score.manage'])
  const context={selectedBatchId:batch,batches:[{id:batch,name:'合成批次'},{id:'22',name:'另一批次'}],roleCode:'SCHOOL_ADMIN',can:p=>permissions.has(p),restore(){},load:async()=>{},selectBatch(id){this.selectedBatchId=String(id);return true}}
  const studentRead=async(id,paging={})=>{reads.push({batchId:id,...paging});if(options.students)return options.students(id,paging);const p=paging.page||1;return {items:rows.slice((p-1)*20,p*20),total:23,page:p,pageSize:20}}
  const deps={useSessionStore:()=>({identity:{userId:'8'}}),useInternshipContextStore:()=>context,currentSessionGeneration:()=>generation,normalizeError,createSubmitLock:request.createSubmitLock,toast(){},teacherInternshipMyStudents:studentRead,teacherInternshipEnterpriseEvals:async()=>{if(options.listError)throw options.listError;return {items:options.evals||[],total:0}},teacherInternshipScores:async()=>({items:[],total:0}),teacherInternshipEnterpriseEvalCreate:async(id,body)=>{writes.push({kind:'create',id,body});return options.write ? options.write() : {}},teacherInternshipEnterpriseEvalResubmit:async(id,bid,body)=>{writes.push({kind:'resubmit',id,bid,body});return options.write ? options.write() : {}},teacherInternshipEnterpriseEvalReview:async()=>{},teacherApi:{computeInternshipScore:async body=>{writes.push({kind:'compute',body});return options.write ? options.write() : {id:'1',version:0,total:0}}},chooseSingleFile:async()=>null,uploadBusinessFile:async()=>({}),uni:{showToast(){},stopPullDownRefresh(){}}}
  Object.assign(deps,{normalizeFileReadiness,fileSdk:{metadata:options.fileMetadata || (async id=>({fileId:id,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true}))}})
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data()}
  for(const[name,fn]of Object.entries(component.methods))vm[name]=fn.bind(vm)
  for(const[name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('<script>')).replace(/<\/template>\s*$/,'')
  const shell={setup:(_,{slots})=>()=>h('div',slots.default?.())},components={MobilePrivacyGate:{render:()=>null},MobileNavBar:{render:()=>null},MobileGlobalState:{props:['state','title','description'],setup:(p,{slots})=>()=>p.state==='ready'?h('div',slots.default?.()):h('section',[p.title,p.description])},MobileSafeAreaBar:shell,MobileStatusTag:{props:['label'],setup:p=>()=>h('span',p.label)},MobileInlineAlert:{props:['title','description'],setup:p=>()=>h('p',[p.title,p.description])}}
  const render=compile(template,{isCustomElement:t=>['view','text','picker','switch','image'].includes(t)})
  return {vm,component,context,permissions,reads,writes,switchIdentity:()=>generation++,html:()=>renderToString(createSSRApp({components,render:()=>render(vm,[])}))}
}

test('企业材料已接收但扫描未完成时保留表单，读取安全结果后才可沿原字段保存',async()=>{
  const p=page('enterprise');await p.vm.load();await p.vm.openCreate()
  Object.assign(p.vm.form,{mentorName:'合成企业导师',sourceFileId:'81',attendanceScore:'0',skillScore:'0',attitudeScore:'0',collaborationScore:'0',safetyScore:'0'})
  p.vm.sourceFileInfo={fileId:'81',readyForBusiness:false,statusText:'等待安全扫描'}
  p.vm.submit();assert.equal(p.writes.length,0);assert.equal(p.vm.form.mentorName,'合成企业导师')
  await p.vm.refreshSourceFile();assert.equal(p.vm.sourceFilePending,false);p.vm.submit();await new Promise(r=>setImmediate(r))
  assert.equal(p.writes[0].body.sourceFileId,'81');assert.equal(p.writes[0].body.attendanceScore,0)
})

test('企业材料安全读取失败与旧身份回执均不能解锁，原材料和输入保留',async()=>{
  const p=page('enterprise',{fileMetadata:async()=>{throw Error('temporary')}});await p.vm.load();await p.vm.openCreate();p.vm.form.sourceFileId='81';p.vm.form.mentorName='原输入'
  await p.vm.refreshSourceFile();assert.equal(p.vm.sourceFilePending,true);assert.match(p.vm.sourceFileInfo.statusText,/已保留/);assert.equal(p.vm.form.mentorName,'原输入')
  const wait=deferred(),q=page('enterprise',{fileMetadata:()=>wait.promise});await q.vm.load();await q.vm.openCreate();q.vm.form.sourceFileId='82';q.vm.sourceFileInfo={fileId:'82',readyForBusiness:false}
  const reading=q.vm.refreshSourceFile();q.switchIdentity();wait.resolve({fileId:'82',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true});await reading;assert.equal(q.vm.sourceFilePending,true)
})

test('正式学生helper复用真实分页名单契约，不请求旧my-students且保留大编号',async()=>{
  const calls=[],source=fs.readFileSync(new URL('../src/services/internshipApi.js',import.meta.url),'utf8').replace(/^import[^\n]+\r?\n/gm,'').replace(/^export /gm,'')
  const helper=new Function('realRequest',source+'\nreturn teacherInternshipMyStudents;')((url,options)=>{calls.push({url,options});return Promise.resolve({items:rows.slice(20),total:23,page:2,pageSize:20})})
  const result=await helper(batch,{page:2,pageSize:20});const url=new URL(calls[0].url,'http://local.invalid');assert.equal(url.pathname,'/internship/intern-students');assert.equal(url.searchParams.get('batchId'),batch);assert.equal(url.searchParams.get('page'),'2');assert.equal(url.searchParams.get('pageSize'),'20');assert.equal(calls[0].options._rawPage,true);assert.equal(result.items[0].id,rows[20].id)
})

for(const kind of ['enterprise','score'])test(`${kind}学生名单按20条追加，后页可选且原选择和草稿不变`,async()=>{
  const p=page(kind);await p.vm.load();assert.equal(p.reads.length,0)
  if(kind==='enterprise')await p.vm.openCreate();else await p.vm.onComputeTab()
  assert.deepEqual(p.reads,[{batchId:batch,page:1,pageSize:20}]);assert.equal(p.vm.students.length,20);assert.equal(p.vm.studentHasMore,true)
  p.vm.studentIndex=4;const chosen=p.vm.students[4].id;if(kind==='enterprise'){p.vm.form.mentorName='未交导师姓名';p.vm.form.sourceFileId='81'}
  await p.vm.loadMoreStudents();assert.equal(p.vm.students.length,23);assert.equal(p.vm.students[p.vm.studentIndex].id,chosen);assert.equal(p.vm.studentHasMore,false);assert.equal(p.reads[1].page,2)
  if(kind==='enterprise'){assert.equal(p.vm.form.mentorName,'未交导师姓名');assert.equal(p.vm.form.sourceFileId,'81')}
  p.vm.studentIndex=22;assert.equal(p.vm.students[22].id,rows[22].id)
})

test('企业评价台账不因学生名单缺权限失败，名单拒绝明确且不假装空数据',async()=>{
  const p=page('enterprise',{evals:[{id:'1',studentName:'原评价学生',reviewStatus:'APPROVED'}]});p.permissions.delete('internship.student.view');await p.vm.load();assert.equal(p.vm.state,'ready');assert.equal(p.vm.list.length,1);await p.vm.openCreate();assert.equal(p.reads.length,0);assert.equal(p.vm.studentState,'forbidden');assert.match(await p.html(),/学生名单.*权限|无权.*学生/)
  const denied=page('enterprise',{listError:{httpStatus:403,bizCode:'NO_PERMISSION'}});await denied.vm.load();assert.equal(denied.vm.state,'forbidden')
})

for(const kind of ['enterprise','score'])test(`${kind}后页失败保留选择且重试原页，失权不能选择或提交`,async()=>{
  let fail=true;const p=page(kind,{students:async(id,{page})=>{if(page===2&&fail)throw {httpStatus:503,message:'offline'};return {items:rows.slice((page-1)*20,page*20),total:23,page,pageSize:20}}});await p.vm.load();if(kind==='enterprise')await p.vm.openCreate();else await p.vm.onComputeTab();p.vm.studentIndex=5
  await p.vm.loadMoreStudents();assert.equal(p.vm.students.length,20);assert.equal(p.vm.studentIndex,5);assert.ok(p.vm.studentError);assert.equal(p.vm.studentPage,1)
  fail=false;await p.vm.loadStudents(p.vm.studentAppendFailed);assert.deepEqual(p.reads.map(x=>x.page),[1,2,2]);assert.equal(p.vm.studentIndex,5)
  p.permissions.delete('internship.student.view');if(kind==='enterprise')Object.assign(p.vm.form,{mentorName:'原导师',sourceFileId:'81',attendanceScore:'0',skillScore:'0',attitudeScore:'0',collaborationScore:'0',safetyScore:'0'})
  p.vm.submit();await Promise.resolve();assert.equal(p.writes.length,0)
})

for(const kind of ['enterprise','score'])test(`${kind}切批次或账号后旧名单不回填，后页不清当前输入`,async()=>{
  const late=deferred(),started=deferred();const p=page(kind,{students:(id)=>{if(id===batch){started.resolve();return late.promise}return Promise.resolve({items:[{id:'new',name:'新身份学生'}],total:1,page:1,pageSize:20})}});await p.vm.load()
  const first=p.vm.loadStudents();await started.promise;p.context.selectBatch('22');p.vm.batchId='22';await p.vm.loadStudents();late.resolve({items:rows.slice(0,20),total:23,page:1,pageSize:20});await first;assert.deepEqual(p.vm.students.map(x=>x.id),['new'])
  const waiting=deferred(),q=page(kind,{students:()=>waiting.promise});await q.vm.load();const old=q.vm.loadStudents();q.switchIdentity();waiting.resolve({items:rows,total:23,page:1,pageSize:20});await old;assert.deepEqual(q.vm.students,[])
})

test('企业评价首20人已有评价时仍可加载后页，不把筛后空页当全部无人',async()=>{
  const p=page('enterprise',{evals:rows.slice(0,20).map(x=>({id:'eval'+x.id,internId:x.id,reviewStatus:'APPROVED'}))});await p.vm.load();await p.vm.openCreate();assert.equal(p.vm.students.length,0);assert.equal(p.vm.studentHasMore,true);assert.match(await p.html(),/继续加载学生/)
  await p.vm.loadMoreStudents();assert.deepEqual(p.vm.students.map(x=>x.id),rows.slice(20).map(x=>x.id));assert.equal(p.vm.studentHasMore,false)
})

test('学生名单真实403不拖垮可读台账也不显示暂无学生',async()=>{
  for(const kind of ['enterprise','score']){const p=page(kind,{students:async()=>{throw {httpStatus:403,bizCode:'NO_PERMISSION'}}});await p.vm.load();if(kind==='enterprise')await p.vm.openCreate();else await p.vm.onComputeTab();assert.equal(p.vm.state,'ready');assert.equal(p.vm.studentState,'forbidden');assert.match(p.vm.studentError,/权限/);assert.doesNotMatch(await p.html(),/暂无可代录学生|暂无可核算学生/)}
})

test('成绩后页对象沿原核算命令携原零版本，不发送分项分数',async()=>{
  const p=page('score');await p.vm.load();await p.vm.onComputeTab();await p.vm.loadMoreStudents();p.vm.studentIndex=22;p.vm.list=[{id:'score1',internshipId:rows[22].id,version:0,status:'DRAFT'}]
  p.vm.submit();await new Promise(r=>setImmediate(r));assert.deepEqual(p.writes[0],{kind:'compute',body:{internshipId:rows[22].id,batchId:batch,expectedVersion:0}})
})

test('企业评价原单重交仍保留零评分否录用原版本和原对象',async()=>{
  const p=page('enterprise');await p.vm.load();p.vm.editReturned({id:'9007199254740993999',version:0,studentName:'原学生',studentNo:'0001',reviewStatus:'RETURNED',mentorName:'原企业导师',attendanceScore:0,skillScore:0,attitudeScore:0,collaborationScore:0,safetyScore:0,recommendHire:false});p.vm.form.sourceFileId='81';p.vm.submit();await new Promise(r=>setImmediate(r))
  const sent=p.writes[0];assert.equal(sent.kind,'resubmit');assert.equal(sent.id,'9007199254740993999');assert.equal(sent.bid,batch);assert.equal(sent.body.expectedVersion,0);assert.equal(sent.body.attendanceScore,0);assert.equal(sent.body.recommendHire,false);assert.equal(sent.body.sourceFileId,'81');assert.equal(sent.body.internshipId,undefined)
})

for(const kind of ['enterprise','score'])test(`${kind}原命令迟到成功不清新批次选择草稿或覆盖新回执`,async()=>{
  const late=deferred(),started=deferred();const p=page(kind,{write:()=>{started.resolve();return late.promise}});await p.vm.load();if(kind==='enterprise'){await p.vm.openCreate();Object.assign(p.vm.form,{mentorName:'原导师',sourceFileId:'81',attendanceScore:'0',skillScore:'0',attitudeScore:'0',collaborationScore:'0',safetyScore:'0'})}else await p.vm.onComputeTab()
  p.vm.submit();await started.promise;p.component.onHide.call(p.vm);p.context.selectBatch('22');p.component.onShow.call(p.vm);await new Promise(r=>setImmediate(r));if(kind==='enterprise')p.vm.form.mentorName='新批次未交导师';else p.vm.receipt={id:'new'}
  late.resolve({id:'old',version:1,total:0});await new Promise(r=>setImmediate(r));assert.equal(p.writes.length,1);assert.equal(p.vm.batchId,'22');if(kind==='enterprise')assert.equal(p.vm.form.mentorName,'新批次未交导师');else assert.equal(p.vm.receipt.id,'new')
})
