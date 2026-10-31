import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile,createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
const view=fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')

test('已发布成绩的结项卡片不再提示等待核算发布，归档后保持历史说明',async()=>{
  const start=view.indexOf('<section class="sp-card sp-completion"'),template=view.slice(start,view.indexOf('</section>',start)+10)
  for(const [status,score,expected] of [['ASSESSING',null,'等待学校核算'],['ASSESSING',{total:95.2},'学校已发布正式成绩'],['ARCHIVED',{total:95.2},'历史记录']]){
    const html=await renderToString(createSSRApp({setup:()=>({my:{status,score},selectTab(){}}),render:compile(template)}))
    assert.ok(html.includes(expected));if(score)assert.ok(!html.includes('等待学校核算并发布'))
  }
})
function page(overrides={}){
  let ctx={batchId:'18',internshipId:'21'},generation=1
  const ref=value=>({value}),calls=[]
  const original={id:'1',version:3,submitStatus:'SUBMITTED',reviewStatus:'RETURNED',selfSummary:'已保存自评正文和成果说明。',selfHarvest:'工作收获',selfProblem:'需要改进',enterpriseRating:4,positionRating:4}
  const deps={changeEpoch:1,evalSourceSequence:0,currentInternshipContext:()=>({...ctx}),currentSessionGeneration:()=>generation,
    changeCurrent:(epoch,g,context)=>g===generation&&context.batchId===ctx.batchId&&context.internshipId===ctx.internshipId,
    evalScope:ref(''),evalBaseline:ref(''),evalConflict:ref(false),selfEvalMeta:ref(null),appealMeta:ref(null),formalDocuments:ref([]),evalReceipt:ref(null),
    evalForm:{performance:'',reflection:'',problems:'',enterpriseRating:null,enterpriseFeedback:'',positionRating:null,positionFeedback:''},
    my:ref({hasData:true,batchId:'18',recordId:'21'}),sourceStates:{eval:{status:'data'}},rowsFrom:v=>Array.isArray(v)?v:v?.items||[],busy:ref(false),
    internshipCoreApi:{selfEval:async()=>({...original}),formalDocuments:async()=>[],submitSelfEval:async body=>{calls.push(body);return{id:'1',version:4}}},
    portalApi:{internshipScoreAppealStatus:async()=>({})},ui:{notify(){}},systemConfirm:async()=>true,loadTab:async()=>{},...overrides}
  const canEdit=view.split('\n').find(s=>s.startsWith('const evalCanEdit = ')).replace('const evalCanEdit = ','return ')
  const computed=fn=>({get value(){return fn()}})
  deps.evalCanEdit=new Function('computed','my','sourceStates','evalConflict','selfEvalMeta',canEdit)(computed,deps.my,deps.sourceStates,deps.evalConflict,deps.selfEvalMeta)
  const read=view.slice(view.indexOf('async function fetchTabSource('),view.indexOf('\nasync function loadTab('))
  const write=view.slice(view.indexOf('async function submitSelfEval('),view.indexOf('\nasync function submitAppeal('))
  const api=new Function(...Object.keys(deps),read+'\n'+write+'\nreturn {load:()=>fetchTabSource("eval"),submitSelfEval,adoptLatestEvaluation}')(...Object.values(deps))
  return{...api,deps,calls,change:()=>ctx={batchId:'19',internshipId:'22'},switchAccount:()=>generation++}
}
test('电脑自评回填原单正文与评分，已通过和审核中的原单只读',async()=>{
  const p=page();await p.load();assert.equal(p.deps.evalForm.performance,'已保存自评正文和成果说明。');assert.equal(p.deps.evalForm.enterpriseRating,4);assert.equal(p.deps.selfEvalMeta.value.version,3);assert.equal(p.deps.evalCanEdit.value,true)
  p.deps.selfEvalMeta.value.reviewStatus='APPROVED';assert.equal(p.deps.evalCanEdit.value,false);p.deps.selfEvalMeta.value.reviewStatus='PENDING';assert.equal(p.deps.evalCanEdit.value,false);p.deps.sourceStates.eval.status='error';assert.equal(p.deps.evalCanEdit.value,false)
})
test('电脑端刷新不覆盖草稿，不自动采用服务端新版本',async()=>{
  let latest={id:'1',version:3,submitStatus:'SUBMITTED',reviewStatus:'RETURNED',selfSummary:'已保存自评'}
  const p=page({internshipCoreApi:{selfEval:async()=>latest,formalDocuments:async()=>[]}});await p.load();p.deps.evalForm.performance='未提交的新正文必须保留';latest={...latest,version:4};await p.load();assert.equal(p.deps.evalForm.performance,'未提交的新正文必须保留');assert.equal(p.deps.selfEvalMeta.value.version,3);assert.equal(p.deps.evalConflict.value,true)
})
test('切批次或账号后迟到读取不回填其他学生自评',async()=>{
  for(const change of ['change','switchAccount']){let resolve;const p=page({internshipCoreApi:{selfEval:()=>new Promise(r=>resolve=r),formalDocuments:async()=>[]}});const pending=p.load();p[change]();resolve({id:'old',version:1,selfSummary:'旧身份正文'});await pending;assert.equal(p.deps.selfEvalMeta.value,null);assert.equal(p.deps.evalForm.performance,'')}
})
test('同一上下文两次读取，后返回的旧请求不能覆盖最新原单与新输入',async()=>{
  const pending=[];const p=page({internshipCoreApi:{selfEval:()=>new Promise(r=>pending.push(r)),formalDocuments:async()=>[]}})
  const first=p.load(),second=p.load();pending[1]({id:'1',version:4,selfSummary:'最新正文'});await second;p.deps.evalForm.performance='最新原单上继续填写';pending[0]({id:'1',version:3,selfSummary:'迟到旧正文'});await first;assert.equal(p.deps.selfEvalMeta.value.version,4);assert.equal(p.deps.evalForm.performance,'最新原单上继续填写')
})
test('电脑提交按打开版本，写冲突保留正文且不重复提交',async()=>{
  let writes=0;const p=page({internshipCoreApi:{selfEval:async()=>({id:'1',version:3,submitStatus:'SUBMITTED',reviewStatus:'RETURNED',selfSummary:'原正文'}),formalDocuments:async()=>[],submitSelfEval:async body=>{writes++;assert.equal(body.expectedVersion,3);throw{bizCode:'DATA_CONFLICT'}}}});await p.load();p.deps.evalForm.performance='这是尚未提交的完整实习自评正文，需要保留本次输入。';await p.submitSelfEval();await p.submitSelfEval();assert.equal(writes,1);assert.match(p.deps.evalForm.performance,/尚未提交/);assert.equal(p.deps.selfEvalMeta.value.version,3)
})
