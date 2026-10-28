import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {compile,createSSRApp,h} from 'vue'
import {renderToString} from '@vue/server-renderer'

function page(name,overrides={}){
  const source=fs.readFileSync(new URL(`../src/modules/internship/views/${name}.vue`,import.meta.url),'utf8')
  const body=source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...body.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,v])=>v.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  const scope=Object.fromEntries(names.map(k=>[k,{}])),store={selectedBatchId:'18'}
  Object.assign(scope,{emptyConflict:()=>({active:false}),useInternshipBatchStore:()=>store,canCode:()=>true,
    studentEvalApi:{getDetail:async()=>({code:0,data:{id:'1',batchId:'18',version:3,submitStatus:'SUBMITTED',reviewStatus:'PENDING',advisorOpinion:'已保存的指导教师意见',mentorOpinion:''}})},
    fileSdk:{metadata:async id=>({fileId:id,readyForBusiness:true,canPreview:true}),blob(){}},...overrides})
  const component=new Function(...names,body.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...names.map(k=>scope[k]))
  const vm={...component.data(),ctx:{},$route:{query:{}},$router:{},selectedId:'1'}
  for(const[k,v]of Object.entries(component.methods))vm[k]=(...a)=>v.apply(vm,a)
  for(const[k,v]of Object.entries(component.computed||{}))Object.defineProperty(vm,k,{get:()=>v.call(vm)})
  const shell={setup:(_,{slots})=>()=>h('div',slots.default?.())}
  const components=Object.fromEntries(Object.keys(component.components).map(k=>[k,shell]))
  components.AppTextarea={props:['modelValue'],setup:p=>()=>h('textarea',p.modelValue)}
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  return {vm,store,html:()=>renderToString(createSSRApp({components,setup:()=>vm,render:compile(template)}))}
}

test('已保存导师意见先只读展示，明确修改后才打开编辑区',async()=>{
  const p=page('StudentEvalView');await p.vm.loadDetail('1');assert.equal(p.vm.commentEditing,false);assert.equal(p.vm.commentDirty,false)
  let html=await p.html();assert.match(html,/已保存的导师意见/);assert.match(html,/修改指导意见/);assert.doesNotMatch(html,/<textarea/)
  p.vm.commentEditing=true;html=await p.html();assert.match(html,/<textarea/);p.vm.cmtForm.advisorOpinion='未保存的新意见';assert.equal(p.vm.commentDirty,true)
})
test('未保存导师意见刷新保持原版本；空意见初次办理直接可填',async()=>{
  let original={id:'1',batchId:'18',version:3,submitStatus:'SUBMITTED',reviewStatus:'PENDING',advisorOpinion:'',mentorOpinion:''}
  const p=page('StudentEvalView',{studentEvalApi:{getDetail:async()=>({code:0,data:original})}});await p.vm.loadDetail('1');assert.equal(p.vm.commentEditing,true)
  p.vm.cmtForm.advisorOpinion='未保存的当前指导意见';original={...original,version:4};await p.vm.loadDetail('1');assert.equal(p.vm.cmtVersion,3);assert.equal(p.vm.cmtForm.advisorOpinion,'未保存的当前指导意见');assert.equal(p.vm.commentConflict.active,true)
})
test('评分依据先取得安全元信息，替换工作区后迟到回包不打开旧文件',async()=>{
  const p=page('ScoreView');await p.vm.previewEvidence('9');assert.equal(p.vm.evidencePreview.fileId,'9')
  let resolve;const late=page('ScoreView',{fileSdk:{metadata:()=>new Promise(r=>resolve=r),blob(){}}});const pending=late.vm.previewEvidence('9');late.vm.resetPanel();resolve({fileId:'9',readyForBusiness:true,canPreview:true});await pending;assert.equal(late.vm.evidencePreview,null)
})
test('不安全或无预览权限的评分依据不能显示',async()=>{
  for(const meta of [{fileId:'9',readyForBusiness:false,canPreview:true},{fileId:'9',readyForBusiness:true,canPreview:false}]){const p=page('ScoreView',{fileSdk:{metadata:async()=>meta,blob(){}}});await p.vm.previewEvidence('9');assert.equal(p.vm.evidencePreview,null);assert.ok(p.vm.panelError)}
})
test('复核发布动作只消费后端授权列表，缺失或明确拒绝不能显示为可用',()=>{
  const p=page('ScoreView'),row={version:0,status:'PENDING_REVIEW',incomplete:false};assert.equal(!!p.vm.canAct(row,'review'),false);row.allowedActions=[];assert.equal(p.vm.canAct(row,'review'),false);row.allowedActions=['review'];assert.equal(p.vm.canAct(row,'review'),true);row.allowedActions=['publish'];assert.equal(p.vm.canAct(row,'review'),false)
})
