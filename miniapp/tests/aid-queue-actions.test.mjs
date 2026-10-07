import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/pages/teacher/affairs-review/index.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm, '').replace('export default', 'return')
function make(load, detail, uni = {}) {
  const api = { getAffairsAidPending: load, getAffairsAidDetail: detail, getAffairsFundingPending: load, getAffairsFundingDetail: detail }
  const component = new Function('teacherApi', 'affairsContractApi', 'affairsAppealApi', 'normalizeError', 'toast', 'uni', script)(api, {}, {}, () => ({}), () => {}, uni)
  const vm = { ...component.data(), ...component.methods }
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  return vm
}
const row = id => ({ applyId: String(id), version: 1, allowedActions: ['APPROVE'] })
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }

test('funding queue searches and pages on the server, preserving the submitted keyword', async () => {
  const calls = []
  const vm = make(async params => { calls.push(params); return {total:2, list:[{applicationId:String(params.page), version:1, allowedActions:['APPROVE']}]} })
  vm.kind = 'FUNDING_APPROVAL'; vm.keyword = ' 甲 '
  await vm.load(); vm.keyword = '未提交'; await vm.loadMore()
  assert.deepEqual(calls, [{page:1,pageSize:20,keyword:'甲'}, {page:2,pageSize:20,keyword:'甲'}])
  assert.deepEqual(vm.list.map(x => x.applicationId), ['1','2'])
  assert.equal(vm.total, 2)
})

test('funding notification loads the original handled application without a queue fallback', async () => {
  const vm = make(() => assert.fail('must not read a replacement queue'), async id => ({applicationId:id, status:'RETURNED', version:4, allowedActions:[]}))
  vm.kind='FUNDING_APPROVAL'; vm.focusId='121'
  await vm.load()
  assert.equal(vm.title, '奖助申请办理'); assert.equal(vm.expandedId, '121')
  assert.equal(vm.list[0].applicationId, '121'); assert.equal(vm.canAction(vm.list[0], 'APPROVE'), false)
})

test('funding notification rejects mismatched detail instead of displaying another record', async () => {
  const vm = make(() => assert.fail('must not substitute queue'), async () => ({applicationId:'other'}))
  vm.kind='FUNDING_APPROVAL'; vm.focusId='121'
  await vm.load()
  assert.equal(vm.state,'error'); assert.deepEqual(vm.list,[])
})

test('funding detail preserves masked amounts and never turns unknown approved amount into zero', () => {
  const vm=make(); vm.kind='FUNDING_APPROVAL'
  const lines=vm.detailLines({projectType:'SCHOLARSHIP', requestedAmount:'***', approvedAmount:null})
  assert.deepEqual(lines.find(x=>x.k==='标准金额（元）'), {k:'标准金额（元）',v:'***'})
  assert.equal(lines.some(x=>x.k==='批准金额（元）'),false)
})

test('load more retains the applied search, deduplicates rows, and does not mix an unsubmitted query', async () => {
  const calls = []
  const vm = make(async params => {
    calls.push(params)
    return { total: 3, list: params.page === 1 ? [row(1), row(2)] : [row(2), row(3)] }
  })
  vm.keyword = ' 张 '
  await vm.load()
  vm.keyword = '李'
  await vm.loadMore()
  assert.deepEqual(calls.map(x => [x.page, x.keyword, x.kind]), [[1, '张', 'AID_APPROVAL'], [2, '张', 'AID_APPROVAL']])
  assert.deepEqual(vm.list.map(x => x.applyId), ['1', '2', '3'])
  assert.equal(vm.total, 3)
  await vm.loadMore()
  assert.equal(calls.length, 2)
})

test('failed next page keeps usable rows and retries the same page without duplicate concurrent requests', async () => {
  const pending = deferred(), calls = []
  const vm = make(params => { calls.push(params.page); return params.page === 1 ? Promise.resolve({ total: 2, list: [row(1)] }) : pending.promise })
  await vm.load()
  const first = vm.loadMore()
  await vm.loadMore()
  pending.reject(new Error('offline'))
  await first
  assert.deepEqual(calls, [1, 2])
  assert.equal(vm.state, 'ready')
  assert.equal(vm.page, 1)
  assert.deepEqual(vm.list, [row(1)])
  assert.match(vm.moreError, /仍保留/)
  assert.equal(vm.loadingMore, false)
  await vm.loadMore()
  assert.deepEqual(calls, [1, 2, 2])
})

test('an old response cannot replace the newest search or clear its loading state', async () => {
  const old = deferred(), recent = deferred()
  const vm = make(params => params.keyword === '旧' ? old.promise : recent.promise)
  vm.keyword = '旧'; const a = vm.load()
  vm.keyword = '新'; const b = vm.load()
  old.resolve({ total: 1, list: [row('old')] }); await a
  assert.equal(vm.state, 'loading')
  recent.resolve({ total: 1, list: [row('new')] }); await b
  assert.deepEqual(vm.list, [row('new')])
  assert.equal(vm.state, 'ready')
})

test('a failed search remains an error, and adjustment queues use their distinct server filter', async () => {
  let query
  const vm = make(params => { query = params; return Promise.reject(new Error('offline')) })
  vm.kind = 'AID_ADJUST'
  await vm.load()
  assert.equal(query.kind, 'AID_ADJUST')
  assert.equal(vm.state, 'error')
  assert.equal(vm.canAction({ allowedActions: [] }, 'APPROVE'), false)
  assert.equal(vm.canAction({}, 'APPROVE'), false)
})

test('a notification opens its exact application beyond page one, including an already processed item', async () => {
  const vm = make(() => assert.fail('must not fall back to the first queue item'), async id => ({ ...row(id), status: 'APPROVED', allowedActions: [] }))
  vm.focusId = '101'
  await vm.load()
  assert.deepEqual(vm.list.map(x => x.applyId), ['101'])
  assert.equal(vm.expandedId, '101')
  assert.equal(vm.canAction(vm.list[0], 'APPROVE'), false)
  assert.equal(vm.state, 'ready')
})

test('an inaccessible notification target shows an error without substituting a different application', async () => {
  const vm = make(() => assert.fail('must not substitute a queue'), async () => { throw new Error('not allowed') })
  vm.focusId = '101'
  await vm.load()
  assert.equal(vm.state, 'error')
  assert.deepEqual(vm.list, [])
})

test('adjustment confirms the persisted target and retains the displayed version', async () => {
  let confirm = false
  const calls = []
  const vm = make(async () => ({ list: [] }), async id => ({ ...row(id), adjustment: { fromLabel: '一般困难', targetLabel: '特别困难', targetLevel: 'SPECIAL' } }), {
    showActionSheet() { assert.fail('An approver must not choose a different target') },
    showModal(options) { assert.match(options.content, /一般困难 → 特别困难/); options.success({ confirm }) }
  })
  vm.kind = 'AID_ADJUST'
  vm.reviewRequest = (...args) => { calls.push(args); return Promise.resolve() }
  await vm.chooseAdjustLevel(row(1))
  assert.deepEqual(calls, [])
  confirm = true
  await vm.chooseAdjustLevel(row(1))
  assert.equal(calls.length, 1)
  assert.equal(calls[0][5], 'SPECIAL')
  assert.equal(calls[0][3].version, 1)
})

test('adjustment stops before confirmation when the visible record is stale', async () => {
  const vm = make(async () => ({ list: [] }), async id => ({ ...row(id), version: 2 }), {
    showModal() { assert.fail('Stale target must not be confirmed') }
  })
  vm.kind = 'AID_ADJUST'
  vm.reviewRequest = () => assert.fail('must not submit stale record')
  await vm.chooseAdjustLevel(row(1))
  assert.equal(vm.acting, false)
})
