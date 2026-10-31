import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { formatDateTime } from '../src/utils/dateUtils.js'
const batch='9007199254740993001',id='9007199254740993002'
const ok=data=>({code:0,data})
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
function page(api={},sdk={}){
  const source=fs.readFileSync(new URL('../src/modules/internship/views/TeacherManagementView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let generation=0
  const store={selectedBatchId:batch}
  const scope={formatDateTime,AppDatePicker:{},ModulePageShell:{},DataTable:{},ErrorState:{},LoadingState:{},AppButton:{},AppExportButton:{},AppStatusTag:{},AppPagination:{},FilePreviewer:{},
    internshipApi:{getTeacherCheckins:async()=>ok({items:[],total:0}),...api},useInternshipBatchStore:()=>store,canCode:()=>true,
    currentSessionGeneration:()=>generation,fileSdk:{metadata:async fileId=>({fileId}),...sdk}}
  const c=new Function(...Object.keys(scope),script)(...Object.values(scope)),vm={...c.data(),ctx:{ctxKey:'current'}}
  for(const [key,method] of Object.entries(c.methods))vm[key]=(...args)=>method.apply(vm,args)
  for(const [key,getter] of Object.entries(c.computed))Object.defineProperty(vm,key,{get:()=>getter.call(vm)})
  return {vm,c,store,switchAccount:()=>generation++}
}

test('教师签到明细按筛选和页码读取，保留大编号及原备注',async()=>{
  let params
  const p=page({getTeacherCheckins:async x=>{params=x;return ok({items:[{id,note:'原备注'}],total:51})}})
  Object.assign(p.vm,{checkinTeacher:id,checkinStart:'2024-01-01',checkinEnd:'2024-01-31',checkinResult:'MAKEUP'})
  await p.vm.onCheckinPage({page:2,pageSize:50})
  assert.deepEqual(params,{batchId:batch,teacherUserId:id,result:'MAKEUP',startDate:'2024-01-01',endDate:'2024-01-31',page:2,pageSize:50})
  assert.equal(p.vm.checkins[0].note,'原备注');assert.equal(p.vm.checkinTotal,51)
})

test('签到明细读取失败和日期倒置保留筛选并清除旧学校事实',async()=>{
  const p=page({getTeacherCheckins:async()=>{throw new Error('network')}})
  p.vm.checkins=[{id:'old'}];p.vm.checkinStart='2024-01-01'
  await p.vm.loadCheckins();assert.deepEqual(p.vm.checkins,[]);assert.equal(p.vm.checkinLoading,false);assert.ok(p.vm.checkinError)
  p.vm.checkinEnd='2023-12-31';await p.vm.loadCheckins();assert.ok(p.vm.checkinError.includes('开始日期'));assert.equal(p.vm.checkinStart,'2024-01-01')
})

test('换批次、账号或卸载后旧查询及照片不能回填',async()=>{
  const d=deferred(),photo=deferred(),p=page({getTeacherCheckins:()=>d.promise},{metadata:()=>photo.promise})
  const waiting=p.vm.loadCheckins();p.store.selectedBatchId='other';p.vm.resetCheckins();d.resolve(ok({items:[{id:'old'}],total:1}));await waiting
  assert.deepEqual(p.vm.checkins,[])
  p.store.selectedBatchId=batch;p.vm.checkins=[{id,batchId:batch,photoFileId:'canonical'}]
  const reading=p.vm.openCheckinPhoto({...p.vm.checkins[0],photoFileId:'forged'},true)
  p.switchAccount();p.vm.resetCheckins();photo.resolve({fileId:'canonical'});await reading
  assert.equal(p.vm.photoFile,null)
  p.c.beforeUnmount.call(p.vm);assert.equal(p.vm.disposed,true)
})

test('导出只发筛选，不随页码截断；条件或学校切换后不触发旧文件下载',async()=>{
  let params;const d=deferred(),p=page({exportTeacherCheckins:x=>{params=x;return d.promise}})
  p.vm.checkinPage=8;p.vm.checkinPageSize=20;p.vm.checkinStart='2024-01-01'
  const waiting=p.vm.exportCheckinsFn();assert.equal(params.page,undefined);assert.equal(params.batchId,batch)
  p.vm.checkinStart='2025-01-01';d.resolve(ok({contentBase64:'old'}));const response=await waiting
  assert.notEqual(response.code,0);assert.equal(response.data,undefined)
})

test('签到照片只使用当前明细的正式编号，关闭后迟到信息不能恢复',async()=>{
  const ids=[],d=deferred(),p=page({}, {metadata:fileId=>{ids.push(fileId);return d.promise}})
  p.vm.checkins=[{id,batchId:batch,photoFileId:'original',watermarkedFileId:'watermark'}]
  const reading=p.vm.openCheckinPhoto({id,watermarkedFileId:'forged'})
  assert.deepEqual(ids,['watermark']);p.vm.clearCheckinPhoto();d.resolve({fileId:'watermark'});await reading
  assert.equal(p.vm.photoFile,null);assert.equal(p.vm.photoLoading,false)
})

test('教师工作台账按统一时区显示相同业务时刻，空值不伪造日期',()=>{
  const {vm}=page();assert.equal(vm.displayTime('2026-10-28T18:00:00Z'),vm.displayTime('2026-10-29T02:00:00+08:00'));assert.equal(vm.displayTime(''),'未记录')
})
