import test from 'node:test'
import assert from 'node:assert/strict'
import { page } from './academic-pc-parallel-b-harness.mjs'
import { academicFlowText } from '../src/modules/academicAffairs/config/academicFlowRegistry.js'
import { academicObjectParentPath } from '../src/modules/academicAffairs/config/academicNavigation.js'

test('归档异常保留版本与纠错对象，并给出中文原因和处理责任', () => {
  const { state } = page('../components/AaArchiveCorrectionWorkspace', { academicFlowText }, { emptyCreateForm: () => ({}) })
  const message = state.manifestReason('V2:HASH_MISMATCH;CORRECTION#3:GRADE_FACT_LINEAGE_BROKEN')
  assert.match(message, /第 2 版.*校验值不一致/)
  assert.match(message, /纠错单 3.*成绩.*关联/)
  assert.match(message, /归档.*人员/)
  assert.doesNotMatch(message, /HASH_MISMATCH|GRADE_FACT_LINEAGE_BROKEN/)
  assert.match(state.manifestReason('MANIFEST_MISSING'), /缺少.*归档清单/)
  assert.match(state.manifestReason('UNRECOGNIZED_INTERNAL_CODE'), /未识别.*实施人员/)
})

test('已发布考务保留资源风险，但不再误称尚未进入可发布阶段', () => {
  const { state } = page('AaExamConsoleView')
  state.current = { status: 'PUBLISHED' }
  state.readiness = { canPublish: false, blockingReasons: ['仍有 1 个考场未配足有效监考教师', '考试批次尚未进入可发布阶段'] }
  assert.equal(state.postPublishReview, true)
  assert.equal(state.readinessReasons.length, 1)
  assert.match(state.readinessReasons[0], /监考教师/)
  state.current.status = 'DRAFT'
  assert.equal(state.postPublishReview, false)
  assert.equal(state.readinessReasons.length, 2)
  assert.equal(state.readiness.canPublish, false)
})

test('选课窗口过期或尚未开始时建议与时间状态一致', () => {
  const { state } = page('AaSelectionConsoleView')
  state.current = { status: 'OPEN', windowState: 'ENDED' }
  assert.match(state.nextActionFor('OPEN'), /办理批次截止/)
  state.current.windowState = 'NOT_STARTED'
  assert.match(state.nextActionFor('OPEN'), /等待选课窗口开始/)
  state.current.windowState = 'OPEN'
  assert.match(state.nextActionFor('OPEN'), /关注容量/)
  assert.match(state.nextActionFor('ARCHIVED'), /历史|归档|查阅/)
})

test('选课批次截止后轮次不再误示可办理，也不能从页面重新开启', () => {
  const { state } = page('AaSelectionConsoleView')
  const round = { roundId: '1', status: 'CLOSED', allowEnroll: true, allowDrop: true }
  state.rounds = [round]; state.current = { status: 'CLOSED', windowState: 'ENDED' }
  assert.equal(state.canOpenRound(round), false)
  assert.match(state.roundAvailability(round), /学生不可办理/)
  state.current = { status: 'OPEN', windowState: 'ENDED' }
  assert.equal(state.canOpenRound(round), false)
  state.current.windowState = 'OPEN'
  assert.equal(state.canOpenRound(round), true)
  state.rounds.push({ roundId: '2', status: 'OPEN' })
  assert.equal(state.canOpenRound(round), false)
})

test('排课工作台归属课表批次，规则页保留自身归属', () => {
  assert.equal(academicObjectParentPath('/admin/academic-affairs/scheduling', new URLSearchParams('batchId=40')), '/admin/academic-affairs/schedule')
  assert.equal(academicObjectParentPath('/admin/academic-affairs/scheduling', new URLSearchParams('tab=workbench&batchId=40')), '/admin/academic-affairs/schedule')
  assert.equal(academicObjectParentPath('/admin/academic-affairs/scheduling', new URLSearchParams('tab=rules')), null)
})

test('挂科补救显示正式状态，未知状态不泄漏内部值，重修入口携带精确申请', () => {
  const calls = []
  const { state } = page('AaGradeFailListView', { matchPermission: patterns => patterns.includes('view') }, {
    ctx: { permissionPatterns: ['view'] }, $router: { push: value => calls.push(value) }
  })
  assert.match(state.remedyLabel({ kind: 'RETAKE', status: 'ENROLLED' }), /重修.*已编班/)
  assert.match(state.remedyLabel({ kind: 'MAKEUP', status: 'FINISHED' }), /仍未通过/)
  assert.equal(state.remedyLabel({ kind: 'INTERNAL', status: 'INTERNAL' }), '补救记录：办理状态待核对')
  state.goRemedy({ kind: 'RETAKE', id: '9007199254740993' })
  assert.equal(calls[0].query.applyId, '9007199254740993')
  state.goRemedy({ kind: 'MAKEUP', id: '21', batchId: '9' }, { gradeId: '31' })
  assert.equal(calls[1].query.tab, 'makeup'); assert.equal(calls[1].query.batchId, '9'); assert.equal(calls[1].query.originGradeId, '31')
  state.ctx.permissionPatterns = []
  state.goRemedy({ kind: 'RETAKE', id: '1' })
  assert.equal(calls.length, 2)
})

test('挂科清单刷新或返回恢复原学期和页码，重新查询回到第一页', () => {
  const calls = []
  const { state } = page('AaGradeFailListView', {}, { $route: { query: { term: '2025-2026-2', page: '3' } }, $router: { replace: value => calls.push(value) } })
  state.restoreQuery()
  assert.equal(state.filters.term, '2025-2026-2'); assert.equal(state.pagination.page, 3)
  state.search()
  assert.equal(calls[0].query.term, '2025-2026-2'); assert.equal(calls[0].query.page, '1')
  state.$route.query.page = '-1'; state.restoreQuery()
  assert.equal(state.pagination.page, 1)
})

test('重修页从挂科来源直接加载指定申请，不误开其他对象', async () => {
  const requests = []
  const { state } = page('AaMakeupConsoleView', { academicAffairsMakeupApi: { retakeApplies: async params => { requests.push(params); return { code: 0, data: { list: [{ applyId: '27', status: 'ENROLLED' }], total: 1 } } } }, gradeError: (_e, fallback) => fallback }, {
    ctx: { currentRole: {}, dataScope: {}, permissionPatterns: [] }, $route: { query: { tab: 'retake', applyId: '27' } }
  })
  state.tab = 'retake'
  await state.reload()
  assert.equal(requests[0].applyId, '27')
  assert.equal(state.activeApplication.applyId, '27')
  state.$route.query.applyId = '28'
  await state.reload()
  assert.equal(state.activeApplication, null)
  assert.match(state.error, /未找到指定重修申请/)
  state.$route.query.applyId = 'not-an-id'
  await assert.rejects(() => state.readTab('retake'), /编号无效/)
})
