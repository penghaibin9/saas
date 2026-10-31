import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { captureWorkContext, restoreWorkContext } from '../src/modules/internship/composables/workContext.js'
import { isConflict, captureConflict } from '../src/modules/internship/composables/conflictGuard.js'

function reportPage(filename, api={}, permissions=true) {
  const source=fs.readFileSync(new URL('../src/modules/internship/views/'+filename,import.meta.url),'utf8')
  let script=source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const names=[...script.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)]
    .flatMap(([,bindings])=>bindings.replace(/[{}]/g,'').split(',').map(name=>name.trim()))
  script=script.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  let generation=0
  const batch={selectedBatchId:'18'},deps={internshipApi:api,useInternshipBatchStore:()=>batch,
    captureWorkContext,restoreWorkContext,isConflict,captureConflict,currentSessionGeneration:()=>generation,canCode:(_ctx,code)=>permissions===true || permissions.includes(code),formatDateTime:value=>value,emptyConflict:()=>({}),toast:{error(){},success(){}}}
  const component=new Function(...names,script)(...names.map(name=>deps[name]??{}))
  const vm={...component.data(),ctx:{currentRole:{},dataScope:{}},$route:{path:'/admin/internship/reports',query:{},params:{}},$refs:{}}
  for(const [name,fn] of Object.entries(component.methods))vm[name]=fn.bind(vm)
  for(const [name,fn] of Object.entries(component.computed))Object.defineProperty(vm,name,{get:fn.bind(vm)})
  return {vm,component,switchAccount:()=>generation++,batch}
}

test('只读计划无计划时显示空态，有计划时显示原正文与附件入口，不出现禁用录入表单',async()=>{
  const p=reportPage('InternshipPlanView.vue',{},['internship.plan.view']),vm=p.vm
  vm.loading=false
  const source=fs.readFileSync(new URL('../src/modules/internship/views/InternshipPlanView.vue',import.meta.url),'utf8'),template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const components=Object.fromEntries(Object.keys(p.component.components).map(name=>[name,{props:['label'],setup:(props,{slots})=>()=>h('section',[props.label,slots.default?.()])}]))
  for(const [name,tag] of [['AppTextInput','input'],['AppTextarea','textarea'],['AppSelect','select']])components[name]={render:()=>h(tag)}
  const render=()=>renderToString(createSSRApp({components,setup:()=>Object.defineProperties({},Object.getOwnPropertyDescriptors(vm)),render:compile(template)}))
  let html=await render();assert.ok(html.includes('本批次尚未发布实习计划'));assert.doesNotMatch(html,/<input|<textarea/)
  vm.plan={status:'PUBLISHED',version:2};vm.form.title='原计划标题';vm.form.content='原计划正文必须保留';vm.form.internshipType='POST'
  html=await render();assert.ok(html.includes('原计划正文必须保留'));assert.ok(html.includes('岗位实习'));assert.ok(html.includes('计划附件'));assert.doesNotMatch(html,/<input|<textarea/)
})

test('报告冲突回读保留中文状态，缺少中文说明时不显示内部状态',async()=>{
  for(const filename of ['WeeklyReportDetailView.vue','ProcessReportDetailView.vue']){
    for(const label of ['', '学校已复核']){
      const conflict=async()=>({code:409001,message:'记录已变化'})
      const {vm}=reportPage(filename,{reviewWeeklyReport:conflict,reviewProcessReport:conflict})
      vm.$route.params.id='42';vm.loading=false;vm.comment='请补充真实工作记录'
      vm.detail={id:'42',batchId:'18',status:'PENDING_REVIEW',version:1,reportType:'DAILY'}
      vm.load=async()=>{vm.detail={...vm.detail,status:'UNKNOWN_INTERNAL_STATE',statusLabel:label}}
      await vm.submit('RETURN')
      assert.equal(vm.conflict.latest.find(item=>item.label==='最新状态').value,label||'状态待核实')
    }
  }
})

test('应交总览真实组件按批阅权限禁用四类催交并说明原因，方法同样拦截只读请求', async () => {
  const source=fs.readFileSync(new URL('../src/modules/internship/views/WeeklyReportListView.vue',import.meta.url),'utf8')
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const permissionSource=fs.readFileSync(new URL('../src/components/common/AppPermissionButton.vue',import.meta.url),'utf8')
  const script=permissionSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]*\n/gm,'').replace('export default','return')
  const AppButton={props:['disabled','title'],setup:(props,{slots})=>()=>h('button',{disabled:props.disabled,title:props.title},slots.default?.())}
  const permission=new Function('AppButton',script)(AppButton)
  permission.render=compile(permissionSource.match(/<template>([\s\S]*?)<\/template>/)[1])
  const kinds=['daily','weekly','monthly','summary'],row={recordId:'9007199254740993001',studentName:'合成学生',studentNo:'0001',status:'MISSING',...Object.fromEntries(kinds.map(kind=>[kind,{missing:1,required:1,submitted:0,configured:true}]))}
  for(const allowed of [false,true]) {
    const calls=[],{vm}=reportPage('WeeklyReportListView.vue',{
      remindReportObligation:async(id,params)=>{calls.push({id,params});return {code:0,data:{queued:true}}},
      remindWeeklyReport:async()=>{calls.push('legacy');return {code:0,data:{reminded:true}}}
    },allowed?['internship.report.review']:['internship.report.view'])
    vm.obligationOpen=true;vm.loading=false;vm.obligationRows=[row]
    const shell={setup:(_props,{slots})=>()=>h('main',slots.default?.())}
    const table={setup:(_props,{slots})=>()=>h('div',kinds.map(kind=>slots['cell-'+kind]?.({row})))}
    const components=Object.fromEntries(['ActionReceipt','ErrorState','LoadingState','EmptyState','AppExportButton','ModuleSummaryStrip','AppStatusTag','AppRiskTag'].map(name=>[name,{render:()=>null}]))
    const descriptors=Object.fromEntries(Object.entries(Object.getOwnPropertyDescriptors(vm)).filter(([key])=>!key.startsWith('$')))
    const app=createSSRApp({components:{...components,ModulePageShell:shell,DataTable:table,AppPermissionButton:permission},setup:()=>Object.defineProperties({},descriptors),render:compile(template)})
    const html=await renderToString(app)
    const buttons=[...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].filter(([, ,content])=>content.includes('催交'))
    assert.equal(buttons.length,4)
    assert.ok(buttons.every(([,attrs])=>allowed?!attrs.includes('disabled'):attrs.includes('disabled')))
    assert.equal(html.includes('当前账号无催交权限，请联系'),!allowed)
    for(const kind of kinds)await vm.remindMissing(row,kind)
    assert.equal(calls.length,allowed?4:0)
    if(!allowed){vm.remind({id:'legacy'});assert.equal(calls.length,0)}
    else assert.deepEqual(calls.map(call=>call.params.reportType),['DAILY','WEEKLY','MONTHLY','SUMMARY'])
    vm.obligationOpen=false;vm.filters.status='OVERDUE';vm.rows=[{id:'legacy',status:'OVERDUE'}]
    const legacyTable={setup:(_props,{slots})=>()=>h('div',slots['cell-actions']?.({row:vm.rows[0]}))}
    const legacy=createSSRApp({components:{...components,ModulePageShell:shell,DataTable:legacyTable,AppPermissionButton:permission},setup:()=>Object.defineProperties({},Object.fromEntries(Object.entries(Object.getOwnPropertyDescriptors(vm)).filter(([key])=>!key.startsWith('$')))),render:compile(template)})
    const legacyHtml=await renderToString(legacy)
    const legacyButtons=[...legacyHtml.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].filter(([, ,content])=>content.includes('催交'))
    assert.equal(legacyButtons.length,1)
    assert.equal(legacyButtons[0][1].includes('disabled'),!allowed)
  }
})

test('报告标量筛选可恢复，显式深链优先且翻页不被原地址拉回',t=>{
  const previous=globalThis.sessionStorage,storage=new Map()
  globalThis.sessionStorage={getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)}
  t.after(()=>{if(previous===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=previous})
  const first=reportPage('WeeklyReportListView.vue')
  first.vm.load=()=>{captureWorkContext(first.vm,['pagination.page','filters.keyword','filters.status','filterDraft.keyword'])}
  first.vm.workContextReady=true;first.vm.pagination.page=5;first.vm.filters.keyword='合成筛选';first.vm.filterDraft.keyword='合成筛选'
  first.vm.filters.status='APPROVED';first.vm.load()
  const restored=reportPage('WeeklyReportListView.vue');restored.vm.load=()=>{}
  restored.component.created.call(restored.vm)
  assert.equal(restored.vm.pagination.page,5);assert.equal(restored.vm.filters.keyword,'合成筛选');assert.equal(restored.vm.filters.status,'APPROVED')
  const deep=reportPage('WeeklyReportListView.vue');deep.vm.load=()=>{}
  deep.vm.$route.query={panel:'review',page:'2'}
  deep.component.watch['$route.query'].handler.call(deep.vm,deep.vm.$route.query);deep.component.created.call(deep.vm)
  assert.equal(deep.vm.pagination.page,2);assert.equal(deep.vm.filters.keyword,'')
  restored.vm.$router={replace:({query})=>{restored.vm.$route.query=query;restored.component.watch['$route.query'].handler.call(restored.vm,query)}}
  restored.vm.onPageChange(3);assert.equal(restored.vm.$route.query.page,'3');assert.equal(restored.vm.filters.keyword,'合成筛选')
  restored.vm.switchTab('APPROVED');assert.equal(restored.vm.pagination.page,3)
})

test('同批次同页签切换报告类型立即清旧选中，迟到周报不能进入月报批阅',async()=>{
  let finishWeekly,finishMonthly
  const writes=[],{vm,component}=reportPage('WeeklyReportListView.vue',{
    getWeeklyReports:()=>new Promise(resolve=>{finishWeekly=resolve}),
    getProcessReports:params=>{assert.equal(params.reportType,'MONTHLY');return new Promise(resolve=>{finishMonthly=resolve})},
    getReportObligations:async()=>({code:0,data:{summary:{}}}),
    reviewWeeklyReport:async(id,body)=>{writes.push(['weekly',id,body]);return {code:0}},
    reviewProcessReport:async(id,body)=>{writes.push(['monthly',id,body]);return {code:0}}
  })
  const old=vm.load()
  vm.rows=[{id:'1',version:3,status:'PENDING_REVIEW'}];vm.selected=['1'];vm.batchRating='5'
  vm.lastReceipt={statusLabel:'旧周报回执'};vm.batchFailures=[{id:'旧周报'}]
  vm.$route.query={type:'monthly',panel:'review',keyword:'合成',page:'2'}
  component.watch['$route.query'].handler.call(vm,vm.$route.query)
  assert.deepEqual(vm.rows,[]);assert.deepEqual(vm.selected,[]);assert.equal(vm.lastReceipt,null)
  assert.deepEqual(vm.batchFailures,[]);assert.equal(vm.filters.keyword,'合成');assert.equal(vm.pagination.page,2)
  await vm.batchApprove();assert.deepEqual(writes,[])
  finishWeekly({code:0,data:{list:[{id:'1',version:3,status:'PENDING_REVIEW'}],total:1}});await old
  assert.deepEqual(vm.rows,[])
  finishMonthly({code:0,data:{list:[{id:'1',version:9,status:'PENDING_REVIEW'}],total:1}})
  await new Promise(resolve=>setImmediate(resolve))
  vm.selected=['1'];vm.load=async()=>{};await vm.batchApprove()
  assert.equal(writes.length,1);assert.equal(writes[0][0],'monthly');assert.equal(writes[0][2].expectedVersion,9)
})

test('总结通过只提交百分分数，空输入拒绝而明确零分有效', async () => {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/ProcessReportDetailView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '').replace('export default', 'return')
  const names = [...source.matchAll(/^import ([\s\S]*?) from [^\n]+$/gm)].flatMap(([, value]) => value.replace(/[{}]/g, '').split(',').map(name => name.trim()))
  const calls = [], deps = { canCode: () => true, formatDateTime: value => value, emptyConflict: () => ({}), isConflict: () => false,
    toast: {success(){},error(){}}, internshipApi: {reviewProcessReport:async(id,body)=>{calls.push(body);return {code:0,data:{id,status:'APPROVED'}}}} }
  const component = new Function(...names, script)(...names.map(name => deps[name] ?? {}))
  const vm = {...component.data(),ctx:{},$route:{params:{id:'42'},query:{}},$refs:{}}
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(vm, name, {get:fn.bind(vm)})
  vm.loading=false;vm.detail={id:'42',batchId:'18',reportType:'SUMMARY',status:'PENDING_REVIEW',version:3};vm.load=async()=>{}
  await vm.submit('APPROVE');assert.equal(calls.length,0);assert.match(vm.formError,/必须填写/)
  vm.summaryScore='0';await vm.submit('APPROVE')
  assert.equal(calls[0].summaryScore,0);assert.equal(calls[0].ratingLevel,undefined);assert.equal(calls[0].expectedVersion,3)
})

test('报告详情重交后不显示旧提交的退回评价',()=>{
  for(const name of ['WeeklyReportDetailView.vue','ProcessReportDetailView.vue']) {
    const {vm}=reportPage(name)
    const versions=[{versionNo:2,review:null},{versionNo:1,review:{ratingLevel:1,comment:'原版退回'}}]
    vm.detail={immutableVersions:versions,versions}
    assert.equal(vm.latestReview,null)
    vm.detail.immutableVersions[0].review={summaryScore:0};assert.equal(vm.latestReview.summaryScore,0)
  }
})

test('批量评分拒绝空分、逐篇携带版本和明确0分并保留部分失败回执',async()=>{
  const calls=[],{vm}=reportPage('WeeklyReportListView.vue',{reviewProcessReport:async(id,body)=>{
    calls.push({id,body});return id==='2'?{code:409,message:'报告已变化'}:{code:0,data:{id}}
  }})
  vm.reportTypeKey='summary';vm.rows=[{id:'1',version:3,status:'PENDING_REVIEW'},{id:'2',version:4,status:'PENDING_REVIEW'}]
  vm.selected=['1','2'];vm.load=async()=>{}
  await vm.batchApprove();assert.equal(calls.length,0)
  vm.batchScore='0';await vm.batchApprove()
  assert.deepEqual(calls.map(it=>[it.id,it.body.summaryScore,it.body.expectedVersion]),[['1',0,3],['2',0,4]])
  assert.equal(calls[0].body.ratingLevel,undefined);assert.equal(vm.batchFailures.length,1)
  assert.equal(vm.lastReceipt.statusLabel,'部分评分完成')
})

test('批量五级评分采用同一已读版本，未知响应停止余下单据',async()=>{
  const calls=[],{vm}=reportPage('WeeklyReportListView.vue',{reviewWeeklyReport:async(id,body)=>{
    calls.push({id,body});throw new Error('网络中断')
  }})
  vm.rows=[{id:'1',version:3,status:'PENDING_REVIEW'},{id:'2',version:4,status:'PENDING_REVIEW'}]
  vm.selected=['1','2'];vm.batchRating='5';vm.load=async()=>{}
  await vm.batchApprove();assert.equal(calls.length,1);assert.equal(calls[0].body.ratingLevel,5)
  assert.equal(calls[0].body.expectedVersion,3);assert.equal(vm.batchFailures.length,2)
  assert.match(vm.batchFailures[1].message,/尚未发送/)
})

test('真实接口包装后的超时和连接失败仍停止下一篇，业务冲突可继续处理',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/internship/api/internship.api.js',import.meta.url),'utf8')
  const call=new Function(source.slice(source.indexOf('function ok('),source.indexOf('async function teacherReportCall('))+'\nreturn call')()
  const outcomes=[
    {error:Object.assign(new Error('请求超时'),{biz:true,code:503002,bizCode:'REQUEST_TIMEOUT'}),stop:true},
    {error:new Error('连接中断'),stop:true},
    {error:Object.assign(new Error('版本已变化'),{biz:true,code:409001,bizCode:'DATA_CONFLICT'}),stop:false},
    {error:Object.assign(new Error('版本已变化'),{biz:true,code:1,bizCode:'DATA_CONFLICT'}),stop:false}
  ]
  for(const {error,stop} of outcomes){
    const writes=[],{vm}=reportPage('WeeklyReportListView.vue',{reviewWeeklyReport:async id=>{
      writes.push(id);return call(async()=>{if(id==='1')throw error;return {id}})
    }})
    vm.rows=[{id:'1',version:3,status:'PENDING_REVIEW'},{id:'2',version:4,status:'PENDING_REVIEW'}]
    vm.selected=['1','2'];vm.batchRating='4';vm.load=async()=>{}
    await vm.batchApprove()
    assert.deepEqual(writes,stop?['1']:['1','2'])
    assert.equal(vm.batchFailures.length,stop?2:1)
    if(stop){assert.match(vm.batchFailures[0].message,/未确认/);assert.match(vm.batchFailures[1].message,/尚未发送/);assert.equal(vm.lastReceipt.statusLabel,'评分结果待核对')}
    else {assert.equal(vm.batchFailures[0].message,'版本已变化');assert.equal(vm.lastReceipt.statusLabel,'部分评分完成')}
  }
})

test('切换账号后迟到的报告与缺交统计不能回填',async()=>{
  let finish
  const {vm,switchAccount}=reportPage('WeeklyReportListView.vue',{getWeeklyReports:()=>new Promise(resolve=>{finish=resolve})})
  const pending=vm.load();switchAccount();finish({code:0,data:{list:[{id:'旧账号单据'}],total:1}});await pending
  assert.deepEqual(vm.rows,[]);assert.equal(vm.obligationSummary,null)
})

test('空日期不会变成非法日期查询，列表与导出复用同一筛选',async()=>{
  const calls=[],{vm}=reportPage('WeeklyReportListView.vue',{
    getWeeklyReports:async params=>{calls.push(params);return {code:0,data:{list:[],total:0}}},
    getReportObligations:async()=>({code:0,data:{summary:{}}}),exportWeeklyReports:params=>{calls.push(params)}
  })
  await vm.load();vm.exportFn();assert.equal(calls[0].startDate,undefined);assert.equal(calls[1].endDate,undefined)
  vm.filters.startDate='2026-10-03';vm.filters.endDate='2026-10-04';vm.filters.keyword='并行B-报告'
  await vm.load();vm.exportFn();assert.equal(calls[2].startDate,calls[3].startDate);assert.equal(calls[2].keyword,calls[3].keyword)
})

test('离开批量评分页后不继续发送下一篇，也不回填迟到列表',async()=>{
  let finishReview,finishList
  const writes=[],{vm,component}=reportPage('WeeklyReportListView.vue',{
    reviewWeeklyReport:id=>{writes.push(id);return writes.length === 1 ? new Promise(resolve=>{finishReview=resolve}) : Promise.resolve({code:0})},
    getWeeklyReports:()=>new Promise(resolve=>{finishList=resolve})
  })
  vm.rows=[{id:'1',version:3,status:'PENDING_REVIEW'},{id:'2',version:4,status:'PENDING_REVIEW'}]
  vm.selected=['1','2'];vm.batchRating='4'
  const load=vm.load;vm.load=async()=>{}
  const pending=vm.batchApprove()
  component.beforeUnmount?.call(vm)
  finishReview({code:0});await pending
  assert.deepEqual(writes,['1']);assert.equal(vm.lastReceipt,null)
  vm.load=load
  const reading=vm.load()
  component.beforeUnmount?.call(vm)
  finishList({code:0,data:{list:[{id:'迟到原单'}],total:1}});await reading
  assert.deepEqual(vm.rows,[])
})
