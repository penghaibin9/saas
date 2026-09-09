import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
const script = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipMatchListView.vue', import.meta.url), 'utf8')).descriptor.script.content.replace(/^import[^\n]*\n/gm, '').replace(/ {2}components: \{[^\n]*\n/, '').replace('export default', 'return')
function view(api = {}, permissions = ['internship.match.intention.view', 'internship.match.result.view', 'internship.match.conflict.view', 'internship.match.export']) {
  const store = { selectedBatchId: '7', withBatchQuery(q) { return { ...q, batchId: this.selectedBatchId } } }
  const def = new Function('matchApi', 'canCode', 'useInternshipBatchStore', 'toast', script)(api, (ctx, code) => ctx.permissionPatterns.includes(code), () => store, { error() {}, success() {} })
  const calls = []
  const vm = { ...def.data(), ctx: { permissionPatterns: permissions }, $route: { path: '/admin/internship/match', query: { panel: 'manual', batchId: '7', keyword: '测试', page: '3' } }, $router: { push: q => calls.push(q), replace: q => calls.push(q), resolve: q => ({fullPath: q.path + '?' + new URLSearchParams(q.query).toString()}) } }
  for (const [key, fn] of Object.entries(def.methods)) vm[key] = fn.bind(vm)
  for (const [key, val] of Object.entries(def.computed)) Object.defineProperty(vm, key, typeof val === 'function' ? { get: () => val.call(vm) } : { get: () => val.get.call(vm), set: value => val.set.call(vm, value) })
  return { vm, calls, store }
}
test('matching form opens and returns with its batch and search context', () => {
  const { vm, calls } = view(); vm.manualVisible = true
  assert.equal(calls[0].query.form, 'manual'); assert.equal(calls[0].query.keyword, '测试')
  vm.$route.query = calls[0].query; assert.equal(vm.formTitle, '手动匹配'); vm.closeForm()
  assert.equal(calls[1].query.form, undefined); assert.equal(calls[1].query.page, '3'); assert.equal(calls[1].query.batchId, '7')
})
test('matching deep link restores list filters and page', () => {
  const { vm } = view(); vm.load = () => {}; vm.applyPanel('manual')
  assert.equal(vm.page, 3); assert.equal(vm.filters.keyword, '测试'); assert.equal(vm.activePanel, 'manual')
})
test('a late matching list response cannot replace the current list', async () => {
  let resolve; const pending = new Promise(done => { resolve = done })
  const { vm } = view({ getResults: () => pending }); vm.activePanel = 'manual'
  const loading = vm.load(); vm.loadTicket++; vm.rows = [{ id: 'current' }]
  resolve({ code: 0, data: { list: [{ id: 'old' }], total: 1 } }); await loading
  assert.equal(vm.rows[0].id, 'current')
})

test('matching refresh, paging and export use displayed filters until search is submitted', async () => {
  const reads = [], exports = []
  const { vm, calls } = view({ getResults: async q => { reads.push(q); return {code:0,data:{list:[],total:0}} }, exportMatches: async q => { exports.push(q); return {code:0,data:{}} } })
  vm.activePanel = 'results'; vm.appliedFilters = { keyword:'已查询',status:'CONFIRMED',matchType:'' }; vm.filters = { ...vm.appliedFilters, keyword:'未查询' }
  await vm.load(); await vm.exportFn(); vm.turnPage(2)
  assert.equal(reads[0].keyword,'已查询'); assert.equal(exports[0].keyword,'已查询'); assert.equal(calls[0].query.keyword,'已查询')
  assert.equal(reads.length,1)
  vm.search(); assert.equal(calls[1].query.keyword,'未查询'); assert.equal(calls[1].query.page,1)
})

test('querying the same address refreshes once without a redundant route mutation', () => {
  const { vm, calls } = view(); let reads = 0; vm.load = () => { reads++ }
  vm.filters = {keyword:'测试',status:'',matchType:''}; vm.page = 1
  vm.$route.fullPath = vm.$router.resolve({path:vm.$route.path,query:{...vm.$route.query,...vm.filters,page:1}}).fullPath
  vm.search(); assert.equal(reads,1); assert.deepEqual(calls,[])
})

test('missing batch or read rights prevent queries and clear previous results', async () => {
  const { vm, store } = view({ getResults: () => assert.fail('forbidden query') }, [])
  vm.activePanel = 'results'; vm.rows = [{id:'old'}]; vm.total = 4; await vm.load()
  assert.match(vm.error,/无权/); assert.deepEqual(vm.rows,[]); assert.equal(vm.total,0)
  store.selectedBatchId = ''; await vm.load(); assert.match(vm.error,/选择实习批次/); assert.equal(vm.loading,false)
})

test('late export or list result is discarded after switching the active batch', async () => {
  let finishRead, finishExport
  const { vm, store } = view({getResults:()=>new Promise(r=>{finishRead=r}), exportMatches:()=>new Promise(r=>{finishExport=r})})
  vm.activePanel = 'results'; const read = vm.load(), exported = vm.exportFn(); store.selectedBatchId = '8'
  finishRead({code:0,data:{list:[{id:'old'}],total:1}}); finishExport({code:0,data:{contentBase64:'old'}})
  await read; assert.deepEqual(vm.rows,[]); assert.notEqual((await exported).code,0)
})

test('conflict view offers only supported filters and cannot export the unfiltered full ledger', async () => {
  const { vm } = view({exportMatches:()=>assert.fail('conflict filter is not supported by ledger export')})
  vm.activePanel = 'conflict'; assert.deepEqual(vm.filterFields.map(f=>f.key),['keyword']); assert.notEqual((await vm.exportFn()).code,0)
  vm.activePanel = 'results'; vm.ctx.permissionPatterns=[]; assert.equal(vm.canExport,false); assert.notEqual((await vm.exportFn()).code,0)
})

test('manual and batch queues default to their own method while explicit deep-link filters still win', () => {
  const { vm } = view(); vm.load = () => {}
  vm.applyPanel('manual'); assert.equal(vm.appliedFilters.matchType,'MANUAL')
  vm.applyPanel('batch'); assert.equal(vm.appliedFilters.matchType,'BATCH')
  vm.$route.query.matchType=''; vm.applyPanel('manual'); assert.equal(vm.appliedFilters.matchType,'')
  vm.$route.query.form='manual'; assert.equal(vm.canEditForm,false)
  vm.ctx.permissionPatterns.push('internship.match.manual'); assert.equal(vm.canEditForm,true)
})
