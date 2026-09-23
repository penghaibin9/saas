import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

function mount(file, deps = {}, initial = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/${file}`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: { currentUserFromToken: () => ({ tenantId: '1', userId: '2' }), CHANGE_STATUS: [], CHANGE_TYPES: [], ...deps } }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  const base = { ctx: { currentRole: {}, dataScope: {}, permissionPatterns: [] }, $route: { query: {} }, $router: { push() {}, replace() {} }, ...initial }
  const state = Object.assign(base, definition.data?.call(base) || {}, definition.methods || {})
  for (const [name, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, name, { get: () => getter.call(state) })
  return state
}

test('attendance routes expose the exact business page title and preserve stable student identity', () => {
  const state = mount('views/AaAttendanceStatsView.vue', { matchPermission: () => false })
  assert.equal(state.pageTitle, '课堂考勤')
  state.panel = 'sessions'
  assert.equal(state.pageTitle, '课堂考勤')
  assert.match(state.pageSubtitle, /场次/)
  const student = state.normalizeStudent({ studentId: '991', sessions: 3 })
  assert.equal(student.studentId, '991')
  assert.equal(student.sessions, 3)
  assert.equal(student.realName, '学生 #991')
  assert.equal(student.studentNo, '学号未提供')
})

test('applied schedule-change evidence never claims notification delivery without a delivery receipt', () => {
  const state = mount('components/parallel-b/ScheduleChangeEvidence.vue', {
    CHANGE_STATUS: [{ value: 'APPLIED', label: '已生效' }]
  }, { changeId: '9' })
  state.detail = {
    changeId: '9', originItemId: '101', batchId: '7', courseName: '软件测试技术', status: 'APPLIED',
    version: 3, appliedAt: '2026-09-09T09:00:00Z', newItemId: '202', reason: '教师参加教学能力比赛',
    origin: { weekday: 1, slotNo: 1, classroom: '教学楼101' },
    target: { weekday: 4, slotNo: 3, classroom: '产教融合楼B203' }
  }
  const receipt = state.evidenceCards.find(item => item.title === '生效与通知回执')
  assert.equal(receipt.status, '课表已生效，送达待核对')
  assert.match(receipt.description, /通知送达数量未随详情返回/)
})

test('schedule-change todo focuses the exact large ID beyond the queue page and clears both supported sources', () => {
  const state = mount('views/AaScheduleChangeApprovalView.vue')
  state.$route.query = { recordId: '9007199254740993', returnToken: 'origin' }
  assert.equal(state.selectedId, '9007199254740993')
  state.rows = [{ changeId: '9' }]
  assert.equal(state.selectedId, '9007199254740993')
  state.$router.replace = ({ query }) => { state.$route.query = query }
  state.closeEvidence()
  assert.equal(state.selectedId, '')
  assert.equal(state.$route.query.returnToken, 'origin')
  state.$route.query = { changeId: '9' }
  assert.equal(state.selectedId, '9')
  state.$route.query = { recordId: ['9', '10'] }
  assert.equal(state.selectedId, '')
})

test('schedule-change statistics separates applications, pending work and effective lessons', () => {
  const state = mount('views/AaScheduleChangeStatsView.vue')
  state.stat = {
    total: 8,
    byType: { ADJUST: 4, STOP: 2, MAKEUP: 2 },
    byStatus: { APPLIED: 5, COLLEGE_REVIEW: 2, REJECTED: 1 }
  }
  assert.equal(state.pendingCount, 2)
  assert.equal(state.completionRate, 62.5)
  assert.equal(state.drilldowns.find(item => item.label === '已生效课次').value, 5)
  assert.equal(state.drilldowns.find(item => item.label === '未生效').value, 3)
})

test('graduation readback targets an exact historical batch in one request', async () => {
  const calls = []
  const state = mount('views/AaGraduationBatchView.vue', {
    academicAffairsApi: { listGradBatches: async query => { calls.push(query); return { code: 0, data: { list: [{ batchId: '9007199254740993' }], total: 1 } } } }
  })
  const result = await state.readBatch('9007199254740993')
  assert.equal(result.batchId, '9007199254740993')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].batchId, '9007199254740993')
  assert.equal(calls[0].pageSize, 1)
})

test('graduation list failure clears old batches and remains a visible error', async () => {
  const state = mount('views/AaGraduationBatchView.vue', {
    academicAffairsApi: { listGradBatches: async () => { throw new Error('连接中断') } },
    gradeError: () => '审核批次加载失败'
  })
  state.batches = [{ batchId: 'old' }]
  await state.loadBatches()
  assert.equal(state.batches.length, 0)
  assert.equal(state.listError, '审核批次加载失败')
  assert.equal(state.loadingList, false)
})

test('schedule publication needs exact formal readback and never claims delivery', async () => {
  const successes = [], errors = []; let count = 0
  const state = mount('views/AaScheduleBatchListView.vue', {
    academicAffairsApi: { publishSchedule: async () => { count++; return { code: 0 } }, getScheduleBatch: async () => ({ code: 0, data: { batchId: '9', status: 'PUBLISHED' } }) },
    toast: { success: value => successes.push(value), error: value => errors.push(value) }
  })
  state.load = async () => {}
  const first = state.act({ batchId: '9' }, 'pub'); await state.act({ batchId: '9' }, 'pub'); await first
  assert.equal(count, 1)
  assert.equal(errors.length, 0)
  assert.equal(successes.length, 1)
  assert.match(successes[0], /已核对正式课表/)
  assert.doesNotMatch(successes[0], /已通知师生|全部送达/)
})
