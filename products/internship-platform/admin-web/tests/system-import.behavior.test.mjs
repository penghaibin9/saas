import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function page(get,save){
  const script=fs.readFileSync(new URL('../src/modules/system/IdentityImportWorkspace.vue',import.meta.url),'utf8')
    .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const route={params:{kind:'students'},query:{jobId:'1'}}
  const vm=new Function('ref','computed','watch','onBeforeUnmount','defineProps','useRoute','useRouter','get','save','getPermissionPatterns','matchPermission',script+
    '\nreturn {preview,error,busy,confirmed,changeContext,confirm,readPage,run}')(
    value=>({value}),getter=>({get value(){return getter()}}),()=>{},()=>{},()=>({fixedKind:''}),()=>route,()=>({}),get,save,()=>[],()=>true)
  return {vm,route}
}
function deferred(){let resolve,reject;const promise=new Promise((done,fail)=>{resolve=done;reject=fail});return {promise,resolve,reject}}

test('导入任务深链切换后立即读取新任务，旧响应不得覆盖或解锁新请求',async()=>{
  const old=deferred(),next=deferred()
  const {vm,route}=page(path=>path.endsWith('/1')?old.promise:next.promise)
  const first=vm.changeContext(['students','1'])
  route.query.jobId='2';const second=vm.changeContext(['students','2'],['students','1'])
  old.resolve({id:'1'});await first
  assert.equal(vm.preview.value,null);assert.equal(vm.busy.value,true)
  next.resolve({id:'2',kind:'students'});await second
  assert.equal(vm.preview.value.id,'2');assert.equal(vm.busy.value,false)
})

test('离开任务后迟到错误不污染新入口，确认勾选不会跨任务保留',async()=>{
  const old=deferred(),{vm,route}=page(()=>old.promise)
  const first=vm.changeContext(['students','1']);vm.confirmed.value=true
  route.query={};await vm.changeContext(['staff',undefined],['students','1'])
  old.reject(new Error('旧任务失败'));await first
  assert.equal(vm.error.value,'');assert.equal(vm.preview.value,null);assert.equal(vm.confirmed.value,false)
})

test('确认开户函数要求预检有效且已核对，重复提交仅一次',async()=>{
  let writes=0;const pending=deferred(),{vm}=page(undefined,()=>{writes++;return pending.promise})
  vm.preview.value={id:'1',status:'VALIDATED',invalidRows:0,version:1}
  await vm.confirm();assert.equal(writes,0)
  vm.confirmed.value=true;vm.preview.value.invalidRows=1;await vm.confirm();assert.equal(writes,0)
  vm.preview.value.invalidRows=0;const first=vm.confirm();await vm.confirm();assert.equal(writes,1)
  pending.resolve({id:'1',status:'IMPORTED'});await first
  assert.equal(vm.confirmed.value,false);assert.equal(vm.preview.value.status,'IMPORTED')
})

test('上传回写同一任务地址不清除刚完成的预检',async()=>{
  let reads=0;const {vm}=page(()=>{reads++})
  vm.preview.value={id:'2',status:'VALIDATED'}
  await vm.changeContext(['students','2'],['students',undefined])
  assert.equal(reads,0);assert.equal(vm.preview.value.id,'2')
})


test('学生预检不得显示在教师开户入口',async()=>{
  const {vm,route}=page(async()=>({id:'1',kind:'students'}))
  route.params.kind='staff';await vm.changeContext(['staff','1'])
  assert.equal(vm.preview.value,null)
  assert.match(vm.error.value,/任务类型与当前入口不一致/)
})

test('范围收回后的详情或下载拒绝清除旧预检及确认，普通失败保留输入',async()=>{
  for(const failure of [{httpStatus:403},{bizCode:'NO_PERMISSION'},{httpStatus:404}]){
    const {vm}=page();vm.preview.value={id:'1',status:'VALIDATED'};vm.confirmed.value=true
    await vm.run(async()=>{throw Object.assign(new Error('当前已无权读取本批次'),failure)})
    assert.equal(vm.preview.value,null);assert.equal(vm.confirmed.value,false)
    assert.equal(vm.error.value,'当前已无权读取本批次');assert.equal(vm.busy.value,false)
  }
  const {vm}=page();vm.preview.value={id:'1',status:'VALIDATED'};vm.confirmed.value=true
  await vm.run(async()=>{throw new Error('服务暂时不可用')})
  assert.equal(vm.preview.value.id,'1');assert.equal(vm.confirmed.value,true)
})
