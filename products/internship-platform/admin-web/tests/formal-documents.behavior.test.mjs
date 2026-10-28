import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function page(overrides={}){
  const body=fs.readFileSync(new URL('../src/modules/internship/views/FormalDocumentWorkspaceView.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...body.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,v])=>v.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  const store={selectedBatchId:'18'},scope=Object.fromEntries(names.map(x=>[x,{}]))
  Object.assign(scope,{useInternshipBatchStore:()=>store,canCode:()=>true,toast:{success(){},error(){}},...overrides})
  const c=new Function(...names,body.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...names.map(x=>scope[x]))
  const vm={...c.data(),ctx:{},$route:{query:{batchId:'18',internshipId:'9'}}}
  for(const[k,v]of Object.entries(c.methods))vm[k]=(...a)=>v.apply(vm,a)
  for(const[k,v]of Object.entries(c.computed))Object.defineProperty(vm,k,{get:()=>v.call(vm)})
  return {vm,store}
}

test('全部文书共用一个不可生成原因时集中显示，独立缺项不合并',()=>{
  const {vm}=page()
  assert.equal(vm.sharedBlocker,'')
  vm.readinessItems=[{ready:false,reason:'档案已冻结'},{ready:false,reason:'档案已冻结'}]
  assert.equal(vm.sharedBlocker,'档案已冻结')
  vm.readinessItems[1]={ready:false,reason:'缺少成绩'};assert.equal(vm.sharedBlocker,'')
  vm.readinessItems[1]={ready:true,reason:'档案已冻结'};assert.equal(vm.sharedBlocker,'')
})
test('正式文书深链定位同批次原实习记录，批次不一致不自动加载',()=>{
  const {vm}=page();let loaded=0;vm.loadSelected=()=>loaded++;vm.applyRouteRecord()
  assert.equal(vm.internshipId,'9');assert.equal(loaded,1)
  vm.$route.query={batchId:'99',internshipId:'88'};vm.applyRouteRecord();assert.equal(loaded,1)
})
test('切换批次后旧文书回包不会回填到新工作区',async()=>{
  let resolve;const {vm,store}=page({internStudentApi:{getStudentDetail:()=>new Promise(r=>resolve=r)},formalDocumentApi:{readiness:async()=>({code:0,data:{items:[]}}),list:async()=>({code:0,data:[]})}})
  vm.internshipId='9';const pending=vm.loadSelected();store.selectedBatchId='19';resolve({code:0,data:{id:'9',batchId:'18'}});await pending
  assert.equal(vm.student,null);assert.deepEqual(vm.documents,[])
})
test('文书生成期间切换学生不自动下载前一个学生的文件',async()=>{
  let resolve;const {vm}=page({formalDocumentApi:{generate:()=>new Promise(r=>resolve=r)}});vm.internshipId='9';let downloads=0;vm.download=()=>downloads++
  const pending=vm.generate({documentType:'FINAL_ASSESSMENT',ready:true,upToDate:false});vm.internshipId='10';resolve({code:0,data:{id:'1'}});await pending
  assert.equal(downloads,0)
})
