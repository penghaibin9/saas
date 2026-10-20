import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('调停课提交后保留可刷新、可追踪的业务回执', () => {
  const apply = read('../src/modules/academicAffairs/views/AaScheduleChangeApplyView.vue')

  for (const contract of [
    'role="status"', 'receipt.changeId', 'receipt.courseName', '学院教务审核人',
    '查看申请详情', '继续从课表选择', 'res.data.changeId', 'this.form = EMPTY()'
  ]) assert.ok(apply.includes(contract), `调停课提交回执缺少：${contract}`)
  assert.ok(apply.includes('/print/schedule-change/${this.receipt.changeId}/notice'))
})

test('调停课审批回执区分学院流转、驳回和终审生效', () => {
  const approval = read('../src/modules/academicAffairs/views/AaScheduleChangeApprovalView.vue')

  for (const contract of [
    'role="status"', 'receipt.changeId', 'statusLabel(receipt.status)', '学院审核已通过',
    '调停课申请已驳回', '终审完成，课表已生效', '新课位进入考勤',
    'res.data.applied?.notified?.students', '查看单据与通知'
  ]) assert.ok(approval.includes(contract), `调停课审批回执缺少：${contract}`)
  assert.ok(approval.includes('grid-template-columns: 1fr'), '窄屏回执必须单列')
})
