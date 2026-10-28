import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { normalizeError } from './request-module.mjs'
import { formatDateTime } from '../src/utils/format.js'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'

const source=fs.readFileSync(new URL('../src/pages/student-internship/help/index.vue',import.meta.url),'utf8')
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve}}
const support=(extra={})=>({sessionId:'7',status:'ACTIVE',unresolvedCount:0,remainingBeforeHuman:3,history:[{question:'周报怎么提交',answer:'请进入报告页面'}],awaitingFeedback:true,answerVersion:1,feedbackNotice:'',...extra})
function page(api={}) {
  let generation=0
  const requests=[],messages=[]
  const calls={getInternship:async()=>({batchId:'3',recordId:'5',historyMode:false}),getInternshipHelp:async()=>({items:[]}),getInternshipSupport:async()=>support(),...api}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]*\n/gm,'').replace('export default','return')
  const component=new Function('studentApi','toast','normalizeError','currentSessionGeneration','formatDateTime',script)(calls,text=>messages.push(text),normalizeError,()=>generation,formatDateTime)
  const vm={...component.data()};for(const [name,fn] of Object.entries(component.methods))vm[name]=fn.bind(vm)
  for(const [name,fn] of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  return {vm,component,requests,messages,switchAccount:()=>generation++}
}

test('咨询刷新恢复原回答待评价和答案版本，不能把历史不明确当作待评价',async()=>{
  const p=page();await p.vm.load();assert.equal(p.vm.awaitingFeedback,true);assert.equal(p.vm.support.answerVersion,1)
  const unknown=page({getInternshipSupport:async()=>support({awaitingFeedback:false,answerVersion:null,feedbackNotice:'历史回答状态未能确认，请重新提问。'})})
  await unknown.vm.load();assert.equal(unknown.vm.awaitingFeedback,false);assert.match(unknown.vm.support.feedbackNotice,/重新提问/)
})

test('咨询反馈携带原答案版本，重复点击只发送一次并消费权威计数',async()=>{
  const pending=deferred(),writes=[]
  const p=page({unresolvedInternshipSupport:async(id,body)=>{writes.push({id,body});await pending.promise;return support({awaitingFeedback:false,unresolvedCount:1})}})
  await p.vm.load();const run=p.vm.markUnresolved();await p.vm.markUnresolved()
  assert.equal(writes.length,1);assert.equal(writes[0].body.answerVersion,1);assert.equal(writes[0].body.internshipId,'5')
  pending.resolve();await run;assert.equal(p.vm.awaitingFeedback,false);assert.equal(p.vm.support.unresolvedCount,1)
})

test('咨询未知错误保留问题与输入并显示统一安全中文',async()=>{
  const p=page({getInternshipSupport:async()=>support({awaitingFeedback:false}),askInternshipSupport:async()=>{throw Error('SQL password C:/private')}})
  await p.vm.load();p.vm.question='原问题仍需解决';p.vm.form.content='人工说明保留';await p.vm.askSupport()
  assert.equal(p.vm.question,'原问题仍需解决');assert.equal(p.vm.form.content,'人工说明保留')
  assert.doesNotMatch(p.messages.join(' '),/SQL|password|private/);assert.ok(p.vm.errorMessage)
})

test('咨询离页与账号切换丢弃迟到读取和反馈，不清除新身份输入',async()=>{
  for(const action of ['hide','account']){
    const pending=deferred(),p=page({solveInternshipSupport:()=>pending.promise})
    await p.vm.load();const run=p.vm.markSolved()
    if(action==='hide')p.component.onHide.call(p.vm);else p.switchAccount()
    p.vm.form.content='新上下文输入';pending.resolve(support({status:'SOLVED',awaitingFeedback:false}));await run
    assert.equal(p.vm.form.content,'新上下文输入');assert.equal(p.vm.support.status,'ACTIVE');assert.equal(p.messages.length,0)
  }
})

test('咨询转人工回读同一求助编号，无批次和历史记录不得发新请求',async()=>{
  const reads=[],p=page({unresolvedInternshipSupport:async()=>support({status:'TRANSFERRED',awaitingFeedback:false,unresolvedCount:3,transferredRiskId:'9',transferred:true}),getInternshipHelp:async(...args)=>{reads.push(args);return {items:[{id:'9',status:'PENDING_HANDLE'}]}}})
  await p.vm.load();await p.vm.markUnresolved();assert.equal(p.vm.records[0].id,'9');assert.deepEqual(reads.at(-1),['3','5'])
  let writes=0;const empty=page({getInternship:async()=>({}),askInternshipSupport:async()=>writes++})
  await empty.vm.load();empty.vm.question='缺少批次';await empty.vm.askSupport();assert.equal(writes,0)
  const historic=page({getInternship:async()=>({batchId:'3',recordId:'5',historyMode:true}),reportInternshipHelp:async()=>writes++})
  await historic.vm.load();historic.vm.form.content='历史记录无法提交';await historic.vm.submitManual();assert.equal(writes,0)
})

test('咨询旧读取和人工提交迟到时不覆盖新批次或新身份草稿',async()=>{
  const pending=deferred(),p=page({getInternshipSupport:()=>pending.promise})
  const run=p.vm.load();await Promise.resolve();await Promise.resolve();p.component.onHide.call(p.vm)
  p.vm.support=support({sessionId:'new-context'});pending.resolve(support({sessionId:'old-context'}));await run
  assert.equal(p.vm.support.sessionId,'new-context')
  const write=deferred(),manual=page({reportInternshipHelp:()=>write.promise})
  await manual.vm.load();manual.vm.form.content='原说明内容';const submitting=manual.vm.submitManual();manual.switchAccount();manual.vm.form.content='新账号保留输入'
  write.resolve({id:'old',status:'PENDING_HANDLE'});await submitting
  assert.equal(manual.vm.form.content,'新账号保留输入');assert.equal(manual.vm.receipt,null)
})

test('咨询渲染中文状态兜底但保留用户原始问题正文',async()=>{
  const p=page();await p.vm.load();p.vm.receipt={id:'9',status:'INTERNAL_NEW_STATUS'}
  p.vm.support.history=[{question:'用户原文FAQ必须保留',answer:'原始回答正文'}]
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('<script>')).replace(/<\/template>\s*$/,'')
  const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:()=>true}).code)(Vue)
  const html=await renderToString(Vue.createSSRApp({render:()=>render(p.vm,[])}))
  assert.ok(html.includes('状态待确认'));assert.ok(html.includes('用户原文FAQ必须保留'));assert.doesNotMatch(html,/INTERNAL_NEW_STATUS/)
  assert.ok(html.includes('没解决'));assert.ok(html.includes('已解决'))
})

test('咨询系统更新时间按设备本地时间显示而不截断世界时时间',()=>{
  const previous=process.env.TZ;process.env.TZ='Asia/Shanghai'
  try{const p=page();assert.equal(p.vm.formatTime('2026-10-12T20:18:00Z'),'2026-10-13 04:18');assert.equal(p.vm.formatTime('invalid'),'—')}
  finally{if(previous===undefined)delete process.env.TZ;else process.env.TZ=previous}
})
