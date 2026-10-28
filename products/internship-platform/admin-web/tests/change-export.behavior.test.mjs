import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/modules/internship/views/ChangeRequestListView.vue', import.meta.url), 'utf8')
function page(overrides = {}) {
  const scope = Object.fromEntries(['ModulePageShell','EmptyState','DualPaneWorkspace','AppStatusTag','AppConfirmDialog','AppDescriptionList','AppAuditTrail','AppPermissionButton','AppPagination','ActionReceipt','AppSearchBox','AppInlineAlert','AppButton','AppExportButton'].map(name => [name, {}]))
  const calls = [], store = { selectedBatchId: '9007199254740993001', withBatchQuery: q => ({ ...q, batchId: store.selectedBatchId }) }
  Object.assign(scope, { REJECT_CHANGE: [], emptyConflict: () => ({}), canCode: ctx => ctx.allowed,
    useInternshipBatchStore: () => store, internshipApi: {
      getChangeRequests: async p => { calls.push(['list',p]); return { code:0,data:{list:[],total:21} } },
      exportChangeRequests: async p => { calls.push(['export',p]); return {code:0,data:{filename:'台账.xlsx'}} }, ...overrides } })
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(scope), script)(...Object.values(scope))
  const vm = { ...component.data(), ctx:{allowed:true,ctxKey:'学校甲'}, $route:{query:{panel:'pending',keyword:'已查学生',page:'1'}}, $router:{replace:to=>{calls.push(['route',to.query]);return to}} }
  for (const [key,fn] of Object.entries(component.methods)) vm[key] = (...args) => fn.apply(vm,args)
  for (const [key,fn] of Object.entries(component.computed)) Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  return {vm,component,store,calls}
}

test('导出完整已应用条件，未搜索关键词不改变翻页或刷新范围', async()=>{
  const {vm,calls}=page();vm.filters.keyword='已查学生';await vm.load()
  vm.filters.keyword='尚未搜索';await vm.exportChanges()
  assert.deepEqual(calls.find(x=>x[0]==='export')[1],{batchId:'9007199254740993001',status:'PENDING',keyword:'已查学生'})
  vm.onPageChange({page:2});assert.equal(calls.at(-1)[1].keyword,'已查学生')
  await vm.load();assert.equal(calls.at(-1)[1].keyword,'已查学生')
  vm.search('新查询');assert.equal(calls.at(-1)[1].keyword,'新查询')
})

test('未成功加载、无读取权限、读取失败不能导出旧范围', async()=>{
  const {vm,calls}=page();await assert.rejects(()=>vm.exportChanges(),/加载/)
  await vm.load();vm.ctx.allowed=false
  await assert.rejects(()=>vm.exportChanges(),/权限/)
  assert.equal(calls.filter(x=>x[0]==='export').length,0)
  const failed=page({getChangeRequests:async()=>({code:1,message:'读取失败'})});await failed.vm.load()
  await assert.rejects(()=>failed.vm.exportChanges(),/失败/)
})

test('导出返回前切换学校或批次，拒绝下载旧范围结果', async()=>{
  for(const context of ['学校','批次']){
    let resolve;const {vm,store}=page({exportChangeRequests:()=>new Promise(r=>{resolve=r})})
    await vm.load();const pending=vm.exportChanges()
    if(context==='学校')vm.ctx.ctxKey='学校乙';else store.selectedBatchId='9007199254740993002'
    resolve({code:0,data:{filename:'旧台账.xlsx'}})
    await assert.rejects(()=>pending,/已变化/)
  }
})
