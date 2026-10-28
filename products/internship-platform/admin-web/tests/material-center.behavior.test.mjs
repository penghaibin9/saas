import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

function page(api = {}, query = {}) {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipMaterialCenterView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
  const store = { selectedBatchId: '9007199254740993001', withBatchQuery: value => value }
  const deps = { ModulePageShell:{}, AppButton:{}, AppSearchBox:{}, AppStatusTag:{}, AppPagination:{}, AppOrgCascader:{}, AppDocumentViewer:{}, SecureFileList:{},
    internshipMaterialCenterApi:{createPreviewProvider:()=>({}),...api}, useInternshipBatchStore:()=>store, canCode:()=>true, normalizeUiError, toast:{warning(){}} }
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const routes = [], vm = { ...component.data(), ctx:{}, $route:{query}, $router:{push:value=>routes.push(value),replace:value=>routes.push(value)} }
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = (...args) => fn.apply(vm,args)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  return {vm,routes,store}
}
test('材料类型、审核与组织筛选同请求、同深链保留大编号', async()=>{
  const reads=[],id='9007199254740993999'
  const p=page({list:async params=>{reads.push(params);return {items:[],total:0}}}, {category:'CUSTOM_MATERIAL',reviewStatus:'RETURNED',collegeId:'11',majorId:'12',classId:id})
  p.vm.restoreQuery();await p.vm.load();p.vm.reload()
  assert.equal(reads[0].category,'CUSTOM_MATERIAL');assert.equal(reads[0].reviewStatus,'RETURNED')
  assert.equal(reads[0].classId,id);assert.equal(p.routes[0].query.classId,id)
  assert.equal(p.vm.materialTypes.find(item=>item.value==='CUSTOM_MATERIAL').label,'自定义收件材料')
})
test('未知审核值与程序异常始终转换为中文业务说明', async()=>{
  const p=page({list:async()=>{throw Error('SQLSTATE database_secret')}})
  assert.equal(p.vm.reviewStatusLabel('INTERNAL_ENUM'),'审核状态待确认')
  await p.vm.load();assert.equal(p.vm.error,'材料列表加载失败')
  p.vm.previewError(Error('stack trace PRIVATE_KEY'));assert.equal(p.vm.operationError,'站内预览失败，请刷新材料状态后重试')
})
test('迟到的列表响应不能带回另一批次的材料', async()=>{
  let finish;const delayed=new Promise(resolve=>{finish=resolve})
  const p=page({list:()=>delayed});const work=p.vm.load();p.store.selectedBatchId='other'
  finish({items:[{studentName:'旧学校学生'}],total:1});await work
  assert.deepEqual(p.vm.rows,[]);assert.equal(p.vm.total,0)
})
