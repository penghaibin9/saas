import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'

async function renderPage(name, state) {
  const source=fs.readFileSync(new URL(`../src/pages/student-internship/${name}/index.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...script.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,binding])=>binding.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  const deps={currentSessionGeneration:()=>0,normalizeMobileVolunteerGroup:()=>({slots:[],status:'DRAFT'}),normalizeMobileCatalogQuery:x=>x,normalizeMobileMaterialPreview:()=>({}),formatDateTime:x=>x,formatMobileDeadline:x=>x,canEditMobileVolunteers:row=>row.status==='DRAFT',mobileConditionRows:()=>[],mobileCompanyLocation:()=>''}
  const component=new Function(...names,script.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...names.map(key=>deps[key]||{}))
  const vm={...component.data(),...state}
  for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const[key,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const shell={setup:(_,{slots})=>()=>h('section',slots.default?.())}
  const components={MobileNavBar:{props:['title','subtitle'],setup:(props,{slots})=>()=>h('header',[props.title,props.subtitle,slots.left?.(),slots.right?.()])},MobileGlobalState:{props:['state','title','description'],setup:(props,{slots})=>()=>props.state==='ready'?h('main',slots.default?.()):h('article',[props.title,props.description])},MobileInlineAlert:{props:['title','description'],setup:props=>()=>h('p',[props.title,props.description])},MobileStatusTag:{props:['label'],setup:props=>()=>h('span',props.label)},MobileSafeAreaBar:shell}
  return {vm,html:await renderToString(createSSRApp({components,setup:()=>vm,render:compile(template,{isCustomElement:tag=>['view','text','picker','image','checkbox','checkbox-group'].includes(tag)})}))}
}

test('知情空态不讲实现机制，有任务保留正文阅读和监护人进度',async()=>{
  const empty=await renderPage('consent',{state:'ready',items:[]})
  assert.ok(empty.html.includes('暂无知情确认任务'));assert.ok(!empty.html.includes('令牌')&&!empty.html.includes('学生确认必须阅读正文'))
  const populated=await renderPage('consent',{state:'ready',items:[{id:'1',consentType:'STUDENT',status:'PENDING',contentVersion:'第2版'},{id:'2',consentType:'GUARDIAN',status:'PENDING',contactMasked:'138****0000'}]})
  assert.ok(populated.html.includes('请完整阅读正文后确认'));assert.ok(populated.html.includes('等待已绑定监护人完成确认'));assert.ok(populated.html.includes('138****0000'))
})

test('安全教育空态只说未配置，有课程保留全部必修和新版重学要求',async()=>{
  const empty=await renderPage('safety',{state:'ready',courses:[],batchId:'18'})
  assert.ok(empty.html.includes('暂无安全教育课程'));assert.ok(!empty.html.includes('旧版本课程'))
  const shown=await renderPage('safety',{state:'ready',batchId:'18',courses:[{id:'1',title:'合成课程',courseVersion:'2',requiredMinutes:30,studiedMinutes:0,remainingAttempts:0,completionStatus:'FAILED',requireCommitment:true,commitmentConfirmed:false}]})
  assert.ok(shown.html.includes('完成全部必修课程'));assert.ok(shown.html.includes('版本更新后需重新学习'));assert.ok(shown.html.includes('剩余尝试 0'));assert.ok(shown.html.includes('待确认'))
})

test('待学课程先于已通过课程，组内保留原顺序及原完成事实',async()=>{
  const courses=[{id:'passed',title:'已办课程',completionStatus:'PASSED'},{id:'new',title:'待学课程',completionStatus:'NOT_STARTED'},{id:'review',title:'待审课程',completionStatus:'PENDING_REVIEW'}]
  const before=JSON.stringify(courses),p=await renderPage('safety',{state:'ready',courses,batchId:'18'})
  assert.deepEqual(p.vm.orderedCourses.map(x=>x.id),['new','review','passed']);assert.equal(JSON.stringify(courses),before)
  assert.ok(p.html.indexOf('待学课程')<p.html.indexOf('已办课程'))
})

test('未开放选岗只显示真实状态和下一步，特殊原因不被概括替换',async()=>{
  const original='当前批次暂未开放选岗。可先查看实习准备事项，开放后再来选择岗位。'
  const waiting=await renderPage('enterprises',{mode:'list',contextState:'ready',context:{catalogState:'NO_OPEN_CAMPAIGN',blockReason:original}})
  assert.ok(waiting.html.includes('等待学校开放选岗'));assert.ok(waiting.html.includes('查看实习准备'));assert.ok(!waiting.html.includes('选岗前准备'));assert.ok(!waiting.html.includes(original))
  const specific=await renderPage('enterprises',{mode:'list',contextState:'ready',context:{catalogState:'NO_OPEN_CAMPAIGN',blockReason:'学校正在核对本批次企业准入'}})
  assert.ok(specific.html.includes('学校正在核对本批次企业准入'));assert.equal(specific.vm.catalogReady,false)
})

test('空消息不显示无效分页，有内容仍明确已读与本人确认的区别',async()=>{
  const empty=await renderPage('messages',{state:'ready',items:[],total:0,page:1,hasMore:false})
  assert.ok(empty.html.includes('暂无消息通知'));assert.ok(!empty.html.includes('上一页')&&!empty.html.includes('下一页'));assert.ok(!empty.html.includes('已读不代表业务办结'))
  const shown=await renderPage('messages',{state:'ready',items:[{messageId:'1',title:'合成通知',readStatus:'UNREAD'}],total:21,page:1,hasMore:true,detail:{messageId:'1',title:'合成通知',readStatus:'UNREAD',requireAck:true}})
  assert.ok(shown.html.includes('已读不代表业务办结'));assert.ok(shown.html.includes('本人确认'));assert.ok(shown.html.includes('上一页')&&shown.html.includes('下一页'))
  assert.equal(shown.vm.detail.readStatus,'UNREAD')
})
