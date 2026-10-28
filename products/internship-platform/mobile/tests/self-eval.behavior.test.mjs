import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'

const source=fs.readFileSync(new URL('../src/pages/student-internship/self-eval/index.vue',import.meta.url),'utf8')
const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
async function page(data){
  const api={getInternship:async()=>({batchId:'2673',recordId:'722',statusText:'READY',destinationType:'SELF_ARRANGED'}),getInternshipSelfEval:async()=>data,getInternshipScoreAppeal:async()=>({})}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\r?\n/gm,'').replace('export default','return')
  const component=new Function('studentApi','normalizeError','toast','currentSessionGeneration','formatDateTime',script)(api,()=>({}),()=>{},()=>0,value=>value)
  const vm={...component.data()};for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const[key,fn]of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  await vm.load()
  const shell={setup:(_,{slots})=>()=>h('div',slots.default?.())}
  const components={MobileGlobalState:shell,MobileSafeAreaBar:shell,MobileNavBar:{props:['title'],setup:props=>()=>h('nav',props.title)},MobileInlineAlert:{render:()=>null},MobileStatusTag:{props:['label'],setup:props=>()=>h('span',props.label||'—')}}
  return{vm,html:await renderToString(createSSRApp({components,setup:()=>vm,render:compile(template,{isCustomElement:tag=>['view','text','picker'].includes(tag)})}))}
}

test('真实空对象合同表示尚无自评原单，不显示修改重交或空状态',async()=>{
  const {vm,html}=await page({})
  assert.equal(vm.evalData,null);assert.ok(html.includes('尚未提交'));assert.ok(html.includes('提交自评'));assert.ok(!html.includes('修改并重新提交'))
})

test('真实鉴定编号保留原版本和状态，退回重交与待审只读不变',async()=>{
  const original={id:'9007199254740993001',version:3,submitStatus:'SUBMITTED',reviewStatus:'RETURNED',reviewStatusLabel:'已退回',selfSummary:'原单正文'}
  const returned=await page(original)
  assert.equal(returned.vm.evalData,original);assert.equal(returned.vm.evalData.version,3);assert.ok(returned.html.includes('已退回'));assert.ok(returned.html.includes('修改并重新提交'))
  const pending=await page({...original,reviewStatus:'PENDING',reviewStatusLabel:'待审核'})
  assert.equal(pending.vm.readonly,true);assert.ok(!pending.html.includes('修改并重新提交'))
})

test('已审自评以正文呈现，保留原文且不挂载只读输入框的尺寸监听',async()=>{
  const original={id:'99',version:3,submitStatus:'SUBMITTED',reviewStatus:'APPROVED',selfSummary:'原实习总结保持完整',selfHarvest:'原收获保持完整'}
  const {vm,html}=await page(original)
  assert.equal(vm.readonly,true);assert.equal(vm.reviewExpanded,false)
  assert.match(html,/原实习总结保持完整/);assert.match(html,/原收获保持完整/)
  assert.doesNotMatch(html,/<textarea/)
  const returned=await page({...original,reviewStatus:'RETURNED'})
  assert.match(returned.html,/<textarea/);assert.equal(returned.vm.form.selfSummary,original.selfSummary)
})
