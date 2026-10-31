import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {normalizeUiError} from '../src/utils/presentationSafety.js'
const pending=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
function page(panel=false,api={}){
  const source=fs.readFileSync(new URL(panel?'../src/modules/internship/components/ProcessAnalyticsPanel.vue':'../src/modules/internship/views/StatsView.vue',import.meta.url),'utf8')
  const body=source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...body.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,v])=>v.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  const store={selectedBatchId:'18',withBatchQuery:q=>q},scope=Object.fromEntries(names.map(x=>[x,{}]))
  Object.assign(scope,{useInternshipBatchStore:()=>store,canCode:()=>true,statsApi:api})
  const component=new Function(...names,body.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...names.map(x=>scope[x]))
  const vm={...component.data(),initialState:{},batchId:'18',filters:{college:'已应用学院'},canExport:true,ctx:{},$route:{query:{college:'已应用学院'}},$router:{}}
  for(const[k,v]of Object.entries(component.methods))vm[k]=(...a)=>v.apply(vm,a)
  for(const[k,v]of Object.entries(component.computed))Object.defineProperty(vm,k,{get:()=>v.call(vm)})
  return {vm,store,component}
}
test('总览导出使用已应用范围，尚未应用的筛选草稿不改变导出',async()=>{
  let sent;const {vm}=page(false,{exportStats:async q=>{sent=q;return {code:0,data:{}}}})
  vm.dim.college='未应用的学院';await vm.exportFn();assert.equal(sent.college,'已应用学院')
})
test('绩效查询继承院系范围，屏幕与自选导出列保持同一顺序',async()=>{
  let sent;const {vm}=page(true,{exportProcessAnalytics:async q=>{sent=q;return {code:0}}})
  vm.availableColumns=[{key:'name',title:'姓名'},{key:'employeeNo',title:'工号'}];vm.selectedKeys=['employeeNo','name']
  await vm.exportFn();assert.equal(sent.college,'已应用学院');assert.equal(sent.columns,'name,employeeNo')
})
test('范围切换丢弃迟到的绩效查询与导出，不回填上一学校数据',async()=>{
  const wait=pending();const {vm}=page(true,{getProcessAnalytics:()=>wait.promise})
  const work=vm.reload();vm.batchId='19';wait.resolve({code:0,data:{items:[{name:'旧学校教师'}],total:1}});await work;assert.deepEqual(vm.items,[])
  const dl=pending();const p=page(true,{exportProcessAnalytics:()=>dl.promise});p.vm.selectedKeys=['name'];const exporting=p.vm.exportFn();p.vm.filters={college:'另一学院'};dl.resolve({code:0,data:{contentBase64:'file'}});assert.equal((await exporting).code,1)
})
test('查询失败清空旧行并显示中文错误；时间切换从第一页查询',async()=>{
  let sent;const {vm}=page(true,{getProcessAnalytics:async q=>{sent=q;return {code:1,message:'统计暂时无法读取'}}})
  vm.items=[{name:'旧结果'}];vm.page=9;await vm.resetQuery();assert.equal(sent.page,1);assert.equal(vm.items.length,0);assert.equal(vm.error,'统计暂时无法读取')
})
test('下钻区分涉及人数与计入数量，指标切换拒绝迟到明细',async()=>{
  const wait=pending();const {vm}=page(false,{getMetricDrilldown:()=>wait.promise})
  vm.$route.query.metric='reportTaskCompletionRate';vm.metrics=[{key:'reportTaskCompletionRate',drilldownAvailable:true}]
  const work=vm.loadDrill('denominator');vm.$route.query.metric='guidanceCoverRate';wait.resolve({code:0,data:{items:[{contribution:10}],total:1,totalValue:10}});await work;assert.equal(vm.drill.items.length,0)
})
test('接口异常不向学校页面透传内部状态、字段或数据库错误',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/internship/api/stats.api.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const statsApi','const statsApi')
  const api=new Function('request','normalizeUiError',source+'\nreturn statsApi')(()=>{throw {code:500,message:'SQLAlchemy currentVersionId NOT_CONNECTED'}},normalizeUiError)
  const res=await api.getOverview();assert.notEqual(res.code,0);assert.match(res.message,/[\u4e00-\u9fff]/);assert.doesNotMatch(res.message,/SQLAlchemy|currentVersionId|NOT_CONNECTED/)
})
test('总览刷新重建面板后恢复绩效分组、周期和自选列，跨身份重置仍清除选择',async()=>{
  let sent;const {vm,component}=page(true,{getProcessAnalytics:async q=>{sent=q;return {code:0,data:{availableColumns:[{key:'name',title:'姓名'}],items:[],total:0}}}})
  vm.initialState={groupBy:'ADVISOR',period:'MONTH',anchor:'2026-09-15',selectedKeys:['name'],page:1}
  component.mounted.call(vm);await new Promise(resolve=>setImmediate(resolve));assert.equal(sent.groupBy,'ADVISOR');assert.equal(sent.period,'MONTH');assert.deepEqual(vm.selectedKeys,['name'])
  const parent=page(false);parent.vm.processState={groupBy:'ADVISOR'};parent.vm.loadDims=()=>{};parent.vm.load=()=>{};parent.component.watch.ctx.handler.call(parent.vm);assert.deepEqual(parent.vm.processState,{})
})
