import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function picker(get, values={}) {
  const source=fs.readFileSync(new URL('../src/modules/system/SystemObjectSelect.vue',import.meta.url),'utf8')
  const script=source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'')
  const props={path:'/organizations/colleges',modelValue:'',label:'选择院系',...values},watchers=[]
  let selectedReady
  const vm=new Function('ref','watch','defineProps','defineEmits','get',script+
    '\nreturn {items,total,page,loading,error,selected,load,search,openOptions,optionLabel:typeof optionLabel=== "function" ? optionLabel : undefined}')(
    value=>({value}),(read,callback,options)=>{
      const watcher={read,callback,cleanup:()=>{}};watchers.push(watcher)
      if(options?.immediate)selectedReady=callback(read(),undefined,fn=>{watcher.cleanup=fn})
    },()=>props,()=>{},get)
  return {vm,props,selectedReady,changePath(path){props.path=path;return watchers[0].callback()}}
}

test('同名对象按代码区分，已选对象回填不依赖第一页且保留前导零',async()=>{
  const {vm,selectedReady}=picker(async(path,params)=>{
    assert.equal(path,'/selection');assert.equal(params.identifier,'9007199254740993')
    return {id:params.identifier,name:'同名学院',code:'0002'}
  },{modelValue:'9007199254740993'})
  await selectedReady
  assert.equal(typeof vm.optionLabel,'function')
  assert.equal(vm.optionLabel({name:'同名学院',code:'0001'}),'同名学院（0001）')
  assert.equal(vm.optionLabel(vm.selected.value),'同名学院（0002）')
  assert.deepEqual(vm.items.value,[])
  assert.equal(vm.selected.value.id,'9007199254740993')
  assert.equal(vm.optionLabel({name:'同名教师',loginName:'T002'}),'同名教师（T002）')
})

test('重新查询失败不保留上一条件的候选，不自动选择第一个对象',async()=>{
  const {vm}=picker(async()=>{throw new Error('当前范围查询不可用')})
  vm.items.value=[{id:'1',name:'旧条件学院'}];vm.total.value=60;vm.page.value=2
  await vm.load(true)
  assert.deepEqual(vm.items.value,[])
  assert.equal(vm.total.value,0)
  assert.equal(vm.page.value,1)
  assert.equal(vm.loading.value,false)
  assert.equal(vm.error.value,'当前范围查询不可用')
  assert.equal(vm.selected.value,null)
})

test('切换组织类型后旧查询不能覆盖新候选，追加失败保留同条件已加载页',async()=>{
  let finish
  const {vm,changePath}=picker((path,params)=>{
    if(path.endsWith('colleges'))return new Promise(resolve=>{finish=resolve})
    if(params.page>1)return Promise.reject(new Error('下一页读取失败'))
    return Promise.resolve({items:[{id:'2',name:'本校部门',code:'D01'}],total:55})
  })
  const old=vm.load(true);await changePath('/organizations/departments')
  finish({items:[{id:'1',name:'旧院系'}],total:60});await old
  assert.deepEqual(vm.items.value,[{id:'2',name:'本校部门',code:'D01'}])
  await vm.load(false)
  assert.equal(vm.items.value[0].id,'2');assert.equal(vm.page.value,2)
  assert.equal(vm.error.value,'下一页读取失败')
})


test('打开与相同远程关键词不重复发请求，空结果也稳定，主动刷新和新关键词仍读取',async()=>{
  let finish;let calls=0
  const {vm}=picker(()=>{calls++;return new Promise(resolve=>{finish=resolve})})
  const request=vm.openOptions();vm.openOptions();vm.search('')
  assert.equal(calls,1)
  finish({items:[],total:0});await request
  vm.openOptions();vm.search('');assert.equal(calls,1)
  const refresh=vm.load(true);assert.equal(calls,2);finish({items:[{id:'1'}],total:1});await refresh
  const searched=vm.search('新教师');assert.equal(calls,3);finish({items:[{id:'2'}],total:1});await searched
  assert.deepEqual(vm.items.value,[{id:'2'}])
})
