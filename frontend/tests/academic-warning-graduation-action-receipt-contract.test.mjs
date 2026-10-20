import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('预警指派、跟进、提醒、升级、关闭与作废均形成 exact-student 回执', () => {
  const warning = read('../src/modules/academicAffairs/views/AaWarningConsoleView.vue')

  for (const contract of [
    'role="status"', 'actionReceipt.studentName', 'actionReceipt.warningId', 'recordActionReceipt',
    '跟进责任已指派', '预警跟进已记录', '预警提醒已发送', '预警已升级',
    '预警已关闭', '误报预警已作废', 'reopenReceipt'
  ]) assert.ok(warning.includes(contract), `预警动作回执缺少：${contract}`)
})

test('毕业学院审核、终审与归档均回答结果和下一步', () => {
  const graduation = read('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue')

  for (const contract of [
    'role="status"', 'actionReceipt.businessId', 'recordActionReceipt', '学院审核已退回',
    '学院审核已通过', '毕业资格终审完成', '终审结论已写入学籍',
    '毕业审核批次已归档', '后续变更必须走正式纠错链'
  ]) assert.ok(graduation.includes(contract), `毕业动作回执缺少：${contract}`)
  assert.ok(graduation.includes('grid-template-columns: 1fr'), '毕业回执窄屏必须单列')
})
