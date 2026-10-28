import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
const ctx = { hasBatch: true, batchId: '9007199254741001', recordId: '9007199254741002', statusText: 'READY' }
const target = { id: '9007199254741003', positionId: '9007199254741003', companyId: '9007199254741004', companyName: '目标企业', title: '目标岗位', canSelect: true }
const returned = { id: '9007199254741005', version: 2, changeType: 'CHANGE_ENTERPRISE', status: 'REJECTED', reason: '原变更原因需要补充', reviewComment: '请补充沟通情况' }
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
function page(api = {}) {
  let generation = 1
  const calls = [], notices = []
  const deps = {
    currentSessionGeneration: () => generation, normalizeError: () => ({ text: '操作未完成，请核对后重试' }),
    toast: text => notices.push(text), uni: { stopPullDownRefresh() {} },
    studentApi: { getInternship: async () => ctx },
    studentInternshipChanges: async (...args) => { calls.push(['history', ...args]); return { items: [], hasMore: false } },
    studentInternshipChangeTargets: async (...args) => { calls.push(['targets', ...args]); return { items: [target], hasMore: true } },
    studentInternshipChangeApply: async body => { calls.push(['create', body]); return { id: 'new', version: 0, status: 'PENDING' } },
    studentInternshipChangeResubmit: async (id, body) => { calls.push(['resubmit', id, body]); return { id, version: 3, status: 'PENDING' } },
    studentInternshipChangeWithdraw: async (id, body) => { calls.push(['withdraw', id, body]); return { id, version: 3, status: 'WITHDRAWN' } }, ...api
  }
  const script = fs.readFileSync(new URL('../src/pages/student-internship/change/index.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const vm = component.data()
  for (const [key, method] of Object.entries(component.methods)) vm[key] = method.bind(vm)
  for (const [key, method] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: method.bind(vm) })
  vm.context = { ...ctx }; vm.pageState = 'ready'
  return { vm, component, calls, notices, logout: () => generation++ }
}

test('学生补正保留原单编号和原版本，两个变更类型都查询权威目标', async () => {
  const { vm, calls } = page()
  await vm.loadTargets(2)
  vm.edit(returned); await Promise.resolve()
  vm.selectTarget(target); vm.form.reason = '补充岗位安排与校企沟通情况'
  await vm.submit()
  const sent = calls.find(call => call[0] === 'resubmit')
  assert.equal(sent[1], returned.id)
  assert.deepEqual(sent[2], { batchId: ctx.batchId, internshipId: ctx.recordId, expectedVersion: 2, changeType: 'CHANGE_ENTERPRISE', reason: '补充岗位安排与校企沟通情况', targetPositionId: target.positionId })
  assert.equal(calls.filter(call => call[0] === 'create').length, 0)
  assert.deepEqual(calls.filter(call => call[0] === 'targets').map(call => call.slice(1, 4)), [[ctx.batchId, ctx.recordId, 'CHANGE_POSITION'], [ctx.batchId, ctx.recordId, 'CHANGE_ENTERPRISE']])
  assert.equal(vm.receipt.id, returned.id); assert.equal(vm.receipt.version, 3)
})

test('冲突和重复点击不丢草稿、不取新版本自动覆盖', async () => {
  const request = deferred()
  const { vm } = page({ studentInternshipChangeResubmit: () => request.promise })
  vm.edit(returned); await Promise.resolve(); vm.selectTarget(target)
  vm.form.reason = '已补充沟通情况等待教师复核'
  const sending = vm.submit(); await vm.submit()
  request.reject({ code: 409001, message: 'RAW_INTERNAL_CODE' }); await sending
  assert.equal(vm.editing.version, 2); assert.equal(vm.editing.id, returned.id)
  assert.equal(vm.form.reason, '已补充沟通情况等待教师复核'); assert.equal(vm.selectedTarget.positionId, target.positionId)
  assert.equal(vm.receipt, null); assert.ok(vm.formError.includes('原版本已保留')); assert.ok(!vm.formError.includes('RAW_INTERNAL_CODE'))
})

test('隐藏、换批次和换账号的迟到岗位与提交不污染新页面', async () => {
  const targetRead = deferred(), submit = deferred()
  const { vm, component, logout } = page({ studentInternshipChangeTargets: () => targetRead.promise, studentInternshipChangeApply: () => submit.promise })
  const reading = vm.loadTargets()
  component.onHide.call(vm); targetRead.resolve({ items: [target] }); await reading
  assert.deepEqual(vm.targets, [])
  vm.hidden = false; vm.selectTarget(target); vm.form.reason = '申请更换岗位安排并说明原因'
  const sending = vm.submit(); logout(); vm.context = { ...ctx, batchId: 'other' }; vm.form.reason = '新学校草稿'
  submit.resolve({ id: 'old', status: 'PENDING', version: 0 }); await sending
  assert.equal(vm.receipt, null); assert.equal(vm.form.reason, '新学校草稿')
})

test('岗位失败与不可选条件保持明确错误，分页不丢已选目标', async () => {
  const { vm } = page({ studentInternshipChangeTargets: async () => { throw Error('NETWORK_INTERNAL') } })
  vm.selectTarget(target); await vm.loadTargets(2)
  assert.ok(vm.targetError); assert.equal(vm.selectedTarget.positionId, target.positionId)
  vm.selectTarget({ ...target, id: 'blocked', canSelect: false }); assert.equal(vm.selectedTarget.positionId, target.positionId)
  assert.equal(vm.statusLabel('UNKNOWN_CODE'), '状态待核对')
})

test('自主实习与退岗提交不夹带旧目标编号', async () => {
  const { vm, calls } = page()
  vm.selectedTarget = target; vm.typeIndex = 2; vm.form = { reason: '申请转为自主联系实习安排', targetEnterpriseName: '自主企业', targetPositionName: '自主岗位' }
  await vm.submit()
  const body = calls.find(call => call[0] === 'create')[1]
  assert.equal(body.targetPositionId, undefined); assert.equal(body.targetEnterpriseName, '自主企业')
})

test('历史实习只读，未知主记录状态不显示内部值', async () => {
  const { vm, calls } = page()
  vm.context.historyMode = true; vm.form.reason = '历史记录不应提交新变更'; vm.selectTarget(target)
  vm.edit(returned); await vm.submit(); await vm.withdraw(returned)
  assert.equal(vm.editing, null); assert.equal(calls.length, 0)
  vm.context.statusText = 'INTERNAL_UNKNOWN'; assert.equal(vm.recordStatusLabel, '实习状态待核对')
})
