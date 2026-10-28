import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { selectionScope, selectionScopeBody, selectionScopePath } from '../../shared/internshipSelectionScope.mjs'

test('教师学生档案账号状态显示中文，未知值不直接显示内部代码', () => {
  const source = fs.readFileSync(new URL('../src/pages/teacher-internship/internship-students/detail.vue', import.meta.url), 'utf8')
  const getter = new Function(source.match(/accountStatusLabel\(\) \{(.*?)\}/)[1])
  assert.equal(getter.call({ account: { accountStatus: 'ACTIVE' } }), '已启用')
  assert.equal(getter.call({ account: { accountStatus: 'UNKNOWN_INTERNAL_STATUS' } }), '状态待核对')
  assert.equal(getter.call({ account: null }), '—')
})

test('学校结果入口保留原志愿大整数编号及版本，未就绪或无效编号不能导航', async () => {
  const modelSource = fs.readFileSync(new URL('../src/modules/internshipVolunteerModel.js', import.meta.url), 'utf8')
  const { normalizeMobileVolunteerGroup } = await import('data:text/javascript;base64,' + Buffer.from(modelSource).toString('base64'))
  const source = fs.readFileSync(new URL('../src/pages/student-internship/enterprises/index.vue', import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*/gm, '').replace('export default', 'return')
  const calls = [], component = new Function('uni', source)({ navigateTo: row => calls.push(row.url) })
  const vm = { group: normalizeMobileVolunteerGroup({ id: '9007199254740993111', version: 8 }), volunteerState: 'ready', volunteerBusy: false }
  component.methods.openResult.call(vm)
  assert.deepEqual(calls, ['/pages/student-internship/volunteer-result/index?groupId=9007199254740993111&groupVersion=8'])
  for (const id of [null, '0', '1&groupId=2', 9007199254740992]) { vm.group.id = id; component.methods.openResult.call(vm) }
  vm.group.id = '1'; vm.volunteerState = 'error'; component.methods.openResult.call(vm)
  vm.volunteerState = 'ready'; vm.volunteerBusy = true; component.methods.openResult.call(vm)
  assert.equal(calls.length, 1)
})

test('首页按批次首次进入选岗，原招聘季链接仍须完整且批次不得被提交内容覆盖', () => {
  const batch = '9007199254740993111'
  assert.deepEqual(selectionScope({ batchId: batch }), { batchId: batch })
  assert.equal(selectionScopePath('/catalog/context', selectionScope({ batchId: batch })), `/catalog/context?batchId=${batch}`)
  assert.throws(() => selectionScopeBody({ batchId: '2' }, { batchId: batch }), /不一致/)
  for (const scope of [{ batchId: batch, campaignId: '2' }, { recordId: '3' }, { batchId: true }, { batchId: '0' }]) {
    assert.throws(() => selectionScope(scope), /定位不完整/)
  }
  assert.deepEqual(selectionScope({ batchId: batch, campaignId: '2', recordId: '3' }), { batchId: batch, campaignId: '2', recordId: '3' })
})

test('首次选岗读取成功后，后续名单及志愿请求固定服务端返回的完整招聘季', async () => {
  const source = fs.readFileSync(new URL('../src/pages/student-internship/enterprises/index.vue', import.meta.url), 'utf8')
  const body = source.match(/async loadContext\(\) \{([\s\S]*?)\n    \},/)[1]
  const calls = []
  const vm = { roundScope: { batchId: '18' }, detailSeq: 0, companySeq: 0, contextSeq: 0, requestSeq: 0, volunteerSeq: 0,
    catalogReady: true, selectionApi: { context: async () => ({ batchId: '18', campaignId: '2', recordId: '19' }) },
    loadPositions: async function () { calls.push({ ...this.roundScope }) }, loadVolunteers: async function () { calls.push({ ...this.roundScope }) } }
  const load = new Function('selectionScope', 'normalizeMobileSelectionContext', 'normalizeMobileVolunteerGroup', 'normalizeMobileMaterialPreview', `return async function () {${body}}`)(selectionScope, data => data, () => ({ slots: [] }), () => ({}))
  await load.call(vm)
  assert.equal(vm.contextState, 'ready')
  assert.deepEqual(calls, [{ batchId: '18', campaignId: '2', recordId: '19' }, { batchId: '18', campaignId: '2', recordId: '19' }])
})

test('档案页返回时隐藏的选岗页不抢发请求，重新显示才回读自己的原招聘季', () => {
  const source = fs.readFileSync(new URL('../src/pages/student-internship/enterprises/index.vue', import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*/gm, '').replace('export default', 'return')
  const component = new Function(source)()
  let reads = 0
  const vm = { roundScope: { batchId: '18', campaignId: '1', recordId: '18' }, contextSeq: 1, requestSeq: 1, volunteerSeq: 1, detailSeq: 1, companySeq: 1,
    $route: { path: '/pages/student-internship/enterprises/index', query: { batchId: '99' } }, loadContext() { reads++ } }
  component.onHide.call(vm)
  component.watch['$route.fullPath'].call(vm)
  assert.equal(reads, 0); assert.equal(vm.contextSeq, 2); assert.equal(vm.roundScope.batchId, '18')
  component.onShow.call(vm)
  assert.equal(reads, 1); assert.equal(vm.hidden, false)
})

test('学生材料缺口显示具体中文事项，不展示内部字段或未知数据文本', () => {
  const source = fs.readFileSync(new URL('../src/pages/student-internship/profile/index.vue', import.meta.url), 'utf8')
  const body = source.match(/blockerLabel\(item\) \{([\s\S]*?)\n    \},/)[1]
  const label = new Function('item', body).bind({ typeLabel: () => '实践材料' })
  assert.equal(label('PROFILE_NOT_READY'), '请先保存实习档案')
  assert.equal(label('profile.selfIntro'), '请填写自我介绍')
  assert.equal(label('profile.skillTags'), '请填写技能标签')
  assert.equal(label('itemType.PRACTICE'), '请添加实践材料')
  assert.equal(label('minItemCount.2'), '请至少添加2项实践或证明材料')
  assert.doesNotMatch(label({message:'INTERNAL_SECRET',code:'UNKNOWN'}), /INTERNAL|UNKNOWN/)
})

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const row = { id: '12', recordId: '34', internId: '34', studentName: '合成学生', applicationType: 'SELF_ARRANGED', evidenceFileId: 'file', version: 2, recordVersion: 3, recordVersionSnapshot: 3, status: 'PENDING', changeTypeLabel: '换单位' }

function volunteerPage(api = {}) {
  let generation = 1, modal
  const calls = [], routes = []
  const store = { selectedBatchId: '1', batches: [{ id: '1', name: '甲批次' }], async load() {}, can() { return true } }
  const detail = { id: '3', recordId: '9007199254740993111', batchId: '1', campaignId: '2', status: 'SUBMITTED', recordStatus: 'READY', version: 4, recordVersion: 5, studentName: '合成学生', volunteers: [] }
  const deps = {
    useInternshipContextStore: () => store, currentSessionGeneration: () => generation, openBusinessFile: async () => {},
    uni: { showModal: options => { modal = options }, redirectTo: options => routes.push(options.url), navigateTo: options => routes.push(options.url) },
    teacherVolunteerApi: { campaigns: async () => ({ items: [{ id: '2', name: '甲招聘季' }] }), detail: async () => ({ ...detail }), list: async () => ({ batchId: '1', items: [], total: 0 }), return: async (...args) => { calls.push(args); return { ...detail, status: 'NEEDS_REVISION' } }, ...api }
  }
  const source = fs.readFileSync(new URL('../src/pages/teacher-internship/internship-volunteers/index.vue', import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(deps), source)(...Object.values(deps))
  const vm = component.data()
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: fn.bind(vm) })
  vm.scope = { ...vm.scope, batchId: '1', campaignId: '2', groupId: '3' }
  return { vm, component, store, detail, calls, routes, modal: () => modal, switchAccount: () => generation++ }
}

test('正式招聘季旧确认框换账号或隐藏后不得提交', async () => {
  for (const change of ['account', 'hidden']) {
    const p = volunteerPage(); await p.vm.load(); p.vm.reason = '请补正岗位说明'
    const handling = p.vm.handle('return'); assert.ok(p.modal())
    if (change === 'account') p.switchAccount(); else p.component.onHide.call(p.vm)
    p.modal().success({ confirm: true }); await handling
    assert.equal(p.calls.length, 0); assert.equal(p.vm.busy, false)
  }
})

test('正式招聘季旧响应不能回填换账号后的学生，新会话读取失败清除旧上下文', async () => {
  const old = deferred(), p = volunteerPage({ detail: () => old.promise })
  const loading = p.vm.load(); for (let tick = 0; tick < 5; tick++) await Promise.resolve()
  p.switchAccount(); old.resolve({ ...p.detail }); await loading
  assert.equal(p.vm.detail, null)
  p.store.load = async () => { throw Error('新学校读取失败') }; await p.vm.load()
  assert.equal(p.vm.scope.batchId, ''); assert.equal(p.vm.scope.campaignId, ''); assert.equal(p.vm.campaigns.length, 0); assert.equal(p.vm.state, 'error')
})

test('正式招聘季旧提交结束不能释放新审核锁，取消恢复选择', async () => {
  const old = deferred(), p = volunteerPage({ return: () => old.promise })
  await p.vm.load(); p.vm.reason = '请补正岗位说明'; const handling = p.vm.handle('return')
  p.modal().success({ confirm: true }); await Promise.resolve()
  p.component.onHide.call(p.vm); await p.component.onShow.call(p.vm)
  p.vm.reason = '新的补正意见'; const next = p.vm.handle('return'); const nextModal = p.modal()
  old.resolve(p.detail); await handling; assert.equal(p.vm.busy, true)
  nextModal.success({ confirm: false }); await next; assert.equal(p.vm.busy, false)
})

test('正式招聘季退回冻结版本及意见，已审分类与学生档案沿原上下文', async () => {
  const p = volunteerPage(); await p.vm.load(); p.vm.reason = '请补正岗位说明'; const handling = p.vm.handle('return')
  p.vm.detail.version = 99; p.vm.detail.recordVersion = 99; p.vm.reason = '随后修改的意见'
  p.modal().success({ confirm: true }); await handling
  assert.equal(p.calls.length, 1); assert.equal(p.calls[0][1].expectedGroupVersion, 4); assert.equal(p.calls[0][1].expectedRecordVersion, 5); assert.equal(p.calls[0][1].reason, '请补正岗位说明')
  assert.ok(p.vm.filters.some(item => item.value === 'REVIEWED'))
  p.vm.openStudent(p.detail); assert.match(p.routes.at(-1), /id=9007199254740993111&batchId=1/)
})

test('统一填报统计说明两类待办，并定位具体招聘季', async () => {
  const p = page('application'); await p.vm.load()
  p.vm.summary = { totalStudents: 10, filledStudents: 10, unfilledStudents: 0, pendingReviewApplications: 1, pendingRecruitmentGroups: 2 }
  assert.match(p.vm.summaryConclusion, /1 条普通申请/); assert.match(p.vm.summaryConclusion, /2 组招聘季志愿/)
  p.vm.openVolunteers({ campaignId: '7' }); assert.match(p.routes.at(-1), /batchId=A&campaignId=7/)
})

test('学生原招聘季补正继续显示具体学校意见', async () => {
  const source = fs.readFileSync(new URL('../src/modules/internshipVolunteerModel.js', import.meta.url), 'utf8')
  const model = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
  assert.equal(model.normalizeMobileVolunteerGroup({ status: 'NEEDS_REVISION', revisionReason: '请补充岗位任务和清晰附件' }).revisionReason, '请补充岗位任务和清晰附件')
})
function page(kind = 'application', api = {}) {
  let generation = 1, modal
  const calls = [], messages = [], routes = []
  const store = { selectedBatchId: 'A', batches: [{ id: 'A', name: '甲批次' }, { id: 'B', name: '乙批次' }], restore() {}, async load() {}, can() { return true }, selectBatch(id) { this.selectedBatchId = id } }
  const deps = {
    useInternshipContextStore: () => store, currentSessionGeneration: () => generation,
    toast: value => messages.push(value), openBusinessFile: async () => {},
    uni: { showModal: value => { modal = value }, navigateTo: value => routes.push(value.url), stopPullDownRefresh() {} },
    teacherInternshipApplications: async () => ({ items: [{ ...row, status: 'PENDING_REVIEW' }], total: 1 }),
    teacherInternshipApplicationSummary: async () => ({ totalStudents: 1, filledStudents: 1 }),
    teacherInternshipApplicationStudents: async () => ({ items: [{ ...row }], total: 1 }),
    teacherInternshipChanges: async () => ({ items: [{ ...row }], total: 31, hasMore: true }),
    teacherInternshipApplicationReview: async (...args) => { calls.push(args); return { statusLabel: '已通过' } },
    teacherInternshipChangeReview: async (...args) => { calls.push(args); return { statusLabel: '已通过' } }, ...api
  }
  const source = fs.readFileSync(new URL(`../src/pages/teacher-internship/internship-${kind}/index.vue`, import.meta.url), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(deps), source)(...Object.values(deps))
  const vm = component.data()
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  for (const [name, fn] of Object.entries(component.computed)) Object.defineProperty(vm, name, { get: fn.bind(vm) })
  return { vm, component, store, calls, messages, routes, modal: () => modal, switchAccount: () => generation++ }
}

test('两页首批读取拒绝甲批次迟到结果，乙批次名单保持', async () => {
  for (const kind of ['application', 'change']) {
    const old = deferred()
    const name = kind === 'application' ? 'teacherInternshipApplications' : 'teacherInternshipChanges'
    const p = page(kind, { [name]: batch => batch === 'A' ? old.promise : Promise.resolve({ items: [{ id: 'B' }], total: 4 }) })
    const loading = p.vm.load(); await Promise.resolve()
    p.store.selectedBatchId = 'B'; await p.vm.load()
    old.resolve({ items: [{ id: 'A' }], total: 8 }); await loading
    assert.equal(p.vm.batchId, 'B'); assert.equal(p.vm.list[0].id, 'B'); assert.equal(p.vm.state, 'ready')
    if (kind === 'change') assert.equal(p.vm.total, 4)
  }
})

test('两页旧未审分页不得混入新已审分类', async () => {
  for (const kind of ['application', 'change']) {
    const old = deferred(), name = kind === 'application' ? 'teacherInternshipApplications' : 'teacherInternshipChanges'
    const p = page(kind, { [name]: async (batch, number, size, status) => number > 1 ? old.promise : { items: [{ id: status }], hasMore: true } })
    await p.vm.load(); const loading = p.vm.loadMore(); await p.vm.setReviewStatus('REVIEWED')
    old.resolve({ items: [{ id: 'old' }], hasMore: false }); await loading
    assert.deepEqual(p.vm.list.map(x => x.id), ['REVIEWED']); assert.equal(p.vm.page, 1); assert.equal(p.vm.loadingMore, false)
  }
})

test('已填切未填重新请求，旧请求不能覆盖或关闭新读取状态', async () => {
  const filled = deferred(), unfilled = deferred(), calls = []
  const p = page('application', { teacherInternshipApplicationStudents: (batch, state) => { calls.push(state); return state === 'FILLED' ? filled.promise : unfilled.promise } })
  await p.vm.load(); const old = p.vm.toggleStudentState('FILLED'); const next = p.vm.toggleStudentState('UNFILLED')
  assert.deepEqual(calls, ['FILLED', 'UNFILLED'])
  filled.resolve({ items: [{ id: 'old' }], total: 1 }); await old; assert.equal(p.vm.studentLoading, true)
  unfilled.resolve({ items: [{ id: 'new' }], total: 0 }); await next
  assert.equal(p.vm.studentRows[0].id, 'new'); assert.equal(p.vm.studentTotal, 0); assert.equal(p.vm.studentLoading, false)
})

test('名单读取失败明确可重试，不能当作成功的空名单', async () => {
  let fail = true
  const p = page('application', { teacherInternshipApplicationStudents: async () => { if (fail) throw Error('failed'); return { items: [{ ...row }], total: 1 } } })
  await p.vm.load(); await p.vm.toggleStudentState('FILLED')
  assert.match(p.vm.studentError, /读取失败/); assert.equal(p.vm.studentLoading, false)
  fail = false; await p.vm.loadStudentState(); assert.equal(p.vm.studentError, ''); assert.equal(p.vm.studentRows.length, 1)
})

test('旧审核确认框在换批次或换账号后不提交，两页相同', async () => {
  for (const kind of ['application', 'change']) for (const change of ['batch', 'account']) {
    const p = page(kind); await p.vm.load(); p.vm.review(p.vm.list[0], 'REJECT')
    assert.ok(p.modal()); if (change === 'batch') p.vm.batchId = 'B'; else p.switchAccount()
    await p.modal().success({ confirm: true, content: '请补充清晰申请证明' })
    assert.equal(p.calls.length, 0)
  }
})

test('审核确认携带打开时版本，取消后恢复批次选择', async () => {
  for (const kind of ['application', 'change']) {
    const p = page(kind); await p.vm.load(); const item = p.vm.list[0]; p.vm.review(item, 'REJECT')
    item.version = 999; item.recordVersion = item.recordVersionSnapshot = 999
    await p.modal().success({ confirm: true, content: '请补充清晰申请证明' })
    assert.equal(p.calls[0][1], 'A'); assert.equal(p.calls[0][2].expectedVersion, 2); assert.equal(p.calls[0][2].recordExpectedVersion, 3)
    p.vm.review({ ...row, status: kind === 'application' ? 'PENDING_REVIEW' : 'PENDING' }, 'REJECT')
    await p.modal().success({ confirm: false }); assert.equal(Boolean(p.vm.actingId || p.vm.acting), false)
  }
})

test('变更显示服务端全量31条，分类传给正式接口，已审不可重复审批', async () => {
  const statuses = [], p = page('change', { teacherInternshipChanges: async (batch, number, size, status) => { statuses.push(status); return { items: [{ ...row, status: status === 'REVIEWED' ? 'REJECTED' : 'PENDING' }], total: 31 } } })
  await p.vm.load(); assert.equal(p.vm.list.length, 1); assert.equal(p.vm.total, 31)
  await p.vm.setReviewStatus('REVIEWED'); assert.deepEqual(statuses, ['PENDING', 'REVIEWED']); p.vm.review(p.vm.list[0], 'APPROVE'); assert.equal(p.modal(), undefined)
})

test('变更冲突刷新并保留意见，不自动打开或重放，切批次清除旧回执', async () => {
  let reviews = 0
  const p = page('change', { teacherInternshipChangeReview: async () => { reviews++; throw { bizCode: 'DATA_CONFLICT' } } })
  await p.vm.load(); p.vm.review(p.vm.list[0], 'REJECT'); const original = p.modal()
  await original.success({ confirm: true, content: '请补充清晰申请证明' })
  assert.equal(reviews, 1); assert.equal(p.modal(), original); assert.equal(p.vm.conflictReceipt.comment, '请补充清晰申请证明')
  p.vm.lastReceipt = { statusLabel: '已通过' }; await p.vm.onBatch({ detail: { value: 1 } }); assert.equal(p.vm.lastReceipt, null); assert.equal(p.vm.conflictReceipt, null)
})

test('两页隐藏或换账号后的迟到结果不回填，重新展示能够加载', async () => {
  for (const kind of ['application', 'change']) {
    const old = deferred(), name = kind === 'application' ? 'teacherInternshipApplications' : 'teacherInternshipChanges'; let reads = 0
    const p = page(kind, { [name]: async () => ++reads === 1 ? old.promise : { items: [{ id: 'new' }], total: 1 } })
    const loading = p.vm.load(); await Promise.resolve(); p.component.onHide.call(p.vm); p.switchAccount()
    old.resolve({ items: [{ id: 'old' }] }); await loading; assert.equal(p.vm.list, null)
    await p.component.onShow.call(p.vm); assert.equal(p.vm.list[0].id, 'new')
  }
})

test('档案深链使用实习主档编号和原批次，免实习按钮使用业务名称', async () => {
  for (const kind of ['application', 'change']) {
    const p = page(kind); await p.vm.load(); p.vm.openStudent(row)
    assert.match(p.routes[0], /detail\?id=34&batchId=A$/)
    if (kind === 'application') { assert.equal(p.vm.approveLabel({ applicationType: 'EXEMPTION' }), '通过免实习申请'); assert.equal(p.vm.canApprove({ ...row, applicationType: 'EXEMPTION', evidenceFileId: '' }), false) }
  }
})

test('保留意见只回填原申请和原动作，旧会话取消不能解除新审核锁', async () => {
  for (const kind of ['application', 'change']) {
    const p = page(kind); await p.vm.load(); p.vm.review(p.vm.list[0], 'REJECT')
    await p.modal().success({ confirm: true, content: '短意见' })
    p.vm.review({ ...p.vm.list[0], id: 'other', studentName: '另一学生' }, 'REJECT'); assert.equal(p.modal().content, '')
    await p.modal().success({ confirm: false })
    p.vm.review(p.vm.list[0], 'APPROVE'); assert.equal(p.modal().content, '')
    const old = p.modal(); p.switchAccount(); await p.vm.load(); p.vm.review(p.vm.list[0], 'REJECT')
    assert.equal(Boolean(p.vm.actingId || p.vm.acting), true)
    await old.success({ confirm: false }); old.fail()
    assert.equal(Boolean(p.vm.actingId || p.vm.acting), true)
  }
})

test('冲突刷新等待期间切账号，旧意见不回填且旧完成不解除新审核锁', async () => {
  const delayed = deferred(); let reads = 0
  const p = page('change', {
    teacherInternshipChanges: async () => ++reads === 2 ? delayed.promise : { items: [{ ...row }], total: 1 },
    teacherInternshipChangeReview: async () => { throw { bizCode: 'DATA_CONFLICT' } }
  })
  await p.vm.load(); p.vm.review(p.vm.list[0], 'REJECT')
  const handling = p.modal().success({ confirm: true, content: '请补充清晰申请证明' })
  await Promise.resolve(); await Promise.resolve(); assert.equal(reads, 2)
  p.switchAccount(); await p.vm.load(); p.vm.review(p.vm.list[0], 'REJECT')
  delayed.resolve({ items: [{ id: 'old' }], total: 1 }); await handling
  assert.equal(p.vm.conflictReceipt, null); assert.equal(p.vm.acting, true); assert.equal(p.vm.list[0].id, row.id)
})

test('新会话读取失败不展示旧批次，上下文自动改批次清除旧回执和意见', async () => {
  for (const kind of ['application', 'change']) {
    const p = page(kind); await p.vm.load(); p.vm.lastReceipt = { studentName: '旧学生' }; p.vm.reviewDraft = p.vm.conflictReceipt = { comment: '旧意见' }
    p.store.selectedBatchId = 'B'; await p.vm.load(); assert.equal(p.vm.lastReceipt, null)
    assert.equal(kind === 'application' ? p.vm.reviewDraft : p.vm.conflictReceipt, null)
    p.switchAccount(); p.store.batches = []; p.store.selectedBatchId = ''; p.store.load = async () => { throw Error('context unavailable') }
    await p.vm.load(); assert.equal(p.vm.state, 'error'); assert.deepEqual(p.vm.batches, []); assert.equal(p.vm.batchId, '')
  }
})
