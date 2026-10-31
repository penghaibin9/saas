import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/modules/internship/views/PayrollLedgerView.vue',import.meta.url),'utf8')
function page(overrides={}){
  const calls=[],store={selectedBatchId:'2746'}
  const deps=Object.fromEntries(['ModulePageShell','DataTable','ErrorState','LoadingState','AppSelect','AppStatusTag','AppButton','FilePreviewer'].map(k=>[k,{}]))
  Object.assign(deps,{request:async(path,options)=>{calls.push([path,options]);return path.includes('org-tree')?{tree:[]}:path.includes('export')?{filename:'工资.xlsx',rowCount:2}:{items:[],total:2}},currentSessionGeneration:()=>1,useInternshipBatchStore:()=>store,canCode:ctx=>ctx.allowed,formatDateTime:v=>v,normalizeUiError:()=>({userMessage:'读取失败'}),prepareXlsxDownload:x=>({...x,url:'blob:local'}),fileSdk:{blob(){}},URL:{revokeObjectURL(){}},...overrides})
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const c=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...c.data(),ctx:{allowed:true,ctxKey:'school'},$route:{query:{}},$router:{replace(){}}}
  for(const[k,v]of Object.entries(c.methods))vm[k]=(...a)=>v.apply(vm,a)
  for(const[k,v]of Object.entries(c.computed))Object.defineProperty(vm,k,{get:()=>v.call(vm)})
  return {vm,calls,store}
}
test('月份与姓名使用已查询条件，翻页和导出不采用未搜索输入',async()=>{
  const p=page();p.vm.draft={payMonth:'2026-10',collegeId:'3',keyword:'已查学生',status:'APPROVED'};await p.vm.search();p.vm.draft.keyword='未查询';await p.vm.exportRows();await p.vm.changePage(2)
  assert.equal(p.calls.find(x=>x[0].includes('/export'))[1].params.keyword,'已查学生')
  const last=p.calls.filter(x=>x[0]==='/internship/payroll').at(-1)[1].params;assert.equal(last.payMonth,'2026-10');assert.equal(last.page,2);assert.equal(last.keyword,'已查学生')
})
test('导出期间切换批次，不产生旧学校下载链接',async()=>{
  let resolve;const p=page({request:async(path)=>path.includes('export')?new Promise(r=>resolve=r):path.includes('org-tree')?{tree:[]}:{items:[],total:0}})
  await p.vm.load();const pending=p.vm.exportRows();p.store.selectedBatchId='2747';resolve({filename:'旧工资.xlsx'});await pending;assert.equal(p.vm.exportFile,null)
})
test('读取失败、无权或没有成功加载，禁止导出旧结果',async()=>{
  const p=page();await p.vm.exportRows();assert.equal(p.calls.length,0);await p.vm.load();p.vm.ctx.allowed=false;await p.vm.exportRows();assert.equal(p.calls.filter(x=>x[0].includes('/export')).length,0)
  const failed=page({request:async()=>{throw Error('offline')}});await failed.vm.load();assert.equal(failed.vm.loaded,false);assert.equal(failed.vm.error,'读取失败');await failed.vm.exportRows();assert.equal(failed.vm.exportFile,null)
})
test('刷新恢复合法查询，其他批次旧条件不沿用',()=>{
  const p=page();p.vm.$route.query={batchId:'2746',payMonth:'2026-09',keyword:'零工资',status:'RETURNED',page:'2'};p.vm.restore();assert.equal(p.vm.page,2);assert.equal(p.vm.applied.payMonth,'2026-09');p.store.selectedBatchId='2747';p.vm.restore();assert.equal(p.vm.applied.keyword,'');assert.equal(p.vm.page,1)
})
