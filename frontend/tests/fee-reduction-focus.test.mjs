import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
function mount(api, id = '') {
  const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/funding/FeeReductionView.vue', import.meta.url), 'utf8')
  const imports = []
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, names) => { imports.push(...names.split(',').map(x=>x.trim())); return '' }).replace(/import\s+(\w+)\s+from\s+['"][^'"]+['"]/g, (_, name) => { imports.push(name); return '' }).replace('export default', 'return')
  const c = new Function(...imports, script)(...imports.map(n=>n==='studentAffairsApi'?api:{}))
  const vm = {...c.data(), $route:{query:{recordId:id}}, ...c.methods}
  for (const [k,v] of Object.entries(c.computed)) Object.defineProperty(vm,k,{get:()=>v.call(vm)})
  return vm
}
test('deep link queries the exact string ID without the default pending filter',async()=>{
  let query
  const vm=mount({getFeeReductions:async q=>{query=q;return {code:0,data:{items:[{feeId:q.recordId,status:'ISSUED'}],total:1}}}},'9007199254740993')
  await vm.load()
  assert.deepEqual(query,{recordId:'9007199254740993',page:1,pageSize:1})
  assert.equal(vm.items[0].status,'ISSUED')
})
test('invalid link does not fall through into an unrelated queue',async()=>{
  const vm=mount({getFeeReductions:()=>assert.fail('must not read a different queue')},'bad')
  await vm.load();assert.match(vm.errorMessage,/链接无效/)
})
test('switching targets discards the late previous record',async()=>{
  let finish
  const vm=mount({getFeeReductions:q=>q.recordId==='1'?new Promise(r=>finish=r):Promise.resolve({code:0,data:{items:[],total:0}})},'1')
  const old=vm.load();vm.$route.query.recordId='2';await vm.load()
  finish({code:0,data:{items:[{feeId:'1'}],total:1}});await old
  assert.deepEqual(vm.items,[])
})
test('return to ledger removes only record focus and retains route context',async()=>{
  const vm=mount({},'1');vm.$route.query.batchId='7';let result
  vm.$router={replace:q=>result=q};vm.clearFocus()
  assert.deepEqual(result,{query:{batchId:'7'}})
})

test('real API adapter carries recordId through to the request transport',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/studentAffairs/api/studentAffairs.api.js',import.meta.url),'utf8')
  const method=source.slice(source.indexOf('  getFeeReductions('),source.indexOf('  submitFeeReduction(')).trim().replace(/,$/,'')
  let request
  const api=new Function('request','callStrict',`return {${method}}`)((url,options)=>{request={url,...options};return {items:[],total:0}},fn=>fn())
  await api.getFeeReductions({recordId:'9007199254740993',page:1,pageSize:1})
  assert.deepEqual(request,{url:'/student-affairs/fee-reductions',params:{recordId:'9007199254740993',page:1,pageSize:1}})
})
