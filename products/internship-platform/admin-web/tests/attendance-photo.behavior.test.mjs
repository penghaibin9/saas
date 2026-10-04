import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const row=()=>({id:'9007199254740993101',date:'2026-10-04',studentName:'合成学生',
  photoFileId:'9007199254740993102',watermarkedFileId:'9007199254740993103',photoSha256:'original',watermarkedSha256:'derived'})
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}

function page(metadata,allowed=true){
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
