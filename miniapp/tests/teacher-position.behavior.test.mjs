import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { positionFilters, positionQuery, positionListUrl, positionDetailUrl, positionFacts } from '../src/modules/internshipPositionModel.js'

function mount(file, api={}, overrides={}) {
  const context={selectedBatchId:'22',batches:[{id:'22',name:'指导批次'}],load:async()=>{},can:()=>true,selectBatch(id){if(id!=='22')return false;this.selectedBatchId=id;return true},...overrides}
  const paths=[]
  const script=fs.readFileSync(new URL('../src/pages/teacher-internship/internship-positions/'+file+'.vue',import.meta.url),'utf8').split('<script>')[1].split('</script>')[0].replace(/^import.*$/gm,'').replace('export default','return')
  const options=new Function('useInternshipContextStore','teacherInternshipPositions','teacherInternshipPositionDetail','positionFilters','positionQuery','positionListUrl','positionDetailUrl','positionFacts','formatDateTime','go','uni',script)(()=>context,api.list,api.detail,positionFilters,positionQuery,positionListUrl,positionDetailUrl,positionFacts,String,path=>paths.push(path),{redirectTo:({url})=>paths.push(url)})
  const vm={...options.data()}
  for(const [key,fn] of Object.entries(options.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  for(const [key,fn] of Object.entries(options.methods))vm[key]=fn.bind(vm)
  return {vm,options,paths,context}
}
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}}
test('teacher position deep links whitelist filters and preserve list restoration',()=>{
  const parsed=positionQuery({batchId:'22',keyword:'  企业  ',status:'PENDING',page:'3',companyId:'foreign'})
  assert.deepEqual(parsed,{batchId:'22',keyword:'企业',status:'PENDING',page:3})
  assert.match(positionDetailUrl('7',parsed),/id=7&batchId=22&status=PENDING&keyword=.*&page=3/)
  assert.doesNotMatch(positionListUrl(parsed),/companyId|section/)
  assert.equal(positionQuery({page:-1,status:'unknown'}).page,1)
})
test('teacher position facts retain false and zero and use the canonical remuneration enums',()=>{
  const groups=positionFacts({nightShift:false,remunerationAmount:0,remunerationType:'ALLOWANCE',remunerationCycle:'ON_COMPLETION'})
  assert.equal(groups[0].items.find(item=>item[0]==='存在夜班')[1],'否')
  assert.equal(groups[0].items[0][1],'待补充')
  assert.equal(groups[1].items[0][1],'0 元')
  assert.equal(groups[1].items[1][1],'实习补贴')
  assert.match(groups[1].items[2][1],/结束后/)
})
test('list permission and requested batch gate all position requests',async()=>{
  let calls=0
  const denied=mount('index',{list:async()=>{calls++}},{can:()=>false})
  await denied.vm.load();assert.equal(denied.vm.state,'forbidden');assert.equal(calls,0)
  const foreign=mount('index',{list:async()=>{calls++}})
  foreign.options.onLoad.call(foreign.vm,{batchId:'99'});await foreign.vm.load()
  assert.match(foreign.vm.error,/指导学生范围/);assert.equal(calls,0)
})
test('list restores deep link filters and keeps them when entering a position',async()=>{
  let query
  const {vm,options,paths}=mount('index',{list:async(batchId,args)=>{query=args;return {batchId,items:[{id:'7'}],total:50}}})
  options.onLoad.call(vm,{batchId:'22',keyword:'设备',status:'PUBLISHED',page:'2'});await vm.load()
  assert.equal(query.page,2);assert.equal(query.keyword,'设备');vm.openPosition({id:'7'})
  assert.match(paths[0],/id=7&batchId=22&status=PUBLISHED/);assert.match(paths[0],/page=2/)
  vm.chooseFilter('DRAFT');assert.match(paths[1],/status=DRAFT/);assert.match(paths[1],/page=1/)
})
test('late list loads cannot overwrite the latest result',async()=>{
  const old=deferred();let calls=0
  const {vm}=mount('index',{list:()=>++calls===1?old.promise:Promise.resolve({batchId:'22',items:[{id:'new'}],total:1})})
  const pending=vm.load();await Promise.resolve();await vm.load();old.resolve({batchId:'22',items:[{id:'old'}],total:1});await pending
  assert.equal(vm.rows[0].id,'new')
})
test('detail rejects mismatched identity and stale responses after leaving',async()=>{
  const wrong=mount('detail',{detail:async()=>({id:'7',batchId:'99'})});wrong.options.onLoad.call(wrong.vm,{id:'7',batchId:'22'});await wrong.vm.load()
  assert.equal(wrong.vm.detail,null);assert.match(wrong.vm.error,/不属于当前批次/)
  const response=deferred(),pendingPage=mount('detail',{detail:()=>response.promise});pendingPage.options.onLoad.call(pendingPage.vm,{id:'7',batchId:'22',page:'3'})
  const pending=pendingPage.vm.load();await Promise.resolve();pendingPage.options.onUnload.call(pendingPage.vm);response.resolve({id:'7',batchId:'22'});await pending
  assert.equal(pendingPage.vm.detail,null);assert.match(pendingPage.vm.returnUrl,/page=3/)
})
