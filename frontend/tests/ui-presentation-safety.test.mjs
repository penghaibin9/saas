import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  normalizeUiError,
  presentAuditRecord,
  safeEnumLabel
} from '../src/utils/presentationSafety.js'

test('SQL、路径、枚举和 JSON 错误不会进入用户文案', () => {
  for (const message of [
    'IntegrityError: column student_id cannot be null',
    '/tmp/upload/tenant-9/file.bin',
    'Unknown enum PENDING_X',
    '{"permissionKey":"student.edit"}'
  ]) {
    const result = normalizeUiError({ message, code: 500001, traceId: 'support-123' })
    assert.doesNotMatch(result.userMessage, /student_id|\/tmp|PENDING_X|permissionKey/)
    assert.match(result.userMessage, /系统暂时无法完成该操作/)
    assert.match(result.userMessage, /support-123/)
  }
})

test('403、409 与可信业务校验保持精确语义', () => {
  assert.equal(normalizeUiError({ message: 'forbidden', code: 403001 }).userMessage, '当前账号没有执行此操作的权限')
  assert.equal(normalizeUiError({ message: 'conflict', code: 409001 }).userMessage, '记录已发生变化，请刷新后重试')
  assert.equal(
    normalizeUiError({
      message: '当前教学任务的正式编班模式不允许进入学生选课供给',
      code: 409001,
      bizCode: 'DATA_CONFLICT'
    }).userMessage,
    '当前教学任务的正式编班模式不允许进入学生选课供给'
  )
  assert.equal(normalizeUiError('结束日期不能早于开始日期').userMessage, '结束日期不能早于开始日期')
})

test('DATA_CONFLICT 仍禁止技术细节穿透 409 保护', () => {
  assert.equal(
    normalizeUiError({
      message: 'IntegrityError: column source_program_course_id cannot be null',
      code: 409001,
      bizCode: 'DATA_CONFLICT'
    }).userMessage,
    '记录已发生变化，请刷新后重试'
  )
})

test('未知枚举与审计字段使用安全 fallback', () => {
  assert.equal(safeEnumLabel({ value: 'NEW_BACKEND_STATUS', dictionary: {} }), '待确认')
  const row = presentAuditRecord({
    action: 'ROLE_ASSIGN_V2',
    result: 'NEW_SUCCESS_KIND',
    actorRole: 'PLATFORM_SECURITY_AUDITOR_V2',
    target: 'student:123'
  })
  assert.deepEqual(
    [row.displayAction, row.displayResult, row.displayRole, row.displayTarget],
    ['业务操作', '结果待确认', '业务经办人', '相关业务对象']
  )
})

test('公共组件源码不再包含任意对象 JSON 或 unknown raw fallback', () => {
  const preview = readFileSync(new URL('../src/components/common/excel/AppImportPreviewTable.vue', import.meta.url), 'utf8')
  const audit = readFileSync(new URL('../src/components/common/AppAuditTrail.vue', import.meta.url), 'utf8')
  const status = readFileSync(new URL('../src/components/common/AppStatusTag.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(preview, /JSON\.stringify\(r\)/)
  assert.match(preview, /该行已读取，请查看校验结果/)
  assert.match(audit, /showIp: \{ type: Boolean, default: false \}/)
  assert.doesNotMatch(audit, /\{\{ r\.action \|\|/)
  assert.doesNotMatch(status, /this\.mapped \? this\.mapped\.label : this\.status/)
})
