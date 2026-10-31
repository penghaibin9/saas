import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const row=()=>({id:'9007199254740993101',date:'2026-10-04',studentName:'合成学生',
  photoFileId:'9007199254740993102',watermarkedFileId:'9007199254740993103',photoSha256:'original',watermarkedSha256:'derived'})
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}

test('异常列表适配为中文设备信号，机器值和原记录不被改写',async()=>{
  const rows=[{id:'1',deviceRisk:'not_available'},{id:'2',deviceRisk:'mock'},{id:'3',deviceRisk:'NEW_FLAG'}],original=JSON.stringify(rows)
  const source=fs.readFileSync(new URL('../src/modules/internship/api/attendance.api.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const attendanceApi','const attendanceApi').replace('export default attendanceApi','return attendanceApi')
  const api=new Function('request',source)(async()=>({items:rows,total:3,page:1,pageSize:20})),result=await api.getExceptions({batchId:'9007199254740993104'})
  assert.equal(result.code,0);assert.deepEqual(result.data.list.map(row=>row.deviceRiskLabel),['未提供可信检测','客户端报告模拟定位','设备信号待确认'])
  assert.equal(result.data.list[1].deviceRisk,'mock');assert.equal(JSON.stringify(rows),original)
})

function page(metadata,allowed=true,extras={}){
  let generation=1
  const store={selectedBatchId:'9007199254740993104'}
  const source=fs.readFileSync(new URL('../src/modules/internship/views/AttendanceView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*\r?\n/gm,'').replace('export default','return')
  const scope=Object.fromEntries(['ModulePageShell','DataTable','LoadingState','ErrorState','EmptyState','AppButton',
    'AppStatusTag','AppConfirmDialog','AppExportButton','AppPermissionButton','AppSearchBox','AppQuickFilterChips',
    'AppDescriptionList','AppAuditTrail','AppFilePreview','ModuleSummaryStrip','AppInlineAlert','ActionReceipt','FilePreviewer'].map(key=>[key,{}]))
  Object.assign(scope,{fileSdk:{metadata:metadata|| (async fileId=>({fileId,sha256:fileId===row().photoFileId?'original':'derived',canPreview:true})),blob(){}},
    emptyConflict:()=>({}),useInternshipBatchStore:()=>store,currentSessionGeneration:()=>generation,
    canCode:()=>allowed,normalizeUiError:()=>({userMessage:'照片暂不可查看'}),captureWorkContext(){},
    attendanceApi:{getCheckins:async()=>({code:0,data:{list:[],total:0}})}})
  Object.assign(scope,extras)
  const component=new Function(...Object.keys(scope),script)(...Object.values(scope))
  const vm={...component.data(),ctx:{ctxKey:'first'},$route:{path:'/admin/internship/attendance',query:{}},$router:{replace(){}}}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.rows=[row()]
  return {vm,component,store,switchAccount:()=>generation++}
}

test('原图和水印按正式大编号与校验值打开，关闭会清除预览',async()=>{
  const p=page();await p.vm.openPhoto(row(),true);assert.equal(p.vm.photoFile.fileId,row().photoFileId)
  await p.vm.openPhoto(row(),false);assert.equal(p.vm.photoFile.fileId,row().watermarkedFileId)
  p.vm.clearPhoto();assert.equal(p.vm.photoFile,null);assert.equal(p.vm.photoRecord,null)
})

test('照片编号、校验值变化或不可预览时显示中文错误',async()=>{
  for(const meta of [{fileId:'foreign',sha256:'derived',canPreview:true},
    {fileId:row().watermarkedFileId,sha256:'changed',canPreview:true},
    {fileId:row().watermarkedFileId,sha256:'derived',canPreview:false}]){
    const p=page(async()=>meta);await p.vm.openPhoto(row());assert.equal(p.vm.photoFile,null)
    assert.equal(p.vm.photoLoading,false);assert.equal(p.vm.photoError,'照片暂不可查看')
  }
})

test('无当前行或无考勤查看权限不会读取照片',async()=>{
  let reads=0;const read=async()=>{reads++;return {}}
  const p=page(read);p.vm.rows=[];await p.vm.openPhoto(row())
  const q=page(read,false);await q.vm.openPhoto(row());assert.equal(reads,0)
})

test('关闭、卸载、切批次、切账号后的迟到照片不会回填',async()=>{
  for(const mode of ['close','unmount','batch','account']){
    const d=deferred(),p=page(()=>d.promise),pending=p.vm.openPhoto(row())
    if(mode==='close')p.vm.clearPhoto()
    if(mode==='unmount')p.component.beforeUnmount.call(p.vm)
    if(mode==='batch'){p.store.selectedBatchId='another';p.vm.resetBatchView()}
    if(mode==='account')p.switchAccount()
    d.resolve({fileId:row().watermarkedFileId,sha256:'derived',canPreview:true});await pending
    assert.equal(p.vm.photoFile,null)
  }
})


test('补卡预览读取成功才记录当前版本已查看，切对象不回填',async()=>{
  for(const mode of ['success','failure','switched']){
    const calls=[]
    const p=page(undefined,true,{fileSdk:{blob(){},async preview(id){calls.push(id);if(mode==='failure')throw new Error('private');if(mode==='switched')p.vm.makeupDetail={data:null}}},
      attendanceApi:{async markMakeupEvidenceViewed(id){calls.push('view:'+id);return {code:0}}},toast:{success(){},error(){}}})
    const row={id:'11',attachment:{fileId:'22',fileName:'证据.png'},evidenceViewed:false}
    p.vm.makeupDetail={data:row};p.vm.rows=[row]
    await p.vm.downloadMakeupEvidence(true)
    assert.deepEqual(calls,mode==='success'?['22','view:11']:['22'])
    if(mode==='success')assert.equal(p.vm.makeupDetail.data.evidenceViewed,true)
    else assert.equal(row.evidenceViewed,false)
  }
})
