import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function page(get, save, emit = () => {},query={}) {
  const source = fs.readFileSync(new URL('../src/modules/system/ResponsibilityHandoff.vue', import.meta.url), 'utf8')
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm, '')
  const route={query};let changed,getters,ready
  const router={replace:async({query})=>{route.query=Object.fromEntries(Object.entries(query).filter(([,v])=>v!==undefined));await changed(getters.map(read=>read()))}}
  const vm=new Function('ref', 'watch','useRoute','useRouter','onBeforeUnmount', 'defineProps', 'defineEmits', 'ElLoading', 'get', 'save', script +
    '\nreturn {batchId,source,page,expanded,items,total,loading,selected,receipt,error,load,restoreContext,setContext,transfer,taskId}')(
    value => ({value}), (sources,callback,options)=>{getters=sources;changed=callback;if(options?.immediate)ready=callback(sources.map(read=>read()))},()=>route,()=>router,() => {}, () => {}, () => emit, {directive:{}}, get, save)
  return Object.assign(vm,{route,ready})
}
function deferred() { let resolve; const promise = new Promise(done => { resolve = done }); return {promise,resolve} }

test('清除交接范围时结束加载并拒绝迟到清单', async () => {
  const pending=deferred(), vm=page(() => pending.promise)
  vm.batchId.value='1'; vm.source.value='2'
  const request=vm.load()
  vm.restoreContext(['1','',1])
  assert.equal(vm.loading.value,false)
  assert.equal(vm.total.value,0)
  pending.resolve({items:[{id:'old'}],total:1}); await request
  assert.deepEqual(vm.items.value,[])
})

test('交接提交期间切换范围不让旧回执覆盖新选择', async () => {
  const pending=deferred(), vm=page(async () => ({items:[],total:0}), () => pending.promise)
  vm.batchId.value='1';vm.source.value='2';vm.selected.value={id:'3',version:1}
  const request=vm.transfer()
  vm.restoreContext(['1','4',1]);vm.selected.value={id:'5',version:2}
  pending.resolve({message:'旧范围交接成功'});await request
  assert.equal(vm.receipt.value,'')
  assert.equal(vm.selected.value.id,'5')
})

test('交接深链恢复批次原责任人与页码，切换对象清除未提交交接并重回第一页',async()=>{
  const reads=[];const vm=page(async(path,params)=>{reads.push({path,params});return {items:[{id:'8'}],total:65}},undefined,undefined,
    {handoffBatchId:'9007199254740993',handoffSourceId:'2',handoffPage:'2',search:'保留筛选'})
  await vm.ready
  assert.equal(vm.expanded.value,true);assert.equal(vm.page.value,2)
  assert.deepEqual(reads[0],{path:'/handoffs',params:{batchId:'9007199254740993',userId:'2',page:2}})
  vm.selected.value={id:'8'};vm.receipt.value='原交接回执'
  await vm.setContext('3','4')
  assert.equal(vm.page.value,1);assert.equal(vm.selected.value,null);assert.equal(vm.receipt.value,'')
  assert.equal(vm.route.query.handoffBatchId,'3');assert.equal(vm.route.query.search,'保留筛选')
  await vm.setContext('3','4',3);assert.equal(vm.page.value,3);assert.equal(vm.route.query.handoffPage,'3')
  await vm.restoreContext(['bad',['4'],'NaN'])
  assert.equal(vm.page.value,1);assert.equal(vm.expanded.value,false);assert.deepEqual(vm.items.value,[])
  assert.equal(reads.length,3)
})


test('交接成功通知工作区刷新异常清单，失败不伪报完成', async () => {
  const events=[]
  const vm=page(async () => ({items:[],total:0}),async () => ({message:'已交接'}),event => events.push(event))
  vm.batchId.value='1';vm.source.value='2';vm.selected.value={id:'3',version:1}
  await vm.transfer()
  assert.deepEqual(events,['transferred'])
  assert.equal(vm.receipt.value,'已交接')
  const failed=page(async () => ({items:[],total:0}),async () => {throw new Error('版本冲突')},event => events.push(event))
  failed.selected.value={id:'3',version:1};await failed.transfer()
  assert.equal(failed.selected.value.id,'3')
  assert.equal(failed.error.value,'版本冲突')
  assert.deepEqual(events,['transferred'])
})


test('异常待办深链仅读取原节点，切换批次或责任人清除节点限制',async()=>{
  const reads=[];const vm=page(async(path,params)=>{reads.push({path,params});return {items:[{id:'9007199254740995'}],total:1}},undefined,undefined,
    {handoffBatchId:'17',handoffSourceId:'19',handoffTaskId:'9007199254740995',blocked:'1',blockedPage:'2'})
  await vm.ready
  assert.equal(vm.taskId.value,'9007199254740995');assert.equal(reads[0].params.taskId,'9007199254740995')
  await vm.setContext('17','20')
  assert.equal(vm.taskId.value,'');assert.equal(vm.route.query.handoffTaskId,undefined)
  assert.equal(vm.route.query.blockedPage,'2');assert.equal(reads.at(-1).params.taskId,undefined)
})
