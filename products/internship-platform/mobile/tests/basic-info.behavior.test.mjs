import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
const batch='9007199254740993101',record='9007199254740993102',student='9007199254740993103'
const info=(version=0)=>({studentId:student,studentNo:'SYN-001',name:'合成学生',sourceRegion:'',nation:'',gender:'',version,complete:false,missingFields:['生源地','民族','性别'],todoCount:1,statusLabel:'待完善',editable:true})
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function page(overrides={}){
  let generation=1
  const api={getInternship:async()=>({hasBatch:true,batchId:batch,recordId:record,batch:'合成批次'}),getBasicInfo:async()=>info(),saveBasicInfo:async()=>({...info(1),sourceRegion:'湖南省 益阳市',nation:'汉族',gender:'男',complete:true,missingFields:[],todoCount:0,statusLabel:'已完善'}),...overrides}
  const source=fs.readFileSync(new URL('../src/pages/student-internship/basic-info/index.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const component=new Function('studentApi','currentSessionGeneration','normalizeError',script)(api,()=>generation,()=>({pageState:'error',text:'操作未完成，请重试'}))
  const vm={...component.data()}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.requestedBatch=batch
  return {vm,component,api,switchAccount:()=>generation++}
}
async function ready(api){const p=page(api);await p.vm.load();p.vm.form={sourceRegion:'湖南省 益阳市',nation:'汉族',gender:'男'};p.vm.markDirty();return p}
test('保存使用服务器解析的同一学生实习编号与主档版本，真实回执清除基础待办',async()=>{
  let sent;const p=await ready({saveBasicInfo:async(...args)=>{sent=args;return {...info(1),complete:true,missingFields:[],todoCount:0,statusLabel:'已完善'}}});await p.vm.submit()
  assert.deepEqual(sent,[batch,record,{sourceRegion:'湖南省 益阳市',nation:'汉族',gender:'男',expectedVersion:0}]);assert.equal(p.vm.profile.studentId,student);assert.equal(p.vm.receipt.todoCount,0);assert.equal(p.vm.submitting,false)
})
test('学校更新后的重新读取保留草稿，显式核对才接受新版本',async()=>{
  const p=await ready();p.api.getBasicInfo=async()=>({...info(2),sourceRegion:'湖北省 武汉市'});await p.vm.load()
  assert.equal(p.vm.form.sourceRegion,'湖南省 益阳市');assert.equal(p.vm.baseVersion,0);assert.equal(p.vm.conflict,true);await p.vm.submit();assert.equal(p.vm.receipt,null)
  p.vm.acceptLatest();assert.equal(p.vm.baseVersion,2);assert.equal(p.vm.form.sourceRegion,'湖南省 益阳市');assert.equal(p.vm.conflict,false)
})
test('冲突与网络失败保持输入并显示中文安全错误',async()=>{
  const p=await ready({saveBasicInfo:async()=>{throw {bizCode:'DATA_CONFLICT',message:'raw_private_error'}}});await p.vm.submit();assert.equal(p.vm.baseVersion,0);assert.equal(p.vm.form.nation,'汉族');assert.ok(p.vm.formError.includes('输入已保留'));assert.equal(p.vm.receipt,null)
  p.api.saveBasicInfo=async()=>{throw Error('raw_private_error')};await p.vm.submit();assert.equal(p.vm.formError,'操作未完成，请重试')
})
test('重复点击仅发送一次保存请求',async()=>{
  const wait=deferred();let calls=0;const p=await ready({saveBasicInfo:()=>{calls++;return wait.promise}});const pending=p.vm.submit();await p.vm.submit();assert.equal(calls,1);wait.resolve(info(1));await pending;assert.equal(p.vm.submitting,false)
})
test('切换账号后的迟到保存不能恢复旧身份和旧回执',async()=>{
  const wait=deferred();const p=await ready({saveBasicInfo:()=>wait.promise});const pending=p.vm.submit();p.switchAccount();p.vm.resetAccount();p.vm.form.nation='新账号未提交资料';wait.resolve(info(1));await pending;assert.equal(p.vm.profile,null);assert.equal(p.vm.receipt,null);assert.equal(p.vm.form.nation,'新账号未提交资料')
})
test('隐藏页面的迟到加载和历史只读资料不能写入',async()=>{
  const wait=deferred();const p=page({getBasicInfo:()=>wait.promise});const pending=p.vm.load();await Promise.resolve();p.component.onHide.call(p.vm);wait.resolve(info());await pending;assert.equal(p.vm.profile,null)
  const q=await ready({getBasicInfo:async()=>({...info(),editable:false})});assert.equal(q.vm.editable,false);await q.vm.submit();assert.equal(q.vm.receipt,null)
})
