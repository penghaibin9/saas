import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { formatDateTime } from '../src/utils/format.js'
import { normalizeError } from './request-module.mjs'

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const original = { id: '9007199254741005', batchId: '18', version: 3, status: 'PENDING', studentName: '合成学生', evidenceFileId: '', evidenceRequired: false }
test('多级请假中间通过只提示交接，不冒充最终请假生效', async () => {
  const { vm,notices }=page({teacherInternshipLeaveReview:async()=>({id:original.id,version:4,status:'PENDING',statusLabel:'审批中'})})
  vm.review({kind:'leave',item:original,action:'APPROVE'})
  await vm.submitReview()
  assert.equal(vm.receipt.pendingNext,true)
  assert.equal(vm.receipt.actionLabel,'本级通过，已交下一级')
  assert.equal(notices.at(-1),'本级通过，已交下一级')
})

test('无补卡查看权限时默认进入有权请假类别，显式选择仍显示原权限说明',async()=>{
  const p=page();p.vm.context.can=permission=>!permission.startsWith('internship.makeup.')
  await p.vm.load();assert.equal(p.vm.tab,'leave');assert.match(p.vm.sourceErrors.makeup,/无权查看/)
  p.vm.selectTab('makeup');await p.vm.load();assert.equal(p.vm.tab,'makeup');assert.match(p.vm.sourceErrors.makeup,/无权查看/)
})
function page(api = {}) {
  let generation = 1
  const calls = [], notices = []
  const context = { selectedBatchId: '18', batches: [{ id: '18', name: '甲批次' }, { id: '19', name: '乙批次' }],
    can: () => true, restore() {}, async load() {}, selectBatch(id) { this.selectedBatchId = String(id) } }
  const deps = { InternshipApprovalCard: {}, normalizeError, formatDateTime, currentSessionGeneration: () => generation, useInternshipContextStore: () => context,
    toast: text => notices.push(text),
    teacherInternshipMakeups: async () => ({ items: [] }),
    teacherInternshipLeaves: async batch => { calls.push(['leaves', batch]); return { items: [original], hasMore: false } },
    realRequest: async (path, options) => { calls.push(['request', path, options]); return path.includes('/overdue') ? { list: [] } : { ...original, batchId: '19' } },
    teacherInternshipLeaveReview: async (id, batch, body) => { calls.push(['review', id, batch, body]); return { id, version: body.expectedVersion + 1, statusLabel: '已通过' } },
    teacherInternshipMakeupReview: async () => ({}),
    openBusinessFile: async () => {}, teacherInternshipMakeupEvidenceViewed: async () => ({}),
    teacherInternshipLeaveEvidenceViewed: async (id, body) => { calls.push(['viewed', id, body]); return { id, version: body.expectedVersion, evidenceFileId: body.evidenceFileId } }, ...api }
  const source = fs.readFileSync(new URL('../src/pages/teacher-internship/internship-approval/ApprovalCore.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(deps), source)(...Object.values(deps))
  const vm = component.data()
  for (const [key, method] of Object.entries(component.methods)) vm[key] = method.bind(vm)
  for (const [key, method] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: method.bind(vm) })
  vm.batchId = '18'; vm.state = 'ready'; vm.batches = context.batches
  return { vm, context, calls, notices, component, logout: () => generation++ }
}

test('退回补正必须有具体原因，并提交独立动作和原版本', async () => {
  const {vm,calls}=page({teacherInternshipLeaveReview:async(id,batch,body)=>{
    calls.push(['correction',id,batch,body]); return {id,version:body.expectedVersion+1,status:'NEEDS_REVISION',statusLabel:'已退回，请补正'}
  }})
  vm.review({kind:'leave',item:original,action:'REQUEST_CHANGES'})
  vm.reviewDraft.comment='短'; await vm.submitReview(); assert.equal(calls.length,0)
  vm.reviewDraft.comment='请补充具体请假事由'; await vm.submitReview()
  assert.equal(calls[0][3].action,'REQUEST_CHANGES'); assert.equal(calls[0][3].expectedVersion,original.version)
  assert.equal(vm.receipt.actionLabel,'已退回补正，等待学生修改重交')
})

test('教师请假与返岗时间按设备时区显示，类型缺失不透出内部枚举', () => {
  const oldTimezone = process.env.TZ
  process.env.TZ = 'Asia/Shanghai'
  try {
    const source = fs.readFileSync(new URL('../src/pages/teacher-internship/internship-approval/ApprovalCard.vue', import.meta.url), 'utf8')
      .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
    const component = new Function('formatDateTime', source)(formatDateTime)
    assert.equal(component.methods.formatTime('2026-10-06T04:38:00Z'), '2026-10-06 12:38')
    assert.equal(page().vm.formatTime('2026-10-06T04:38:00Z'), '2026-10-06 12:38')
    assert.equal(component.computed.kindLabel.call({ kind: 'leave', item: { leaveType: 'PRIVATE_ENUM', days: 3 } }), '请假类型待核对 · 3天')
  } finally { if (oldTimezone === undefined) delete process.env.TZ; else process.env.TZ = oldTimezone }
})

test('返岗分页追加而不重复精确深链原单，旧分页不能覆盖刷新或解除新加载锁', async () => {
  const old = deferred(), next = deferred(); let calls = 0
  const { vm } = page({ realRequest: () => (++calls === 1 ? old : next).promise })
  vm.tab = 'overdue'; vm.overdues = [{ ...original, status: 'RETURNED' }]; vm.overdueHasMore = true
  const stale = vm.loadMore()
  vm.loadSeq++; vm.loadingMore = false
  const current = vm.loadMore()
  old.resolve({ list: [{ ...original, id: 'stale' }], hasMore: false }); await stale
  assert.equal(vm.loadingMore, true); assert.equal(vm.overdues.length, 1)
  next.resolve({ list: [original, { ...original, id: 'other' }], hasMore: false }); await current
  assert.deepEqual(vm.overdues.map(item => item.id), [original.id, 'other'])
  assert.equal(vm.overduePage, 2); assert.equal(vm.overdueHasMore, false); assert.equal(vm.loadingMore, false)
})

test('补卡来源拒绝不阻断授权请假，失败来源不冒充零待办', async () => {
  const { vm } = page({ teacherInternshipMakeups: async () => { throw { code: 'NO_PERMISSION' } } })
  await vm.load()
  assert.equal(vm.state, 'ready'); assert.equal(vm.leaves[0].id, original.id)
  assert.ok(vm.sourceErrors.makeup); assert.equal(vm.sourceErrors.leave, '')
  assert.equal(vm.tabOptions.find(x => x.key === 'makeup').count, '—')
  vm.review({ kind: 'makeup', item: original, action: 'REJECT' })
  assert.equal(vm.reviewDraft.visible, false)
})

test('待办通过权威单据解析实际批次，分页外原单仍可定位', async () => {
  const { vm, context, calls } = page({ teacherInternshipLeaves: async () => ({ items: [], hasMore: true }) })
  vm.focusId = original.id; vm.tab = 'leave'
  await vm.load()
  assert.equal(context.selectedBatchId, '19'); assert.equal(vm.batchId, '19')
  assert.equal(vm.leaves[0].id, original.id)
  assert.ok(calls.some(c => c[1]?.endsWith('/leaves/' + original.id)))
})

test('冲突保持原单旧版本与意见，回读后必须明确核对才可继续', async () => {
  let writes = 0
  const latest = { ...original, version: 9 }
  const { vm } = page({ teacherInternshipLeaveReview: async () => { writes++; throw { code: 1, bizCode: 'APPROVAL_VERSION_CONFLICT', httpStatus: 409 } }, realRequest: async () => latest })
  vm.review({ kind: 'leave', item: original, action: 'REJECT' }); vm.reviewDraft.comment = '请补充合成测试的证明材料'
  await vm.submitReview()
  assert.equal(vm.reviewDraft.item.version, 3); assert.equal(vm.reviewDraft.latest.version, 9)
  assert.equal(vm.reviewDraft.conflicted, true); assert.equal(vm.reviewDraft.comment, '请补充合成测试的证明材料')
  await vm.submitReview(); assert.equal(writes, 1)
  vm.adoptReview(); assert.equal(vm.reviewDraft.item.version, 9); assert.equal(vm.reviewDraft.conflicted, false)
})

test('隐藏后的审批回执与旧解锁不污染再次显示的新操作', async () => {
  const old = deferred(), current = deferred(); let writes = 0
  const { vm } = page({ teacherInternshipLeaveReview: async () => (++writes === 1 ? old.promise : current.promise) })
  vm.review({ kind: 'leave', item: original, action: 'REJECT' }); vm.reviewDraft.comment = '请补充证明的合成测试'
  const first = vm.submitReview(); vm.pause(); vm.hidden = false
  vm.review({ kind: 'leave', item: original, action: 'REJECT' }); vm.reviewDraft.comment = '第二次核对证明的合成测试'
  const second = vm.submitReview()
  old.resolve({ id: original.id, version: 4, statusLabel: '已驳回' }); await first
  assert.equal(vm.receipt, null); assert.equal(vm.reviewSubmitting, true)
  current.resolve({ id: original.id, version: 4, statusLabel: '已驳回' }); await second
  assert.equal(vm.receipt.id, original.id); assert.equal(vm.reviewSubmitting, false)
})

test('证明留痕绑定刚查看的版本和附件，换材料后不能复用旧已查看状态', async () => {
  const { vm, calls } = page()
  const item = { ...original, evidenceFileId: '101' }
  await vm.viewEvidence({ kind: 'leave', item })
  assert.deepEqual(calls.find(c => c[0] === 'viewed').slice(1), [original.id, { batchId: '18', expectedVersion: 3, evidenceFileId: '101' }])
  assert.equal(vm.isEvidenceViewed('leave', item), true)
  assert.equal(vm.isEvidenceViewed('leave', { ...item, version: 4, evidenceFileId: '102' }), false)
})

test('预览期间换账号不得写查看留痕', async () => {
  const preview = deferred()
  const { vm, calls, logout } = page({ openBusinessFile: async () => preview.promise })
  const request = vm.viewEvidence({ kind: 'leave', item: { ...original, evidenceFileId: '101' } })
  logout(); preview.resolve(); await request
  assert.equal(calls.filter(c => c[0] === 'viewed').length, 0)
})

test('销假冲突不自动采纳新版，也不能凭保留说明再次写入', async () => {
  const latest = { ...original, status: 'RETURNED', version: 9 }
  let writes = 0
  const { vm } = page({ realRequest: async (path, options) => {
    if (options?.method === 'POST') { writes++; throw { code: 1, bizCode: 'DATA_CONFLICT', httpStatus: 400 } }
    return latest
  } })
  vm.openReturn({ ...original, status: 'RETURNED' }); vm.returnDraft.note = '已核实合成测试返岗'
  await vm.submitReturn()
  assert.equal(vm.returnDraft.item.version, 3); assert.equal(vm.returnDraft.latest.version, 9)
  await vm.submitReturn(); assert.equal(writes, 1)
  vm.adoptReturn(); assert.equal(vm.returnDraft.item.version, 9)
})

test('第二页请假原单冲突直接读取原编号，不把列表外记录误认为已办结', async () => {
  const calls = [], latest = { ...original, version: 12 }
  const { vm } = page({ teacherInternshipLeaveReview: async () => { throw { code: 'DATA_CONFLICT' } },
    teacherInternshipLeaves: async () => ({ items: [] }), realRequest: async path => { calls.push(path); return latest } })
  vm.leavePage = 2; vm.leaves = [original]
  vm.review({ kind: 'leave', item: original, action: 'REJECT' }); vm.reviewDraft.comment = '请补充证明原单'
  await vm.submitReview()
  assert.equal(vm.leavePage, 2); assert.equal(vm.reviewDraft.latest.version, 12)
  assert.deepEqual(calls, [`/mobile/teacher/internship/context/leaves/${original.id}?batchId=18`])
  vm.adoptReview(); assert.equal(vm.reviewDraft.item.version, 12); assert.equal(vm.leaves[0].version, 12)
})

test('已确认返岗和原单回读失败都不能采用新版本继续写，核实输入保留', async () => {
  for (const failed of [false, true]) {
    const { vm } = page({ realRequest: async (path, options) => {
      if (options?.method === 'POST') throw { code: 'DATA_CONFLICT' }
      if (failed) throw { message: '当前原单暂不可读取' }
      return { ...original, status: 'RETURNED', version: 8, returnAcknowledged: true }
    } })
    vm.overduePage = 2; vm.overdues = [{ ...original, status: 'RETURNED' }]
    vm.openReturn(vm.overdues[0]); vm.returnDraft.note = '已核实返岗原说明'; await vm.submitReturn()
    assert.equal(vm.overduePage, 2); assert.equal(vm.returnDraft.note, '已核实返岗原说明')
    vm.adoptReturn(); assert.equal(vm.returnDraft.conflicted, true); assert.equal(vm.returnDraft.item.version, 3)
    assert.ok(vm.returnDraft.error.includes(failed ? '暂不可读取' : '已办结'))
  }
})

test('冲突回读失败后可保留原意见和旧版本重读，明确采用前不能再次提交', async () => {
  for (const kind of ['review', 'return']) {
    let reads = 0, writes = 0
    const latest = { ...original, version: 12, status: kind === 'return' ? 'RETURNED' : 'PENDING' }
    const { vm } = page({ teacherInternshipLeaveReview: async () => { writes++; throw { code: 'DATA_CONFLICT' } },
      realRequest: async (_path, options) => {
        if (options?.method === 'POST') { writes++; throw { code: 'DATA_CONFLICT' } }
        if (++reads === 1) throw { message: '网络暂不可用' }
        return latest
      } })
    const key = kind === 'return' ? 'returnDraft' : 'reviewDraft', input = kind === 'return' ? 'note' : 'comment'
    if (kind === 'return') vm.openReturn(latest)
    else vm.review({ kind: 'leave', item: original, action: 'REJECT' })
    const oldVersion = vm[key].item.version
    vm[key][input] = '保留原核实输入'; await vm[kind === 'return' ? 'submitReturn' : 'submitReview']()
    assert.equal(vm[key].latest, null); assert.ok(vm[key].error.includes('网络'))
    await vm.rereadConflict(kind)
    assert.equal(vm[key].latest.version, 12); assert.equal(vm[key].item.version, oldVersion)
    assert.equal(vm[key][input], '保留原核实输入'); assert.equal(vm[key].conflicted, true)
    await vm[kind === 'return' ? 'submitReturn' : 'submitReview'](); assert.equal(writes, 1)
    vm[kind === 'return' ? 'adoptReturn' : 'adoptReview']()
    assert.equal(vm[key].item.version, 12); assert.equal(vm[key][input], '保留原核实输入')
    assert.equal(vm[key].conflicted, false)
  }
})

test('取消后重读的新草稿不会被旧响应覆盖或解锁，重复重读只发一次', async () => {
  for (const kind of ['review', 'return']) {
    const old = deferred(), next = deferred(); let reads = 0
    const { vm } = page({ realRequest: () => (++reads === 1 ? old : next).promise })
    const key = kind === 'return' ? 'returnDraft' : 'reviewDraft'
    const open = () => {
      if (kind === 'return') vm.openReturn({ ...original, status: 'RETURNED' })
      else vm.review({ kind: 'leave', item: original, action: 'REJECT' })
      vm[key].conflicted = true
    }
    open(); const first = vm.rereadConflict(kind)
    await vm.rereadConflict(kind); assert.equal(reads, 1)
    vm[kind === 'return' ? 'closeReturn' : 'closeReview'](); open()
    const current = vm.rereadConflict(kind)
    old.resolve({ ...original, version: 8 }); await first
    assert.equal(vm[key].reading, true); assert.equal(vm[key].latest, null)
    next.resolve({ ...original, version: 9 }); await current
    assert.equal(vm[key].reading, false); assert.equal(vm[key].latest.version, 9)
  }
})

test('冲突回读中隐藏再恢复可保留输入继续读取，旧请求不能覆盖新锁或新原单', async () => {
  for (const kind of ['review', 'return']) {
    const old = deferred(), next = deferred(); let reads = 0
    const { vm } = page({ realRequest: () => (++reads === 1 ? old : next).promise })
    const key = kind === 'return' ? 'returnDraft' : 'reviewDraft', input = kind === 'return' ? 'note' : 'comment'
    if (kind === 'return') vm.openReturn({ ...original, status: 'RETURNED' })
    else vm.review({ kind: 'leave', item: original, action: 'REJECT' })
    vm[key].conflicted = true; vm[key][input] = '隐藏后保留原说明'
    const first = vm.rereadConflict(kind); vm.pause()
    assert.equal(vm[key].reading, false); assert.equal(vm[key][input], '隐藏后保留原说明')
    vm.hidden = false; const current = vm.rereadConflict(kind)
    old.resolve({ ...original, version: 8 }); await first
    assert.equal(vm[key].reading, true); assert.equal(vm[key].latest, null)
    next.resolve({ ...original, version: 9 }); await current
    assert.equal(vm[key].reading, false); assert.equal(vm[key].latest.version, 9)
    assert.equal(vm[key].item.version, original.version); assert.equal(vm[key].conflicted, true)
    assert.equal(vm[key][input], '隐藏后保留原说明')
  }
})

test('暂停页面时迟到队列不覆盖数据，父页面确实转发隐藏与显示', async () => {
  const read = deferred()
  const { vm } = page({ teacherInternshipLeaves: async () => read.promise })
  const pending = vm.load(); await Promise.resolve(); await Promise.resolve()
  vm.pause(); read.resolve({ items: [{ ...original, id: 'late' }] }); await pending
  assert.equal(vm.leaves.length, 0)
  const source = fs.readFileSync(new URL('../src/pages/teacher-internship/internship-approval/index.vue', import.meta.url), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '').replace('export default', 'return')
  const component = new Function('InternshipApprovalCore', source)({})
  const calls = [], shell = { $refs: { core: { pause: () => calls.push('pause'), resume: () => calls.push('resume') } } }
  component.onHide.call(shell); component.onShow.call(shell); component.onUnload.call(shell)
  assert.deepEqual(calls, ['pause', 'resume', 'pause'])
})
