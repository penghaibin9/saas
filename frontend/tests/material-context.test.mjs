import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/modules/studentAffairs/views/MaterialOperationsView.vue', import.meta.url), 'utf8').replaceAll('\r', '')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

function createFixture() {
  return { acting: '', createValid: true, createVisible: true, bizContext: { bizId: '9007199254740993' },
    form: { bizType: 'FUNDING', bizId: '9007199254740993', itemCode: 'proof', itemName: '收入证明', requirementReason: '请补充收入证明', dueDate: '' },
    loadRequirements: async () => {} }
}

test('material creation preserves large IDs and distinguishes a saved record from a failed refresh', async () => {
  const create = method('createRequirement()', 'review('), vm = createFixture(), notices = []
  let payload, writes = 0
  vm.loadRequirements = async () => { throw new Error('offline') }
  await create.call(vm, { createRequirement: async data => { payload = data; writes++ } }, { success: text => notices.push(text), error: text => notices.push(text) })
  assert.equal(writes, 1)
  assert.equal(payload.bizId, '9007199254740993')
  assert.equal(payload.itemCode, 'PROOF')
  assert.equal(vm.form.bizId, '9007199254740993')
  assert.equal(vm.createVisible, false)
  assert.equal(vm.form.itemName, '')
  assert.match(notices.at(-1), /登记已成功.*刷新失败/)
})

test('failed material creation retains input and prevents duplicate in-flight requests', async () => {
  const create = method('createRequirement()', 'review('), vm = createFixture(), original = { ...vm.form }
  let reject, writes = 0
  const api = { createRequirement: () => { writes++; return new Promise((_, fail) => { reject = fail }) } }
  const toast = { error: () => {}, success: () => assert.fail('failed write cannot show success') }
  const first = create.call(vm, api, toast)
  await create.call(vm, api, toast)
  reject(new Error('conflict'))
  await first
  assert.equal(writes, 1)
  assert.deepEqual(vm.form, original)
  assert.equal(vm.createVisible, true)
  assert.equal(vm.acting, '')
})
function method(name, next) {
  const start = source.indexOf(`    async ${name}`)
  const end = source.indexOf(`\n    ${next}`, start)
  assert.ok(start >= 0 && end > start)
  return new AsyncFunction('affairsOperationsApi', 'toast', source.slice(source.indexOf('{', start) + 1, end).replace(/\n\x20{4}\},$/, ''))
}

test('funding context survives material entry and returns to funding instead of leave', () => {
  const contextBody = source.match(/applicationContext\(\) \{(.*) \},/)[1]
  const returnBody = source.match(/returnToApplication\(\) \{(.*) \},/)[1]
  const routes = [], vm = { $route: { query: { bizType: 'FUNDING', bizId: '41' } }, $router: { push: route => routes.push(route) } }
  vm.applicationContext = new Function(contextBody).call(vm)
  assert.deepEqual(vm.applicationContext, { bizType: 'FUNDING', bizId: '41' })
  new Function(returnBody).call(vm)
  assert.deepEqual(routes[0], { path: '/admin/student-affairs/funding', query: { recordId: '41' } })
})

test('legacy teacher material todo returns to its loaded application, never to the material ID', () => {
  const contextBody = source.match(/materialReturnContext\(\) \{([\s\S]*?)\n\x20{4}\},/)[1]
  const returnBody = source.match(/returnToApplication\(\) \{(.*) \},/)[1]
  const routes = [], vm = { applicationContext: {}, $route: { query: { recordId: '7' } }, requirements: [], $router: { push: r => routes.push(r) } }
  const resolve = () => new Function(contextBody).call(vm)
  assert.deepEqual(resolve(), {})
  vm.requirements = [{ requirementId: '8', bizType: 'FUNDING', bizId: '90' }]
  assert.deepEqual(resolve(), {})
  vm.requirements.push({ requirementId: '7', bizType: 'FUNDING', bizId: '41' })
  vm.materialReturnContext = resolve(); new Function(returnBody).call(vm)
  assert.deepEqual(routes, [{ path: '/admin/student-affairs/funding', query: { recordId: '41' } }])
  assert.deepEqual(vm.applicationContext, {})
})
test('switching material applications discards stale list and summary responses', async () => {
  const load = method('loadRequirements()', 'async loadBatches')
  const vm = { requirementsGeneration: 0, applicationContext: {bizType:'AID',bizId:'1'}, pagination:{page:1,pageSize:20}, selected:new Set(), summary:{} }
  const requests = []
  const api = { listCenter: params => new Promise(resolve => requests.push({params,resolve})) }
  const first = load.call(vm, api)
  vm.applicationContext = {bizType:'LEAVE',bizId:'1'}
  const second = load.call(vm, api)
  requests[1].resolve({items:[{requirementId:'leave'}],total:1,summary:{missing:1}})
  await second
  requests[0].resolve({items:[{requirementId:'aid'}],total:25,summary:{missing:25}})
  await first
  assert.equal(vm.requirements[0].requirementId, 'leave')
  assert.equal(vm.summary.total, 1)
  assert.equal(vm.summary.missing, 1)
  assert.deepEqual(requests.map(x=>x.params.bizType), ['AID','LEAVE'])
})
test('a delayed resolved student cannot refill the create form for another application', async () => {
  const resolve = method('applyRouteBizContext()', 'clearBizContext')
  const requests = []
  const vm = {contextGeneration:0, $route:{query:{bizType:'AID',bizId:'1'}}, form:{}, loadItemSuggestions:async()=>{}}
  const api = {resolveBizContext: params => new Promise(done => requests.push({params,done}))}
  const first = resolve.call(vm, api)
  vm.$route.query = {bizType:'AID',bizId:'2'}
  const second = resolve.call(vm, api)
  requests[1].done({bizType:'AID',bizId:'2'})
  await second
  requests[0].done({bizType:'AID',bizId:'1'})
  await first
  assert.equal(vm.form.bizId, '2')
  assert.equal(vm.bizContext.bizId, '2')
})

test('review validates the correction instructions, preserves them on conflict, and blocks double submission', async () => {
  const confirm = method('confirmReview()', 'async backfillLegacy')
  const vm = {acting:'',reviewTarget:{requirementId:'1',version:4},reviewAction:'RETURN',reviewReason:'短'}
  let reject, calls = 0
  const api = {reviewRequirement:(...args)=>{calls++;assert.deepEqual(args,['1','RETURN','请补充收入变化的具体原因',4]);return new Promise((_,no)=>{reject=no})}}
  await confirm.call(vm,api)
  assert.match(vm.reviewError,/至少5字/)
  vm.reviewReason='请补充收入变化的具体原因'
  const first=confirm.call(vm,api)
  await confirm.call(vm,api)
  reject(new Error('该材料已由其他老师处理，请刷新核对'));await first
  assert.equal(calls,1)
  assert.equal(vm.reviewReason,'请补充收入变化的具体原因')
  assert.match(vm.reviewError,/刷新核对/)
  assert.equal(vm.acting,'')
})
