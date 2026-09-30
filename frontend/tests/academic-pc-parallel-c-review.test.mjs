import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { gradeError, gradeStatusLabel } from '../src/modules/academicAffairs/views/parallel-c/grade-review.js'

const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaGradeCollegeReviewView.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const row = (id, status = 'SUBMITTED') => ({ gradeTaskId: id, courseName: `课程${id}`, status, allowedActions: ['COLLEGE_REVIEW'] })
const result = (...rows) => ({ code: 0, data: { list: rows, total: rows.length } })
function mount(api) {
  const names = ['ModulePageShell', 'LoadingState', 'ErrorState', 'EmptyState', 'AppStatusTag', 'AppConfirmDialog', 'GradeReviewEvidence']
  const options = new Function('academicAffairsApi', 'currentUserFromToken', 'gradeStatusLabel', 'gradeError', ...names, script)(api, () => ({}), gradeStatusLabel, gradeError, ...names.map(() => ({})))
  const vm = { ...options.data(), identityKey: 'identity-1', $route: { path: '/college-review', fullPath: '/college-review', query: {} }, $router: { replace: async () => {} }, ctx: { currentRole: {}, dataScope: {} } }
  for (const [name, method] of Object.entries(options.methods)) vm[name] = method.bind(vm)
  for (const [name, getter] of Object.entries(options.computed || {})) if (name !== 'identityKey') Object.defineProperty(vm, name, { get: () => getter.call(vm) })
  return vm
}

test('指定任务单独按 ID 查询，不以第一页替代；403 不显示原对象', async () => {
  const calls = []
  const vm = mount({ getGradeTasks: async params => { calls.push(params); return params.taskId === '88' ? result(row('88')) : { code: 403 } } })
  await vm.selectTask('88')
  assert.equal(vm.current.gradeTaskId, '88')
  assert.deepEqual(calls[0], { taskId: '88', page: 1, pageSize: 1 })
  await vm.selectTask('89')
  assert.equal(vm.current, null)
  assert.match(vm.error, /无权/)
})

for (const mode of ['success', 'throw']) test(`快速切换，旧 ${mode} 和 finally 不污染新任务`, async () => {
  const a = deferred(), b = deferred()
  const vm = mount({ getGradeTasks: params => params.taskId === 'A' ? a.promise : b.promise })
  const old = vm.selectTask('A'), next = vm.selectTask('B')
  if (mode === 'success') a.resolve(result(row('A'))); else a.reject(new Error('旧错误'))
  await old
  assert.equal(vm.detailLoading, true)
  assert.equal(vm.current, null)
  assert.equal(vm.detailError, '')
  b.resolve(result(row('B'))); await next
  assert.equal(vm.current.gradeTaskId, 'B')
})

test('确认冻结任务；切换对象后旧确认不发送 POST', async () => {
  let writes = 0
  const vm = mount({ getGradeTasks: async p => result(row(p.taskId)), collegeReviewGrade: async () => { writes++ } })
  await vm.selectTask('A'); vm.openReview('RETURN')
  const oldDialog = vm.dlg
  await vm.selectTask('B'); vm.dlg = oldDialog
  await vm.doReview({ reason: '请核对异常成绩后重新提交' })
  assert.equal(writes, 0)
})

test('重复确认只提交一次，写后按同一任务回读正式状态', async () => {
  const response = deferred(); let writes = 0, reads = 0
  const vm = mount({ getGradeTasks: async p => { reads++; return result(row(p.taskId, writes ? 'RETURNED' : 'SUBMITTED')) }, collegeReviewGrade: () => { writes++; return response.promise } })
  await vm.selectTask('A'); vm.openReview('RETURN')
  const first = vm.doReview({ reason: '请核对异常成绩后重新提交' }); await vm.doReview({ reason: '请核对异常成绩后重新提交' })
  await Promise.resolve(); response.resolve({ code: 0, data: { gradeTaskId: 'A', status: 'RETURNED' } }); await first
  assert.equal(writes, 1); assert.equal(reads, 3)
  assert.equal(vm.receipt.status, 'RETURNED'); assert.equal(vm.receipt.verified, true)
})

test('写入超时且回读不变，保留待核实；再次核对只能 GET', async () => {
  let writes = 0
  const vm = mount({ getGradeTasks: async p => result(row(p.taskId)), collegeReviewGrade: async () => { writes++; throw new Error('timeout') } })
  await vm.selectTask('A'); vm.openReview('RETURN'); await vm.doReview({ reason: '请核对异常成绩后重新提交' })
  assert.equal(vm.receipt.verified, false); assert.ok(vm.pending)
  vm.openReview('RETURN'); await vm.doReview({ reason: '请核对异常成绩后重新提交' }); await vm.verifyReceipt()
  assert.equal(writes, 1); assert.equal(vm.busy, false)
})

test('确认前已流转则不写；不把正式发布状态显示为学院审核成功', async () => {
  let writes = 0
  const vm = mount({ getGradeTasks: async p => result(row(p.taskId, 'PUBLISHED')), collegeReviewGrade: async () => { writes++ } })
  vm.current = row('A'); vm.dlg = { visible: true, action: 'RETURN', taskId: 'A', courseName: '课程A', identity: vm.identityKey, route: vm.routeKey, seq: vm.detailSeq }; await vm.doReview({ reason: '请核对异常成绩后重新提交' })
  assert.equal(writes, 0); assert.equal(vm.current.status, 'PUBLISHED')
  assert.equal(gradeStatusLabel('PUBLISHED'), '已正式发布')
  assert.equal(gradeStatusLabel('UNKNOWN'), '状态待确认')
})

test('409 保留服务端给出的真实业务阻断，缺少说明时才使用通用文案', () => {
  assert.equal(
    gradeError({ code: 409001, bizCode: 'DATA_CONFLICT', message: '历史成绩缺少发布任务快照，无法安全判定及格线，请先完成数据治理' }),
    '历史成绩缺少发布任务快照，无法安全判定及格线，请先完成数据治理'
  )
  assert.equal(gradeError({ code: 409001, bizCode: 'DATA_CONFLICT' }), '任务已变化，请重新读取并核对后办理。')
})

test('身份失效后旧读取不会落页', async () => {
  const wait = deferred(); const vm = mount({ getGradeTasks: () => wait.promise })
  const load = vm.selectTask('A'); vm.identityKey = 'identity-2'; vm.invalidate()
  wait.resolve(result(row('A'))); await load
  assert.equal(vm.current, null); assert.equal(vm.detailLoading, false)
})

test('办理期间冻结当前对象，避免旧收尾遗留 busy 或改写另一个任务', async () => {
  const response = deferred(); let writes = 0
  const vm = mount({ getGradeTasks: async p => result(row(p.taskId, writes ? 'RETURNED' : 'SUBMITTED')), collegeReviewGrade: () => { writes++; return response.promise } })
  await vm.selectTask('A'); vm.openReview('RETURN'); const action = vm.doReview({ reason: '请核对异常成绩后重新提交' })
  await Promise.resolve(); await vm.selectTask('B')
  assert.equal(vm.selectedId, 'A')
  response.resolve({ code: 0 }); await action
  assert.equal(vm.busy, false)
  await vm.selectTask('B'); assert.equal(vm.selectedId, 'B')
})


test('缺失完整审核证据，即使 allowedActions 允许也不能通过', async () => {
  let writes = 0
  const vm = mount({ collegeReviewGrade: async () => { writes++ } })
  vm.current = row('A'); vm.openReview('APPROVE')
  assert.equal(vm.dlg.visible, false)
  vm.dlg = { visible: true, action: 'APPROVE', taskId: 'A', identity: vm.identityKey, seq: vm.detailSeq }
  await vm.doReview({})
  assert.equal(writes, 0)
})

test('命令 409 保留意见和任务，重新核对只有 GET，再次确认才写入', async () => {
  let writes = 0, reads = 0
  const reason = '请核对缓考标记和成绩依据后重新提交'
  const vm = mount({ getGradeTasks: async p => { reads++; return result(row(p.taskId)) }, collegeReviewGrade: async () => { writes++; return { code: 409, bizCode: 'DATA_CONFLICT' } } })
  await vm.selectTask('A'); vm.openReview('RETURN'); await vm.doReview({ reason })
  assert.equal(vm.reviewReason, reason); assert.equal(vm.dlg.visible, true); assert.equal(vm.dlg.taskId, 'A')
  assert.equal(vm.reviewConflict, true); assert.match(vm.reviewMessage, /已变化/)
  assert.equal(vm.pending, null); assert.equal(vm.receipt, null)
  await vm.doReview({ reason }); assert.equal(writes, 1)
  const before = reads; await vm.refreshReview(); assert.equal(reads, before + 1); assert.equal(writes, 1)
  assert.equal(vm.reviewReason, reason); assert.equal(vm.reviewConflict, false)
  vm.dlg.visible = false; vm.openReview('RETURN'); assert.equal(vm.reviewReason, reason)
  await vm.doReview({ reason: '' }); assert.equal(writes, 2)
})

test('命令 403 清空任务、队列、意见、确认和回执，旧队列响应也无效', async () => {
  const delayedList = deferred(); let writes = 0
  const vm = mount({ getGradeTasks: p => p.taskId ? Promise.resolve(result(row(p.taskId))) : delayedList.promise,
    collegeReviewGrade: async () => { writes++; return { code: 403, bizCode: 'NO_PERMISSION' } } })
  await vm.selectTask('A'); vm.rows = [row('A')]; vm.pagination.total = 1; vm.focusTaskId = 'A'
  const list = vm.load()
  vm.openReview('RETURN'); await vm.doReview({ reason: '请核对该学生个人成绩依据' })
  assert.equal(writes, 1); assert.equal(vm.current, null); assert.deepEqual(vm.rows, [])
  assert.equal(vm.reviewReason, ''); assert.equal(vm.reviewDraftTaskId, ''); assert.equal(vm.selectedId, '')
  assert.equal(vm.dlg.taskId, ''); assert.equal(vm.dlg.courseName, ''); assert.equal(vm.dlg.visible, false)
  assert.equal(vm.receipt, null); assert.equal(vm.pending, null); assert.equal(vm.pagination.total, 0); assert.match(vm.error, /无权/)
  delayedList.resolve(result(row('A'))); await list
  assert.deepEqual(vm.rows, []); assert.equal(vm.current, null)
})
