import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeUiError } from '../src/utils/presentationSafety.js'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
const batch='9007199254740993101',record='9007199254740993102'
const row=(version=0)=>({name:'合成学生',studentNo:'SYN-001',sourceRegion:'湖南省 益阳市',nation:'汉族',gender:'男',version,complete:true,missingFields:[],todoCount:0,statusLabel:'已完善'})
const ok=data=>({code:0,data})
const deferred=()=>{let resolve;const promise=new Promise(a=>resolve=a);return {promise,resolve}}
function page(overrides={}){
  const api={getBasicInfo:async()=>ok(row()),saveBasicInfo:async()=>ok(row(1)),...overrides}
  const source=fs.readFileSync(new URL('../src/modules/internship/components/StudentBasicInfoEditor.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const names=['AppDrawer','AppInput','AppSelect','AppChinaRegionPicker','LoadingState','ErrorState','internStudentApi','normalizeUiError']
  const component=new Function(...names,script)(...names.map(name=>name==='internStudentApi'?api:name==='normalizeUiError'?()=>({userMessage:'操作未完成，请重试'}):{}))
  const emitted=[];const vm={...component.data(),visible:true,canManage:true,recordId:record,batchId:batch,$emit:(...args)=>emitted.push(args)}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  return {vm,api,emitted,component}
}

test('普通教师基础资料只读为正文，学校经办仍可编辑',async()=>{
  const p=page();await p.vm.load();p.vm.canManage=false
  const source=fs.readFileSync(new URL('../src/modules/internship/components/StudentBasicInfoEditor.vue',import.meta.url),'utf8')
  const template=source.slice(10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const components=Object.fromEntries(Object.keys(p.component.components).map(name=>[name,{setup:(_p,{slots})=>()=>h('section',slots.default?.())}]))
  for(const name of ['AppInput','AppSelect','AppChinaRegionPicker'])components[name]={render:()=>h('input')}
  const render=()=>renderToString(createSSRApp({components,setup:()=>Object.defineProperties({},Object.getOwnPropertyDescriptors(p.vm)),render:compile(template)}))
  let html=await render();for(const value of ['湖南省 益阳市','汉族','男','当前仅可查看'])assert.ok(html.includes(value))
  assert.doesNotMatch(html,/<input|保存基础资料/)
  p.vm.canManage=true;html=await render();assert.match(html,/<input/);assert.ok(html.includes('保存基础资料'))
})
test('学校编辑按原大编号和主档版本保存，成功回执保留',async()=>{
  let sent;const p=page({saveBasicInfo:async(...args)=>{sent=args;return ok(row(1))}});await p.vm.load();p.vm.form.sourceRegion='湖北省 武汉市';p.vm.markDirty();await p.vm.save()
  assert.deepEqual(sent,[record,batch,{sourceRegion:'湖北省 武汉市',nation:'汉族',gender:'男',expectedVersion:0}]);assert.equal(p.vm.receipt.version,1);assert.equal(p.vm.saving,false);assert.equal(p.emitted[0][0],'saved')
})
test('重新读取新版保留旧输入，核对后才允许继续保存',async()=>{
  const p=page();await p.vm.load();p.vm.form.nation='未提交民族资料';p.vm.markDirty();p.api.getBasicInfo=async()=>ok(row(2));await p.vm.load();assert.equal(p.vm.baseVersion,0);assert.equal(p.vm.form.nation,'未提交民族资料');assert.equal(p.vm.conflict,true);p.vm.acceptLatest();assert.equal(p.vm.baseVersion,2)
})
test('后台冲突与网络错误不冒充成功、不丢输入、不显示内部错误',async()=>{
  const p=page({saveBasicInfo:async()=>({code:1,bizCode:'DATA_CONFLICT',message:'raw_private_error'})});await p.vm.load();await p.vm.save();assert.ok(p.vm.formError.includes('输入已保留'));assert.equal(p.vm.baseVersion,0);assert.equal(p.vm.receipt,null)
  p.api.saveBasicInfo=async()=>{throw Error('raw_private_error')};await p.vm.save();assert.equal(p.vm.formError,'操作未完成，请重试')
})
test('重复点击只提交一次，切对象后迟到结果不能覆盖新资料',async()=>{
  const wait=deferred();let count=0;const p=page({saveBasicInfo:()=>{count++;return wait.promise}});await p.vm.load();const pending=p.vm.save();await p.vm.save();assert.equal(count,1);p.vm.recordId='9007199254740993112';p.vm.reset();p.vm.form.nation='新学生未提交资料';wait.resolve(ok(row(1)));await pending;assert.equal(p.vm.receipt,null);assert.equal(p.vm.form.nation,'新学生未提交资料')
})
test('关闭工作区后迟到加载不重新打开资料，无管理权限不发送写请求',async()=>{
  const wait=deferred();const p=page({getBasicInfo:()=>wait.promise});const pending=p.vm.load();p.vm.visible=false;p.vm.reset();wait.resolve(ok(row()));await pending;assert.equal(p.vm.profile,null)
  const q=page();await q.vm.load();q.vm.canManage=false;await q.vm.save();assert.equal(q.emitted.length,0)
})
test('公共预校验表把基础字段展示为中文业务名称',()=>{
  const source=fs.readFileSync(new URL('../src/components/common/excel/AppImportPreviewTable.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const component=new Function('safeBusinessMessage',script)((message,fallback)=>message||fallback)
  const vm={rows:[{studentNo:'SYN-001',...row()}],errors:[],previewSchema:[],previewFields:['studentNo','sourceRegion','nation','gender']}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  assert.deepEqual(vm.schema.map(field=>field.label),['学号','生源地','民族','性别'])
  const text=vm.previewRows[0].data;for(const value of ['SYN-001','湖南省 益阳市','汉族','男'])assert.ok(text.includes(value));assert.ok(!text.includes('sourceRegion'));assert.ok(!text.includes('gender'))
})

test('实际导入窗口回调从页面实例取得接口，模板预检确认和错误行均可调用',async()=>{
  const calls=[]
  const api={
    downloadBasicInfoTemplate:async()=>calls.push(['template']),
    uploadBasicInfoXlsx:async(...args)=>{calls.push(['upload',...args]);return ok({rows:[{studentNo:'SYN-001',expectedVersion:3}],validRows:1,invalidRows:0})},
    basicInfoImportConfirm:async(...args)=>{calls.push(['confirm',...args]);return ok({updated:1})},
    downloadBasicInfoErrors:async(...args)=>{calls.push(['errors',...args]);return ok({})}
  }
  const source=fs.readFileSync(new URL('../src/modules/internship/views/InternshipStudentListView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const names=['ModulePageShell','ModuleToolbar','DataTable','LoadingState','ErrorState','EmptyState','AppDrawer','AppSensitiveText','AppStatusTag','AppExportButton','AppTextarea','AppInternshipCandidateStudentPicker','AppInternshipAdvisorPicker','AppExcelImportDrawer','TableActionColumn','StudentBasicInfoEditor','ActionReceipt','STUDENT_STATUS','ELIGIBILITY_STATUS','DESTINATION_TYPE','internStudentApi','AdvancedFilter','RISK_LEVEL']
  const component=new Function(...names,script)(...names.map(name=>name==='internStudentApi'?api:name.endsWith('STATUS')||name==='DESTINATION_TYPE'?[]:{}))
  const scope={...component.data(),batchStore:{selectedBatchId:batch}}
  const expressions={}
  const template=source.slice(0,source.indexOf('<!-- 建档 -->'))
  for(const key of ['download-template','upload','confirm','download-errors']){
    const expression=template.match(new RegExp(':'+key+'-fn="([^"]+)"'))[1]
    expressions[key]=new Function('scope',`with(scope){return (${expression})}`)(scope)
  }
  const file={name:'合成基础资料.xlsx'}
  await expressions['download-template']()
  const preview=await expressions.upload(file)
  assert.equal(preview.data.validRows,1)
  const result=await expressions.confirm({rows:preview.data.rows})
  assert.equal(result.data.updated,1)
  await expressions['download-errors']({rows:preview.data.rows,errors:[]})
  assert.deepEqual(calls,[['template'],['upload',file,batch],['confirm',preview.data.rows,batch],['errors',preview.data.rows,[]]])
})

function importDrawer(overrides={}) {
  const source=fs.readFileSync(new URL('../src/components/common/excel/AppExcelImportDrawer.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const names=['AppButton','AccountImportBoundaryNotice','AppExcelUpload','AppImportPreviewTable','AppImportErrorSummary','toast','downloadXlsxFromApi','normalizeUiError']
  const toasts=[],emitted=[]
  const component=new Function(...names,script)(...names.map(name=>name==='toast'?{error:m=>toasts.push(m),info:m=>toasts.push(m)}:name==='downloadXlsxFromApi'?()=>{}:name==='normalizeUiError'?normalizeUiError:{}))
  const vm={...component.data(),visible:true,selectedFile:{name:'测试资料.xlsx'},uploadFn:async()=>ok({rows:[{studentNo:'SYN-01',expectedVersion:5}],total:1,validRows:1,invalidRows:0}),confirmFn:async()=>ok({updated:1}),$emit:(...args)=>emitted.push(args),...overrides}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  return {vm,component,toasts,emitted}
}

test('错误预检不提交，重新上传明确清除旧版本预检',async()=>{
  let calls=0
  const p=importDrawer({confirmFn:async()=>{calls++;return ok({updated:1})}})
  p.vm.pre={rows:[{studentNo:'SYN-01',expectedVersion:5}],total:2,validRows:1,invalidRows:1}
  await p.vm.doConfirm();assert.equal(calls,0)
  p.vm.restartUpload();assert.equal(p.vm.step,0);assert.equal(p.vm.selectedFile,null);assert.deepEqual(p.vm.pre.rows,[])
})

test('导入版本冲突保留原行与版本并显示可继续办理的说明',async()=>{
  const p=importDrawer({confirmFn:async()=>({code:1,bizCode:'DATA_CONFLICT',message:'raw_database_error'})})
  await p.vm.doPreValidate();const rows=p.vm.pre.rows;await p.vm.doConfirm()
  assert.equal(p.vm.step,1);assert.equal(p.vm.pre.rows,rows);assert.equal(rows[0].expectedVersion,5)
  assert.ok(p.vm.formError.includes('原表格内容已保留'));assert.ok(p.vm.formError.includes('重新上传'))
  assert.equal(p.emitted.length,0);assert.equal(p.vm.busy,false)
})

test('关闭再打开后旧预检结果不能覆盖新文件，也不能解锁新请求',async()=>{
  const wait=deferred();const p=importDrawer({uploadFn:()=>wait.promise})
  const pending=p.vm.doPreValidate();p.vm.close();p.vm.visible=false;p.component.watch.visible.call(p.vm,false)
  p.vm.visible=true;p.component.watch.visible.call(p.vm,true);p.vm.selectedFile={name:'新文件.xlsx'};p.vm.busy=true
  wait.resolve(ok({rows:[{studentNo:'OLD'}],validRows:1,invalidRows:0}));await pending
  assert.equal(p.vm.step,0);assert.equal(p.vm.selectedFile.name,'新文件.xlsx');assert.deepEqual(p.vm.pre.rows,[]);assert.equal(p.vm.busy,true)
})

test('确认提交期间只发一次请求，关闭后迟到成功不发导入回执',async()=>{
  const wait=deferred();let calls=0;const p=importDrawer({confirmFn:()=>{calls++;return wait.promise}})
  await p.vm.doPreValidate();const pending=p.vm.doConfirm();await p.vm.doConfirm();assert.equal(calls,1)
  p.vm.close();p.vm.visible=false;wait.resolve(ok({updated:1}));await pending
  assert.equal(p.vm.step,1);assert.equal(p.vm.result,null);assert.ok(!p.emitted.some(e=>e[0]==='imported'))
})

test('预检服务失败保留文件，显示中文错误并允许重试',async()=>{
  const p=importDrawer({uploadFn:async()=>{throw Error('TypeError: private_backend_field')}})
  await p.vm.doPreValidate();assert.equal(p.vm.step,0);assert.equal(p.vm.selectedFile.name,'测试资料.xlsx')
  assert.equal(p.vm.formError,'预校验失败');assert.equal(p.vm.busy,false);assert.equal(p.emitted.length,0)
})
