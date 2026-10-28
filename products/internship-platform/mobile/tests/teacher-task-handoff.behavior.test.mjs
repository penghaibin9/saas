import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

function page(kind, overrides = {}) {
  let generation = 1, modal
  const calls = [], redirects = [], context = {
    selectedBatchId: '1', batches: [{ id: '1', name: '甲批次' }, { id: '2', name: '乙批次' }],
    restore() {}, async load() {}, can: () => true,
    selectBatch(id) { if (!this.batches.some(row => row.id === String(id))) return false; this.selectedBatchId = String(id); return true }
  }
  const deps = {
    useInternshipContextStore: () => context, currentSessionGeneration: () => generation,
    normalizeError: e => ({ pageState: e.httpStatus === 403 ? 'forbidden' : 'error', text: e.message || '读取失败' }),
    teacherInternshipCheckinExemptions: async (...args) => { calls.push(args); return { items: [], hasMore: false } },
    teacherInternshipCheckinExemptionReview: async (...args) => calls.push(args),
    teacherInternshipApplications: async (...args) => { calls.push(args); return { items: [], hasMore: false } },
    teacherInternshipApplicationSummary: async () => ({}), teacherInternshipApplicationStudents: async () => ({}),
    teacherInternshipApplicationReview() {}, teacherInternshipChanges: async (...args) => { calls.push(args); return { items: [], hasMore: false } },
    teacherInternshipChangeReview() {}, openBusinessFile() {}, toast() {},
    uni: { showModal(value) { modal = value }, stopPullDownRefresh() {}, redirectTo(value) { redirects.push(value.url) } }, ...overrides
  }
  const filename = { exemption: 'checkin-exemption', application: 'internship-application', change: 'internship-change' }[kind]
  const source = fs.readFileSync(new URL(`../src/pages/teacher-internship/${filename}/index.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(deps), script)(...Object.values(deps)), vm = component.data()
  for (const [key, method] of Object.entries(component.methods)) vm[key] = (...args) => method.apply(vm, args)
  for (const [key, getter] of Object.entries(component.computed || {})) Object.defineProperty(vm, key, { get: () => getter.call(vm) })
  return { vm, component, calls, context, redirects, modal: () => modal, logout() { generation++ } }
}

for (const [kind, key] of [['exemption', 'exemptionId'], ['application', 'applicationId'], ['change', 'changeId']]) {
  test(`${kind} 待办使用原单批次和编号，不沿用上次批次`, async () => {
    const p = page(kind)
    await p.component.onLoad.call(p.vm, { batchId: '2', [key]: '9007199254740993' })
    assert.equal(p.context.selectedBatchId, '2')
    assert.deepEqual(p.calls[0], ['2', 1, 20, 'ALL', '9007199254740993'])
    assert.equal(p.vm.state, 'ready')
  })
}

test('免签甲批次迟到响应不能覆盖乙批次名单', async () => {
  let finish
  const p = page('exemption', { teacherInternshipCheckinExemptions: batch => batch === '1' ? new Promise(resolve => { finish = resolve }) : Promise.resolve({ items: [{ id: '乙原单' }], hasMore: false }) })
  const old = p.vm.load(); await new Promise(resolve => setImmediate(resolve))
  await p.vm.onBatch({ detail: { value: 1 } })
  finish({ items: [{ id: '甲原单' }], hasMore: true }); await old
  assert.equal(p.vm.batchId, '2'); assert.equal(p.vm.list[0].id, '乙原单'); assert.equal(p.vm.hasMore, false)
})

test('免签从待办手动切批次后刷新仍属于新批次，保留筛选并清除旧原单', async () => {
  const p = page('exemption')
  await p.component.onLoad.call(p.vm, { batchId:'1', exemptionId:'9007199254740993' })
  await p.vm.onBatch({ detail:{value:1} })
  assert.equal(p.vm.list,null)
  const target = new URL(p.redirects[0], 'https://local.invalid')
  assert.equal(target.searchParams.get('batchId'),'2'); assert.equal(target.searchParams.has('exemptionId'),false)
  const reentered=page('exemption')
  await reentered.component.onLoad.call(reentered.vm,Object.fromEntries(target.searchParams))
  assert.deepEqual(reentered.calls[0],['2',1,20,'ALL',''])
})

test('免签从原单回到本批次全部申请后刷新不会重新锁定旧待办', async () => {
  const p=page('exemption')
  await p.component.onLoad.call(p.vm,{batchId:'2',exemptionId:'5'})
  await p.vm.clearFocus()
  assert.deepEqual(p.redirects,['/pages/teacher-internship/checkin-exemption/index?batchId=2&status=PENDING'])
})

test('免签确认框打开后离页、撤权或切批次，不发送旧审核', async () => {
  for (const change of ['leave', 'permission', 'batch']) {
    const p = page('exemption'); await p.vm.load()
    const item = { id: '5', status: 'PENDING', version: 0 }; p.vm.list = [item]
    p.vm.review(item, 'APPROVE')
    if (change === 'leave') p.component.onHide.call(p.vm)
    if (change === 'permission') p.context.can = () => false
    if (change === 'batch') await p.vm.onBatch({ detail: { value: 1 } })
    await p.modal().success({ confirm: true, content: '核对通过' })
    assert.equal(p.calls.filter(call => call[0] === '5').length, 0)
  }
})

test('待办指向无权批次时明确拒绝，不展示缓存批次', async () => {
  const p = page('exemption')
  await p.component.onLoad.call(p.vm, { batchId: '9', exemptionId: '5' })
  assert.equal(p.vm.state, 'forbidden'); assert.equal(p.calls.length, 0); assert.equal(p.vm.list, null)
})

test('免签审核成功回读后释放本次锁，可以继续筛选办理', async () => {
  const p = page('exemption'); await p.vm.load()
  const item = { id: '5', version: 0, status: 'PENDING' }; p.vm.list = [item]
  p.vm.review(item, 'APPROVE'); await p.modal().success({ confirm: true, content: '已核对' })
  assert.equal(p.vm.actingId, ''); assert.equal(p.vm.state, 'ready')
  await p.vm.setStatus('APPROVED'); assert.equal(p.vm.status, 'APPROVED')
})

test('已办调岗展示本次冻结前后关系，不能用后来的当前岗位替代', () => {
  const p=page('change')
  const row={status:'APPROVED',currentEnterprise:'后来企业',currentPosition:'后来岗位',targetEnterpriseName:'目标企业',targetPositionName:'目标岗位',
    approvedHistory:{before:{enterpriseName:'原企业',positionName:'原岗位'},after:{enterpriseName:'目标企业',positionName:'目标岗位'}}}
  assert.equal(p.vm.relationship(row).before.positionName,'原岗位')
  assert.equal(p.vm.relationship(row).after.positionName,'目标岗位')
  assert.equal(p.vm.relationship({...row,approvedHistory:null}),null)
  assert.equal(p.vm.relationship({...row,status:'PENDING'}).before.positionName,'后来岗位')
})
