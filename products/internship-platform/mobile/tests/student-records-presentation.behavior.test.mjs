import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { selectionScope, selectionScopePath } from '../../shared/internshipSelectionScope.mjs'
import { formatDateTime } from '../src/utils/format.js'

function page(path, extra={}) {
  const source=fs.readFileSync(new URL(`../src/pages/student-internship/${path}.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm,'').replace('export default','return')
  const deps={currentSessionGeneration:()=>0,formatDateTime,selectionScope,selectionScopePath,internshipSelectionApi:{forScope:()=>({})},studentApi:{},getDeviceDigest:()=>'',toast:()=>{},normalizeError:()=>({pageState:'error',text:'读取失败'}),setInterval:()=>1,clearInterval:()=>{},...extra}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm={...component.data(),$refs:{}}
  for(const [name,fn]of Object.entries(component.methods||{}))vm[name]=fn.bind(vm)
  for(const [name,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  vm.state='ready'
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const components={MobileNavBar:{props:['title','fallbackUrl'],setup:p=>()=>h('nav',{'data-return':p.fallbackUrl},p.title)},MobilePrivacyGate:{render:()=>null},
    MobileGlobalState:{props:['state','title','description'],setup:(p,{slots})=>()=>p.state==='ready'?h('div',slots.default?.()):h('section',[p.title,p.description,slots.actions?.()])},
    MobileInlineAlert:{props:['title','description'],setup:p=>()=>h('p',[p.title,p.description])},MobileStatusTag:{props:['status','label'],setup:p=>()=>h('span',p.label||p.status)},
    MobileSafeAreaBar:{setup:(_,{slots})=>()=>h('footer',slots.default?.())}}
  const render=compile(template,{isCustomElement:tag=>['view','text','picker','image','navigator'].includes(tag)})
  return {vm,component,html:()=>renderToString(createSSRApp({components,render:()=>render(vm,[])})),tree:async()=>{const events=compile(template,{isCustomElement:tag=>['view','text','picker','image','navigator'].includes(tag)||/^[A-Z]/.test(tag)});let tree;await renderToString(createSSRApp({render:()=>{tree=events(vm,[]);return tree}}));return tree}}
}
function nodes(node,predicate,result=[]) {if(!node||typeof node!=='object')return result;if(predicate(node))result.push(node);for(const child of Array.isArray(node.children)?node.children:[])nodes(child,predicate,result);return result}

test('档案呈现保留原招聘季资料草稿与必需提示，学校材料不开放编辑',async()=>{
  const p=page('profile/index');p.vm.scope={batchId:'18',campaignId:'7',recordId:'18'};p.vm.accept({profile:{profileVersion:8,selfIntro:'原自我介绍',strengths:'原优势',skillTags:['测试'],expectedLocations:['原地点'],availableFrom:'2026-10-07'},schoolFacts:{realName:'合成学生',studentNo:'00001'},items:[{id:'3',title:'学校提供材料',sourceType:'SCHOOL',itemType:'PRACTICE',description:'原学校正文',fileIds:['11']}]});p.vm.completeness={percent:100,blockers:['profile.selfIntro']}
  let html=await p.html();for(const text of ['原自我介绍','原优势','00001','100%','请填写自我介绍','原学校正文','查看附件 1','学校提供的记录只读','历史投递材料不变'])assert.ok(html.includes(text),text)
  assert.match(html,/batchId=18&amp;campaignId=7&amp;recordId=18/);assert.equal(p.vm.version,8)
  p.vm.editItem(p.vm.items[0]);assert.equal(p.vm.itemDraft,null)
  p.vm.draft.selfIntro='尚未保存的新介绍';html=await p.html();assert.match(html,/尚未保存的新介绍/);assert.match(html,/请先保存上方介绍/)
  const preview=nodes(await p.tree(),n=>n.type==='button'&&n.props?.onClick===p.vm.loadPreview)[0];assert.equal(preview.props.disabled,true)
})

test('知情呈现保持完整学校正文原版本拒绝原因及阅读后才能确认',async()=>{
  const p=page('consent/detail');p.vm.id='3';p.vm.batchId='18';const body='学校完整正文第一段。\n第二段包含全部告知与责任，不得改写。';p.vm.detail={id:'3',status:'VALID',version:8,contentVersion:'学校修订版',contentSnapshot:body,confirmedAt:'2026-10-13T03:10:00Z'}
  let html=await p.html();assert.ok(html.includes(body));assert.match(html,/学校修订版/);assert.ok(html.includes(formatDateTime(p.vm.detail.confirmedAt)));assert.doesNotMatch(html,/本人已阅读并确认|确认后记录本人账号/)
  p.vm.detail={...p.vm.detail,status:'PENDING',confirmedAt:null};p.vm.viewed=false;let buttons=nodes(await p.tree(),n=>n.type==='button'&&(n.props?.onClick===p.vm.confirm||n.props?.onClick===p.vm.reject));assert.equal(buttons.length,2);assert.ok(buttons.every(n=>n.props.disabled))
  p.vm.viewed=true;buttons=nodes(await p.tree(),n=>n.type==='button'&&(n.props?.onClick===p.vm.confirm||n.props?.onClick===p.vm.reject));assert.ok(buttons.every(n=>!n.props.disabled));assert.match(await p.html(),/至少5字/)
  p.vm.detail.status='REJECTED';p.vm.detail.rejectionReason='原拒绝理由完整保留';p.vm.actionError='任务或正文已变化，请核对';html=await p.html();assert.match(html,/原拒绝理由完整保留/);assert.match(html,/任务或正文已变化/);assert.ok(html.includes(body));assert.equal(p.vm.detail.version,8)
})

test('志愿结果呈现保留学校确认不等于上岗及原招聘季版本与退回补正',async()=>{
  const p=page('volunteer-result/index');p.vm.messageVersion='7';p.vm.result={id:'1',batchId:'18',campaignId:'7',recordId:'18',batchName:'原批次',campaignName:'原招聘季',version:8,submissionVersion:2,status:'APPROVED',items:[{id:'4',volunteerNo:1,status:'APPROVED',positionName:'原岗位',companyName:'原企业',applicationStatement:'原投递陈述'}]}
  let html=await p.html();for(const text of ['学校已确认岗位','还需完成协议、保险及上岗核验','通过学校要求后再上岗','原招聘季','志愿已有更新'])assert.ok(html.includes(text),text)
  assert.doesNotMatch(html,/第 8 版|原投递陈述/);nodes(await p.tree(),n=>n.type==='button'&&n.props?.['aria-expanded']===false)[0].props.onClick();html=await p.html();for(const text of ['第 8 版','2 次','原投递陈述'])assert.ok(html.includes(text),text)
  assert.match(html,/batchId=18&amp;campaignId=7&amp;recordId=18/);assert.doesNotMatch(html,/查看结果不会修改志愿/)
  p.vm.result.status='NEEDS_REVISION';p.vm.result.campaignStatus='OPEN';p.vm.result.revisionReason='学校原补正意见';html=await p.html();assert.match(html,/学校原补正意见/);assert.match(html,/进入原招聘季补正/)
  p.vm.result.campaignStatus='CLOSED';html=await p.html();assert.doesNotMatch(html,/进入原招聘季补正/);assert.match(html,/原招聘季当前未开放补正/)
})

test('课程缺编号恢复入口保留批次且不请求课程，不伪造学习成功或无限重试',async()=>{
  let reads=0;const p=page('safety/course',{studentApi:{getInternshipSafetyCourseDetail:async()=>{reads++;return {}}}});p.component.onLoad.call(p.vm,{batchId:'18'});await p.vm.load()
  const html=await p.html();assert.equal(reads,0);assert.equal(p.vm.course,null);assert.match(html,/尚未选择课程/);assert.match(html,/从安全教育选择课程/);assert.match(html,/pages\/student-internship\/safety\/index\?batchId=18/);assert.doesNotMatch(html,/重试|本课程已通过|提交学习结果/)
  p.component.onUnload.call(p.vm)
})
test('知情缺编号只提示正确返回列表，保留批次且不请求或确认正文',async()=>{
  let reads=0;const p=page('consent/detail',{studentApi:{getInternshipConsentDetail:async()=>{reads++;return {}}}});p.vm.batchId='18';await p.vm.load()
  const html=await p.html();assert.equal(reads,0);assert.match(html,/链接不完整/);assert.match(html,/返回知情确认/);assert.match(html,/consent\/index\?batchId=18/);assert.doesNotMatch(html,/本人已阅读并确认|请重试/)
})

test('课程正向模板保留正文承诺时长次数与教师审核限制，仅组件验证不算实页通过',async()=>{
  const p=page('safety/course');p.vm.id='5';p.vm.course={title:'合成安全课程',courseVersion:3,passingScore:60,requiredMinutes:30,remainingAttempts:2,requireCommitment:true,contentSnapshot:'学校完整课程正文不得删改',completion:{id:'8',version:4,status:'IN_PROGRESS',studiedMinutes:0,commitmentConfirmed:false}}
  let html=await p.html();for(const text of ['学校完整课程正文不得删改','本人已阅读本课程','剩余尝试','还需学习 30 分钟','确认安全承诺'])assert.ok(html.includes(text),text);assert.equal(p.vm.canSubmit,false)
  p.vm.course.completion.studiedMinutes=30;assert.equal(p.vm.canSubmit,false);p.vm.course.completion.commitmentConfirmed=true;assert.equal(p.vm.canSubmit,true)
  p.vm.course.completion.status='PENDING_REVIEW';html=await p.html();assert.match(html,/等待指导教师审核/);assert.doesNotMatch(html,/提交学习结果/)
  p.vm.course.completion.status='FAILED';p.vm.course.remainingAttempts=0;assert.equal(p.vm.noAttemptsLeft,true);assert.match(await p.html(),/已无剩余尝试次数/)
})
