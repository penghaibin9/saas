import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/pages/student-internship/self-eval/index.vue',import.meta.url),'utf8')
const original={id:'1',version:3,submitStatus:'SUBMITTED',reviewStatus:'RETURNED',selfSummary:'原已保存的实习自评内容，用于正常上下文读取测试。'}
function page(api={}){
  let generation=1;const calls=[]
  const deps={currentSessionGeneration:()=>generation,formatDateTime:v=>v,normalizeError:e=>({pageState:e.status===403?'forbidden':'error',text:'真实读取失败',kind:e.bizCode==='DATA_CONFLICT'?'conflict':'error'}),toast(){},studentApi:{
    getInternship:async()=>({batchId:'18',recordId:'21'}),getInternshipSelfEval:async()=>({...original}),getInternshipScoreAppeal:async()=>({}),submitInternshipSelfEval:async b=>{calls.push(b);return {id:'1',version:4}},...api}}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const c=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...c.data()}
  for(const[k,v]of Object.entries(c.methods))vm[k]=(...a)=>v.apply(vm,a)
  for(const[k,v]of Object.entries(c.computed))Object.defineProperty(vm,k,{get:()=>v.call(vm)})
  vm.requestedBatchId='18';return {vm,c,calls,switchAccount:()=>generation++}
}
test('同批次刷新保留未提交正文与打开版本，服务端更新后阻止覆盖',async()=>{
  let latest=original;const p=page({getInternshipSelfEval:async()=>latest});await p.vm.load();p.vm.form.selfSummary='尚未提交的新正文，任何刷新都不能直接覆盖。';await p.vm.load();assert.match(p.vm.form.selfSummary,/尚未提交/);latest={...original,version:4};await p.vm.load();assert.equal(p.vm.evalData.version,3);assert.ok(p.vm.conflictText);await p.vm.submit();assert.equal(p.calls.length,0)
})
test('读取失败保留草稿并显示错误，恢复后不伪装成新建自评',async()=>{
  let failed=false;const p=page({getInternshipSelfEval:async()=>{if(failed)throw {status:503};return original}});await p.vm.load();p.vm.form.selfSummary='保留输入的自评正文，断网不能清空本次填写。';failed=true;await p.vm.load();assert.equal(p.vm.loaded,false);assert.equal(p.vm.pageState,'error');assert.ok(p.vm.loadError);failed=false;await p.vm.load();assert.match(p.vm.form.selfSummary,/保留输入/);assert.equal(p.vm.evalData.id,'1')
})
test('账号切换或离页后的迟到读取不回填旧学生内容',async()=>{
  for(const kind of ['account','leave']){let resolve;const p=page({getInternship:()=>new Promise(r=>resolve=r)});const pending=p.vm.load();if(kind==='account')p.switchAccount();else p.c.onHide.call(p.vm);resolve({batchId:'18',recordId:'21'});await pending;assert.equal(p.vm.loaded,false);assert.equal(p.vm.dashboard,null)}
})
test('缺失或不匹配批次不发送无上下文自评请求，无权保持明确拒绝',async()=>{
  let reads=0;for(const d of [{},{batchId:'19',recordId:'21'}]){const p=page({getInternship:async()=>d,getInternshipSelfEval:async()=>{reads++}});await p.vm.load();assert.equal(p.vm.loaded,false);assert.equal(p.vm.readonly,true)}assert.equal(reads,0)
  const p=page({getInternship:async()=>{throw {status:403}}});await p.vm.load();assert.equal(p.vm.pageState,'forbidden')
})
test('提交只使用打开时版本；冲突保留原正文且不自动重发',async()=>{
  let calls=0;const p=page({submitInternshipSelfEval:async body=>{calls++;assert.equal(body.expectedVersion,3);throw {bizCode:'DATA_CONFLICT'}}});await p.vm.load();p.vm.form.selfSummary+='这是本次新增说明。';const before=structuredClone(p.vm.form);await p.vm.submit();await p.vm.submit();assert.equal(calls,1);assert.deepEqual(p.vm.form,before);assert.equal(p.vm.evalData.version,3)
})
test('提交完成前离页，迟到结果不显示旧回执或继续读取',async()=>{
  let resolve;const p=page({submitInternshipSelfEval:()=>new Promise(r=>resolve=r)});await p.vm.load();const pending=p.vm.submit();p.c.onHide.call(p.vm);resolve({id:'1',version:4});await pending;assert.equal(p.vm.receipt,null)
})
