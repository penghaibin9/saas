import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

function page(api) {
  let generation=1
  const source=fs.readFileSync(new URL('../src/pages/teacher-internship/todos/index.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const component=new Function('teacherApi','go','uni','currentSessionGeneration',script)(api,()=>{}, {stopPullDownRefresh(){}},()=>generation)
  const vm=component.data()
  for(const [key,method] of Object.entries(component.methods))vm[key]=(...args)=>method.apply(vm,args)
  for(const [key,method] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>method.call(vm)})
  return {vm,component,logout:()=>generation++}
}

test('returning from employment review rereads pending tasks in the selected group',async()=>{
  let done=false,requested
  const {vm,component}=page({getInternshipWorkbenchTodos:async query=>{
    requested=query
    return {items:done?[]:[{todoId:'833',sourceBizId:'10'}],groupCounts:{OTHER:done?0:1},hasMore:false}
  }})
  vm.group='OTHER'
  await component.onShow.call(vm)
  assert.equal(vm.items[0].sourceBizId,'10')
  done=true;vm.page=2
  await component.onShow.call(vm)
  assert.deepEqual(requested,{status:'PENDING',group:'OTHER',page:1,pageSize:30})
  assert.deepEqual(vm.items,[]);assert.equal(vm.counts.OTHER,0);assert.equal(vm.state,'ready')
})

test('failed reread shows an error and a later return retries the same group',async()=>{
  let fail=true
  const {vm,component}=page({getInternshipWorkbenchTodos:async()=>{
    if(fail)throw Error('合成网络异常')
    return {items:[],groupCounts:{OTHER:0},hasMore:false}
  }})
  vm.group='OTHER'
  await component.onShow.call(vm)
  assert.equal(vm.state,'error');assert.equal(vm.error,'合成网络异常')
  fail=false
  await component.onShow.call(vm)
  assert.equal(vm.state,'ready');assert.equal(vm.error,'');assert.equal(vm.group,'OTHER')
})

test('只展示非零待办和当前分类，全部分类仍可展开',()=>{
  const {vm}=page({});vm.counts={ALL:3,REPORT:0,LEAVE:3,VISIT:0}
  assert.deepEqual(vm.visibleFilters.map(x=>x.key),['ALL','LEAVE'])
  vm.group='REPORT';assert.deepEqual(vm.visibleFilters.map(x=>x.key),['ALL','REPORT','LEAVE'])
  vm.allFiltersOpen=true;assert.equal(vm.visibleFilters.length,8)
})

test('切分类和账号后旧待办回执不能覆盖当前列表',async()=>{
  let resolve;const old=new Promise(r=>resolve=r)
  const p=page({getInternshipWorkbenchTodos:args=>args.group==='ALL'?old:Promise.resolve({items:[{todoId:'new'}],groupCounts:{ALL:1,LEAVE:1},hasMore:false})})
  const pending=p.vm.load();p.vm.group='LEAVE';await p.vm.load();resolve({items:[{todoId:'old'}],groupCounts:{ALL:99},hasMore:false});await pending
  assert.equal(p.vm.items[0].todoId,'new');assert.equal(p.vm.counts.ALL,1)
  let finish;const next=new Promise(r=>finish=r)
  const q=page({getInternshipWorkbenchTodos:()=>next});const reading=q.vm.load();q.logout();finish({items:[{todoId:'foreign'}],groupCounts:{ALL:1},hasMore:false});await reading;assert.deepEqual(q.vm.items,[])
})

test('后续待办失败保留当前页并可重试，不冒充完成',async()=>{
  let fail=false;const p=page({getInternshipWorkbenchTodos:async args=>{if(args.page===2&&fail)throw Error('后续队列暂不可用');return {items:[{todoId:String(args.page)}],groupCounts:{ALL:2},hasMore:args.page===1}}})
  await p.vm.load();fail=true;await p.vm.loadMore();assert.equal(p.vm.page,1);assert.equal(p.vm.items.length,1);assert.equal(p.vm.hasMore,true);assert.match(p.vm.loadMoreError,/暂不可用/)
  fail=false;await p.vm.loadMore();assert.equal(p.vm.page,2);assert.deepEqual(p.vm.items.map(x=>x.todoId),['1','2']);assert.equal(p.vm.loadMoreError,'')
})
