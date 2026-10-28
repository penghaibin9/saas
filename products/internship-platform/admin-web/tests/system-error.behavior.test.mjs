import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

function page(request, plan) {
  const source=fs.readFileSync(new URL('../src/views/auth/StandaloneSecurityErrorView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'').replace('export default','return')
  const component=new Function('request','getVisibleNavPlan','clearAuthSession',script)(request,()=>plan,()=>{})
  const destinations=[]
  const vm={...component.data(),status:'403',$route:{query:{}},$router:{replace:async path=>destinations.push(path)}}
  for(const [name,method] of Object.entries(component.methods))vm[name]=method.bind(vm)
  return {vm,destinations}
}

test('无权页面返回当前身份的可用工作页，不固定进入实习首页',async()=>{
  const calls=[]
  const {vm,destinations}=page(async path=>{calls.push(path);return {}},[{children:[{children:[{path:'/admin/system/organizations'}]}]}])
  await vm.goSafe()
  assert.deepEqual(calls,['/rbac/current-context'])
  assert.deepEqual(destinations,['/admin/system/organizations'])
  assert.equal(vm.returning,false)
})

test('权限服务失败或无可用页时停留并解释原因，重复点击不会重复读取',async()=>{
  let reject,reads=0
  const {vm,destinations}=page(()=>{reads++;return new Promise((resolve,fail)=>{reject=fail})},[])
  const pending=vm.goSafe();await vm.goSafe();assert.equal(reads,1)
  reject(new Error('unavailable'));await pending
  assert.deepEqual(destinations,[])
  assert.match(vm.navigationError,/暂时无法确认/)
  const empty=page(async()=>({}),[])
  await empty.vm.goSafe()
  assert.deepEqual(empty.destinations,[])
  assert.match(empty.vm.navigationError,/暂无可进入/)
})
