import test from 'node:test'
import assert from 'node:assert/strict'
import { page } from './academic-pc-parallel-b-harness.mjs'

test('调课审批从通用详情进入精确业务对象，不依赖通用通过按钮', () => {
  const routes = []
  const { state } = page('../../../views/admin/approval/ApprovalDetailView', {}, { $router: { push: value => routes.push(value) } })
  state.task = { bizType: 'AA_SCHEDULE_CHANGE', sourceBizId: '9007199254740993', allowedActions: [] }
  state.openSourceBusiness()
  assert.equal(routes[0].path, '/admin/academic-affairs/schedule-change/approval')
  assert.equal(routes[0].query.changeId, '9007199254740993')
  state.task.sourceBizId = 'invalid'
  assert.equal(state.sourceBusinessRoute, null)
  state.task = { bizType: 'OTHER', sourceBizId: '9' }
  assert.equal(state.sourceBusinessRoute, null)
})

test('通用批量审批遇调课任务先说明正式入口，不发送批量动作', async () => {
  const notices = []
  const { state } = page('../../../views/admin/approval/ApprovalTodoListView', { toast: { info: text => notices.push(text) } }, {
    ctx: { permissionActions: { batchApprove: { visible: true, allowed: true } } }
  })
  state.rows = [{ taskId: '161', bizType: 'AA_SCHEDULE_CHANGE' }]; state.selected = ['161']
  await state.onBatch('batchApprove')
  assert.equal(state.approveDialog, false)
  assert.match(notices[0], /调停课审批/)
})
