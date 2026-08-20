const TECHNICAL_MESSAGE_PATTERNS = [
  /\b(?:integrityerror|traceback|sqlstate|syntaxerror|typeerror|referenceerror)\b/i,
  /\b(?:select|insert|update|delete)\s+.+\b(?:from|into|set)\b/i,
  /\b(?:column|constraint|table|permissionkey|traceid|bizcode)\b/i,
  /(?:^|[\s=:])[a-z]+(?:[A-Z][a-z0-9]+)+(?=$|[\s,.;:=])/,
  /\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/,
  /(?:[A-Za-z]:\\|\/(?:tmp|var|home|opt|srv)\/)/,
  /<\/?[a-z][^>]*>/i,
  /^(?:\s*\{.*\}|\s*\[.*\])\s*$/s
]

const BUSINESS_CODE_MESSAGES = Object.freeze({
  NO_PERMISSION: '当前账号没有执行此操作的权限',
  NO_DATA_SCOPE: '当前账号尚未配置可管理范围',
  RECORD_NOT_FOUND: '记录不存在或已被删除',
  VERSION_CONFLICT: '记录已发生变化，请刷新后重试'
})

const SAFE_BACKEND_BUSINESS_MESSAGE_CODES = new Set([
  'DATA_CONFLICT'
])

function numericStatus(error) {
  const raw = error && typeof error === 'object' ? (error.status || error.code) : 0
  const value = Number(raw)
  if (value >= 100000) return Math.trunc(value / 1000)
  return value
}

function supportCode(error) {
  if (!error || typeof error !== 'object') return ''
  return String(error.traceId || error.supportCode || '').trim().slice(0, 64)
}

export function isTechnicalUiMessage(value) {
  const text = String(value || '').trim()
  if (!text) return false
  return TECHNICAL_MESSAGE_PATTERNS.some((pattern) => pattern.test(text))
}

export function normalizeUiError(error, context = {}) {
  const rawMessage = String(
    error && typeof error === 'object' ? (error.message || error.userMessage || '') : (error || '')
  ).trim()
  const bizCode = String(
    (error && typeof error === 'object' && error.bizCode) || context.bizCode || ''
  ).trim()
  const status = numericStatus(error) || Number(context.status || 0)
  const code = supportCode(error)

  let userMessage = BUSINESS_CODE_MESSAGES[bizCode] || ''
  if (
    !userMessage &&
    SAFE_BACKEND_BUSINESS_MESSAGE_CODES.has(bizCode) &&
    rawMessage &&
    rawMessage.length <= 160 &&
    !isTechnicalUiMessage(rawMessage)
  ) {
    userMessage = rawMessage
  }
  if (!userMessage && status === 403) userMessage = '当前账号没有执行此操作的权限'
  if (!userMessage && status === 409) userMessage = '记录已发生变化，请刷新后重试'
  if (!userMessage && status >= 500) userMessage = '系统暂时无法完成该操作，请稍后重试'
  if (!userMessage && rawMessage && !isTechnicalUiMessage(rawMessage) && rawMessage.length <= 160) {
    userMessage = rawMessage
  }
  if (!userMessage) userMessage = context.fallback || '操作未完成，请稍后重试'

  if (code && (status >= 500 || isTechnicalUiMessage(rawMessage))) {
    userMessage += `（问题编号：${code}）`
  }

  return {
    userMessage,
    supportCode: code,
    rawDeveloperDetail: rawMessage,
    bizCode,
    status
  }
}

export function safeBusinessMessage(value, fallback = '操作未完成，请稍后重试') {
  return normalizeUiError(value, { fallback }).userMessage
}

export function safeEnumLabel({ value, dictionary = {}, unknownLabel = '待确认' } = {}) {
  const key = String(value ?? '').trim()
  if (!key) return '—'
  return dictionary[key] || dictionary[key.toUpperCase()] || unknownLabel
}

const AUDIT_ACTION_LABELS = Object.freeze({
  CREATE: '创建', UPDATE: '修改', DELETE: '删除', SUBMIT: '提交',
  APPLY: '提交申请', RESUBMIT: '重新提交',
  APPROVE: '审核通过', REVIEW_APPROVE: '审批通过',
  REJECT: '审核驳回', REVIEW_REJECT: '审批驳回',
  RETURN: '退回修改', REVIEW_RETURN: '退回修改', RETURN_VERSIONED: '办理销假',
  PUBLISH: '发布', ARCHIVE: '归档', ROLE_ASSIGN: '分配角色'
})
const AUDIT_RESULT_LABELS = Object.freeze({
  SUCCESS: '成功', PASSED: '已通过', COMPLETED: '已完成',
  FAILED: '失败', REJECTED: '已驳回', RETURNED: '已退回'
})
const AUDIT_ROLE_LABELS = Object.freeze({
  STUDENT: '学生', TEACHER: '教师', COUNSELOR: '辅导员',
  ACADEMIC_ADMIN: '教务管理员', STUDENT_AFFAIRS_ADMIN: '学工管理员',
  SCHOOL_ADMIN: '学校管理员', PLATFORM_OPERATOR: '平台运营人员',
  PLATFORM_SECURITY_AUDITOR: '平台安全审计员'
})

export function presentAuditRecord(record = {}) {
  return {
    ...record,
    displayAction: record.actionLabel || safeEnumLabel({
      value: record.action,
      dictionary: AUDIT_ACTION_LABELS,
      unknownLabel: '业务操作'
    }),
    displayResult: record.resultLabel || safeEnumLabel({
      value: record.result,
      dictionary: AUDIT_RESULT_LABELS,
      unknownLabel: record.result ? '结果待确认' : '—'
    }),
    displayRole: record.actorRoleLabel || safeEnumLabel({
      value: record.actorRole,
      dictionary: AUDIT_ROLE_LABELS,
      unknownLabel: record.actorRole ? '业务经办人' : '—'
    }),
    displayTarget: record.targetLabel || record.targetName || (record.target ? '相关业务对象' : ''),
    displayReason: record.reason ? safeBusinessMessage(record.reason, '已记录操作原因') : ''
  }
}
