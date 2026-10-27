import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
function mount(api, id = '') {
  const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/funding/StudentLoanView.vue', import.meta.url), 'utf8')
  const imports = []
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, names) => { imports.push(...names.split(',').map(x=>x.trim())); return '' }).replace(/import\s+(\w+)\s+from\s+['"][^'"]+['"]/g, (_, name) => { imports.push(name); return '' }).replace('export default', 'return')
  const c = new Function(...imports, script)(...imports.map(n=>n==='studentAffairsApi'?api:n==='toast'?{success(){},error(){}}:{}))
  const vm = {...c.data(), $route:{query:{recordId:id}}, ...c.methods}
  for (const [k,v] of Object.entries(c.computed)) Object.defineProperty(vm,k,{get:()=>v.call(vm)})
  return vm
}
test('deep link queries the exact string ID without the default pending filter',async()=>{
  let query
  const vm=mount({getLoans:async q=>{query=q;return {code:0,data:{items:[{loanId:q.recordId,status:'CONFIRMED'}],total:1}}}},'9007199254740993')
  await vm.load()
  assert.deepEqual(query,{recordId:'9007199254740993',page:1,pageSize:1})
  assert.equal(vm.loans[0].status,'CONFIRMED')
})
test('invalid link does not fall through into an unrelated queue',async()=>{
  const vm=mount({getLoans:()=>assert.fail('must not read a different queue')},'bad')
  await vm.load();assert.match(vm.errorMessage,/编号无效/)
})
test('switching targets discards the late previous record',async()=>{
  let finish
  const vm=mount({getLoans:q=>q.recordId==='1'?new Promise(r=>finish=r):Promise.resolve({code:0,data:{items:[],total:0}})},'1')
  const old=vm.load();vm.$route.query.recordId='2';await vm.load()
  finish({code:0,data:{items:[{loanId:'1'}],total:1}});await old
  assert.deepEqual(vm.loans,[])
})
test('return to ledger removes only record focus and retains route context',async()=>{
  const vm=mount({},'1');vm.$route.query.batchId='7';let result
  vm.$router={replace:q=>result=q};vm.clearFocus()
  assert.deepEqual(result,{path:undefined,query:{batchId:'7'}})
})

test('real API adapter carries recordId through to the request transport',async()=>{
  const source=fs.readFileSync(new URL('../src/modules/studentAffairs/api/studentAffairs.api.js',import.meta.url),'utf8')
  const method=source.slice(source.indexOf('  getLoans('),source.indexOf('  },',source.indexOf('  getLoans('))+5).trim().replace(/,$/,'')
  let request
  const api=new Function('request','callStrict',`return {${method}}`)((url,options)=>{request={url,...options};return {items:[],total:0}},fn=>fn())
  await api.getLoans({recordId:'9007199254740993',page:1,pageSize:1})
  assert.deepEqual(request,{url:'/student-affairs/loans',params:{recordId:'9007199254740993',page:1,pageSize:1}})
})

test('focused work area exposes only server-provided actions',()=>{
 const vm=mount({})
 assert.deepEqual(vm.availableActions({allowedActions:['VERIFY','RETURN']}).map(a=>a.code),['VERIFY','RETURN'])
 assert.deepEqual(vm.availableActions({allowedActions:[]}),[])
 assert.deepEqual(vm.availableActions({}),[])
})

test('receipt-only handling never turns a masked amount into a replacement amount', async () => {
  let payload
  const vm = mount({ actionLoan: async (_id, body) => { payload = body; return { code: 0 } } })
  vm.load = async () => {}
  vm.openAction({ loanId: '1', version: 3, amount: '5000以上', loanType: 'ORIGIN', yearCode: '2026-2027', allowedActions: ['SUBMIT_RECEIPT'] }, 'SUBMIT_RECEIPT')
  vm.actionDrawer.form.receiptCode = 'TEST-123456'
  await vm.submitAction()
  assert.ok(payload, vm.actionDrawer.errorMessage)
  assert.equal(Object.hasOwn(payload, 'amount'), false)
  assert.equal(payload.receiptCode, 'TEST-123456')
})

test('loan conflict reloads the exact record and retains the entered reason', async () => {
  let query
  const vm = mount({ actionLoan: async () => ({ code: 409001, bizCode: 'APPROVAL_VERSION_CONFLICT', message: '记录已更新' }),
    getLoans: async q => { query = q; return { code: 0, data: { items: [{ loanId: '1', version: 4, allowedActions: ['RETURN'] }] } } } })
  vm.openAction({ loanId: '1', version: 3, allowedActions: ['RETURN'] }, 'RETURN')
  vm.actionDrawer.form.reason = '请补齐学校要求的回执材料'
  await vm.submitAction()
  assert.equal(query.recordId, '1')
  assert.equal(vm.actionDrawer.row.version, 4)
  assert.equal(vm.actionDrawer.form.reason, '请补齐学校要求的回执材料')
  assert.equal(vm.actionDrawer.visible, true)
})
