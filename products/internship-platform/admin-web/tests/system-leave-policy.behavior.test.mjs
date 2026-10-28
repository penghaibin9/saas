import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function page(get, save, query={}) {
  const source=fs.readFileSync(new URL('../src/modules/system/LeavePolicyWorkspace.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const route={query};let changed,ready
  const router={replace:async({query})=>{route.query=Object.fromEntries(Object.entries(query).filter(([,v])=>v!==undefined));await changed(route.query.batchId)}}
  const vm=new Function('ref','computed','watch','onMounted','onBeforeUnmount','useRoute','useRouter','get','save','matchPermission','getPermissionPatterns',script+
    '\nreturn {batchId,policy,nodes,preview,reason,error,receipt,conflict,loading,checking,saving,loadPolicy,check,publish,invalidatePreview,reviewConflict,addNode,selectBatch,restoreBatch}')(
    value=>({value}),getter=>({get value(){return getter()}}),(source,callback,options)=>{if(typeof source==='function'){changed=callback;if(options?.immediate)ready=callback(source())}},()=>{},()=>{},()=>route,()=>router,get,save,()=>true,()=>[])
  return Object.assign(vm,{route,ready})
}
const policy={expectedVersion:1,version:'1',nodes:[{type:'GUIDE',roleCode:'INTERN_MENTOR',userId:''}]}
function deferred(){let resolve;const promise=new Promise(done=>{resolve=done});return {promise,resolve}}

test('切换批次拒绝旧策略与旧责任预览迟到覆盖',async()=>{
  const old=deferred(), preview=deferred()
  const vm=page(path=>path.endsWith('/1')?old.promise:Promise.resolve(policy),()=>preview.promise)
  vm.batchId.value='1';const first=vm.loadPolicy()
  vm.batchId.value='2';await vm.loadPolicy();old.resolve({...policy,version:'旧批次'});await first
  assert.equal(vm.policy.value.version,'1')
  const check=vm.check();vm.batchId.value='3';await vm.loadPolicy()
  preview.resolve({canPublish:true,total:100});await check
  assert.equal(vm.preview.value,null);assert.equal(vm.checking.value,false)
})

test('编辑节点后旧预览不能重新打开发布，缺预览时键盘提交无效',async()=>{
  const pending=deferred();let writes=0
  const vm=page(async()=>policy,()=>{writes++;return pending.promise})
  vm.batchId.value='1';await vm.loadPolicy();await vm.publish();assert.equal(writes,0)
  const check=vm.check();vm.nodes.value=[];vm.invalidatePreview()
  pending.resolve({canPublish:true});await check;await vm.publish()
  assert.equal(vm.preview.value,null);assert.equal(writes,1)
})

test('发布冲突保留节点和原因，明确核对后仍需重新预览',async()=>{
  let writes=0
  const vm=page(async()=>policy,async()=>{writes++;throw Object.assign(new Error('版本冲突'),{details:{version:2,current:{nodes:policy.nodes}}})})
  vm.batchId.value='1';await vm.loadPolicy();vm.reason.value='本次输入';vm.preview.value={canPublish:true}
  await vm.publish();assert.equal(vm.reason.value,'本次输入');assert.deepEqual(vm.nodes.value,policy.nodes)
  await vm.publish();assert.equal(writes,1)
  vm.reviewConflict(2);assert.equal(vm.policy.value.expectedVersion,2);assert.equal(vm.preview.value,null)
  await vm.publish();assert.equal(writes,1)
})

test('发布防重复且离开批次后不回填旧回执',async()=>{
  const pending=deferred();let writes=0
  const vm=page(async()=>policy,()=>{writes++;return pending.promise})
  vm.batchId.value='1';await vm.loadPolicy();vm.preview.value={canPublish:true}
  const first=vm.publish();await vm.publish();assert.equal(writes,1)
  vm.batchId.value='2';await vm.loadPolicy();pending.resolve({version:2,expectedVersion:2,checkedStudents:1});await first
  assert.equal(vm.receipt.value,'');assert.equal(vm.policy.value.version,'1');assert.equal(vm.saving.value,false)
})


test('补回中间级次时仍保持指导教师到院系到学校的顺序',()=>{
  const vm=page()
  vm.nodes.value=[{type:'GUIDE'},{type:'SCHOOL'}]
  vm.addNode()
  assert.deepEqual(vm.nodes.value.map(n=>n.type),['GUIDE','COLLEGE','SCHOOL'])
})

test('清除批次立即结束读取并禁止旧策略迟到回填',async()=>{
  const old=deferred();let reads=0
  const vm=page(()=>{reads++;return old.promise})
  vm.batchId.value='1';const pending=vm.loadPolicy()
  vm.batchId.value='';await vm.loadPolicy()
  assert.equal(reads,1);assert.equal(vm.loading.value,false);assert.equal(vm.policy.value,null)
  old.resolve(policy);await pending
  assert.equal(vm.policy.value,null);assert.equal(vm.loading.value,false)
})

test('配置批次深链恢复并回读，重新选择和清空同步地址但不保存发布内容',async()=>{
  const reads=[];const vm=page(async path=>{reads.push(path);return policy},undefined,{batchId:'9007199254740993',search:'保留筛选'})
  await vm.ready
  assert.equal(vm.batchId.value,'9007199254740993');assert.equal(reads[0],'/leave-policies/9007199254740993')
  vm.reason.value='未提交内容';vm.preview.value={canPublish:true}
  await vm.selectBatch('2')
  assert.equal(vm.route.query.batchId,'2');assert.equal(vm.route.query.search,'保留筛选')
  assert.equal(vm.reason.value,'');assert.equal(vm.preview.value,null)
  await vm.selectBatch('')
  assert.equal(vm.route.query.batchId,undefined);assert.equal(vm.policy.value,null)
  assert.equal(reads.length,2)
  await vm.restoreBatch(['1','2']);assert.equal(vm.batchId.value,'')
})
