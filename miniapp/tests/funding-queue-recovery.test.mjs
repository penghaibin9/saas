import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const cases = [
  { name: 'loan', read: 'getAffairsLoans', write: 'actAffairsLoan', rows: 'items', id: 'loanId', load: 'loadItems' },
  { name: 'reduction', read: 'getAffairsFeeReductions', write: 'actAffairsFeeReduction', rows: 'items', id: 'feeId', load: 'loadItems' },
  { name: 'work-study', read: 'getWorkStudyRecords', write: 'actWorkStudy', rows: 'records', id: 'recordId', load: 'loadRecords' }
]
function deferred() { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b }); return { promise, resolve, reject } }
function mount(config, api, navigation = {}) {
  const source = fs.readFileSync(new URL(`../src/pages/teacher/affairs/${config.name}/index.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
  const notices = []
  const component = new Function('teacherApi','fileSdk','normalizeError','toast','uni',script)(api,{},e=>({text:e.message}),t=>notices.push(t),navigation)
  const vm = { ...component.data(), ...component.methods }
  for (const [key, getter] of Object.entries(component.computed)) Object.defineProperty(vm,key,{ get:()=>getter.call(vm) })
  return { vm, notices, unload:()=>component.onUnload.call(vm) }
}
for (const c of cases) {
  test(`${c.name}: unknown or masked amounts never display as zero`,()=>{
    const {vm}=mount(c,{})
    for(const amount of [null,undefined,'']) assert.equal(vm.money(amount),'—')
    assert.equal(vm.money('***'),'金额已隐藏')
    assert.equal(vm.money('0.00'),'¥0.00')
    assert.equal(vm.money('1800.50'),'¥1800.50')
  })
  const row = (id, version=3) => ({ [c.id]:id, version, allowedActions:['APPROVE'] })
  const response = (items,total=items.length) => ({items,total,statusCounts:{ALL:total}})
  const act = vm => {
    vm.actionTarget=row('selected'); vm.actionType='APPROVE'
    if(c.name==='reduction') return vm.submitAction()
    return c.name==='loan' ? vm.runAction(vm.actionTarget,{action:'VERIFY',version:3}) : vm.runAction(vm.actionTarget,'APPROVE','',false)
  }
  test(`${c.name}: newest query wins; old failure cannot clear current loading`,async()=>{
    const old=deferred(), recent=deferred()
    const {vm}=mount(c,{[c.read]:q=>q.keyword==='old'?old.promise:recent.promise})
    vm.keyword='old'; const a=vm.search(); vm.keyword='new'; const b=vm.search()
    old.reject(new Error('old failure')); await a
    assert.equal(vm.refreshing,true); assert.equal(vm.state,'loading')
    recent.resolve(response([row('new')])); await b
    assert.deepEqual(vm[c.rows],[row('new')]); assert.equal(vm.listError,'')
    assert.equal(vm.refreshing,false)
  })
  test(`${c.name}: unloading invalidates pending data`,async()=>{
    const pending=deferred(); const {vm,unload}=mount(c,{[c.read]:()=>pending.promise})
    const task=vm.load(); unload(); pending.resolve(response([row('late')]))
    await task; assert.deepEqual(vm[c.rows],[])
  })
  test(`${c.name}: pagination retains the applied search, retries failure and deduplicates`,async()=>{
    const pending=deferred(),calls=[]; let retry=false
    const {vm}=mount(c,{[c.read]:q=>{calls.push(q); return q.page===1?Promise.resolve(response([row('a')],3)):retry?Promise.resolve(response([row('a'),row('b'),row('c')],3)):pending.promise}})
    vm.keyword='甲'; await vm.search(); vm.keyword='未提交'
    const a=vm[c.load](true); await vm[c.load](true)
    pending.reject(new Error('offline')); await a
    assert.equal(calls.length,2); assert.equal(vm.page,1); assert.equal(vm.state,'ready')
    assert.deepEqual(vm[c.rows],[row('a')]); assert.match(vm.moreError,/仍保留/)
    retry=true; await vm[c.load](true)
    assert.deepEqual(calls.map(q=>[q.page,q.keyword]),[[1,'甲'],[2,'甲'],[2,'甲']])
    assert.deepEqual(vm[c.rows].map(x=>x[c.id]),['a','b','c']); assert.equal(vm.moreError,'')
  })
  test(`${c.name}: an old next page cannot contaminate a new search`,async()=>{
    const pending=deferred(); const {vm}=mount(c,{[c.read]:q=>q.page===2?pending.promise:Promise.resolve(response([row(q.keyword)],5))})
    vm.keyword='old'; await vm.search(); const a=vm[c.load](true)
    vm.keyword='new'; await vm.search(); pending.resolve(response([row('old-next')],5)); await a
    assert.deepEqual(vm[c.rows],[row('new')]); assert.equal(vm.page,1)
  })
  test(`${c.name}: committed action stays successful when refresh fails; retry only reads`,async()=>{
    let writes=0,offline=true
    const {vm,notices}=mount(c,{[c.write]:async()=>{writes++},[c.read]:async()=>{if(offline)throw new Error('网络暂不可用');return response([])}})
    await act(vm)
    assert.equal(writes,1); assert.equal(vm.actionTarget,null); assert.equal(vm.actionError,'')
    assert.equal(vm.state,'error'); assert.match(vm.listError,/网络/); assert.equal(notices.length,1)
    offline=false; await vm.load(); assert.equal(writes,1); assert.equal(vm.state,'ready')
  })
  test(`${c.name}: duplicate events do not double-write and conflicts retain the form`,async()=>{
    const pending=deferred(); let writes=0
    const {vm}=mount(c,{[c.write]:()=>{writes++;return pending.promise},[c.read]:()=>assert.fail('failed mutation must retain form')})
    const a=act(vm); await act(vm); pending.reject(new Error('记录已更新，请刷新后核对')); await a
    assert.equal(writes,1); assert.equal(vm.actionTarget[c.id],'selected'); assert.equal(vm.actionTarget.version,3)
    assert.match(vm.actionError,/记录已更新/); assert.equal(vm.busy,'')
  })
}
test('work-study: blank hours or subsidy never silently become zero',()=>{
  const {vm}=mount(cases[2],{})
  vm.monthly={monthCode:'2026-09',workHours:'',subsidyAmount:'',rating:'PASS'}
  assert.equal(vm.monthlyValid,false)
  vm.monthly.workHours='0'; assert.equal(vm.monthlyValid,false)
  vm.monthly.subsidyAmount='0'; assert.equal(vm.monthlyValid,true)
  vm.monthly.rating='FAIL'; vm.monthly.subsidyAmount=''; assert.equal(vm.monthlyValid,true)
  vm.monthly.workHours=''; assert.equal(vm.monthlyValid,false)
})

test('reduction: exact target bypasses pending filter and survives a write/read',async()=>{
  const calls=[]; const {vm}=mount(cases[1],{getAffairsFeeReductions:async q=>{calls.push(q);return {items:[{feeId:q.recordId,status:'APPROVED'}],total:1}},actAffairsFeeReduction:async()=>({})})
  vm.focusId='9007199254740993';await vm.load()
  assert.deepEqual(calls[0],{recordId:'9007199254740993',page:1,pageSize:1})
  vm.openAction(vm.items[0],'FULFILL');await vm.submitAction()
  assert.equal(calls[1].recordId,'9007199254740993')
  assert.equal(vm.focusId,'9007199254740993')
})
test('reduction: malformed target never silently opens an unrelated queue',async()=>{
  const {vm}=mount(cases[1],{getAffairsFeeReductions:()=>assert.fail('invalid link')})
  vm.focusId='NaN';await vm.load();assert.equal(vm.state,'error');assert.match(vm.listError,/链接无效/)
})

test('reduction: return replaces the focused URL with the normal queue',()=>{
  let target;const {vm}=mount(cases[1],{},{redirectTo:q=>target=q});vm.focusId='1';vm.clearFocus();assert.deepEqual(target,{url:'/pages/teacher/affairs/reduction/index'})
})

test('loan: exact confirmed target bypasses pending filters and persists after a write',async()=>{
 const calls=[];const {vm}=mount(cases[0],{getAffairsLoans:async q=>{calls.push(q);return {items:[{loanId:q.recordId,status:'CONFIRMED'}],total:1}},actAffairsLoan:async()=>({})})
 vm.focusId='9007199254740993';await vm.load();assert.deepEqual(calls[0],{recordId:'9007199254740993',page:1,pageSize:1})
 await vm.runAction(vm.items[0],{action:'CONFIRM',version:2});assert.deepEqual(calls[1],calls[0])
})
test('loan: malformed target cannot read an unrelated queue',async()=>{
 const {vm}=mount(cases[0],{getAffairsLoans:()=>assert.fail('invalid target')});vm.focusId='NaN';await vm.load();assert.equal(vm.state,'error');assert.match(vm.listError,/编号无效/)
})

test('work-study: hiring keeps the exact application visible after state changes',async()=>{
 const calls=[];const {vm}=mount(cases[2],{getWorkStudyRecords:async q=>{calls.push(q);return {items:[{recordId:q.recordId,status:'APPROVED'}],total:1}},actWorkStudy:async()=>({})})
 vm.focusId='9007199254740993';await vm.load();assert.deepEqual(calls[0],{recordId:'9007199254740993',page:1,pageSize:1})
 await vm.runAction(vm.records[0],'APPROVE','',false);assert.deepEqual(calls[1],calls[0])
})

test('work-study: malformed target cannot read an unrelated queue',async()=>{
 const {vm}=mount(cases[2],{getWorkStudyRecords:()=>assert.fail('invalid target')});vm.focusId='NaN';await vm.load();assert.equal(vm.state,'error');assert.match(vm.listError,/编号无效/)
})

test('work-study: a monthly history failure retains the exact onboard record and can retry',async()=>{
 let fail=true;const {vm}=mount(cases[2],{getWorkStudyRecords:async()=>({items:[{recordId:'2',status:'ONBOARD'}],total:1}),getWorkStudyMonthly:async id=>{assert.equal(id,'2');if(fail)throw new Error('考核读取失败');return {items:[{monthlyId:'3',subsidyAmount:'160.00'}]}}})
 vm.focusId='2';await vm.load();assert.equal(vm.records[0].recordId,'2');assert.equal(vm.state,'ready');assert.match(vm.historyError,/读取失败/)
 fail=false;await vm.load();assert.equal(vm.historyError,'');assert.equal(vm.monthlies[0].monthlyId,'3')
})
