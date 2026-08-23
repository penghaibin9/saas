import { safeEnumLabel } from '../../../utils/presentationSafety.js'

/** 教务业务枚举仅作为接口值传输；学校端统一展示中文。 */
export const ACADEMIC_STATUS_LABELS = Object.freeze({
  CREATED: '已创建',
  DRAFT: '草稿',
  PENDING: '待处理',
  RUNNING: '处理中',
  UPLOADED: '已上传',
  SCANNING: '安全扫描中',
  PARSING: '服务端预检中',
  VALIDATED: '预检通过',
  VALIDATION_FAILED: '预检未通过',
  CONFIRMING: '确认中',
  SUCCEEDED: '已完成',
  FAILED: '失败',
  EXPIRED: '已过期',
  REVOKED: '已撤销',
  REGISTERED: '已注册',
  ARRANGED: '已编排',
  PUBLISHED: '已发布',
  SCORING: '录分中',
  SCORED: '已录分',
  REVIEWED: '学院已审核',
  FINISHED: '已结束',
  SUBMITTED: '已提交',
  TEACHER_REVIEW: '教师审核中',
  TEACHER_CONFIRM: '教师确认中',
  COLLEGE_REVIEW: '学院审核中',
  ACADEMIC_REVIEW: '教务审核中',
  ACADEMIC_FINAL: '教务终审中',
  APPROVED: '已通过',
  REJECTED: '已驳回',
  RETURNED: '已退回',
  CANCELLED: '已取消',
  APPLIED: '已生效',
  ENROLLED: '已编入',
  RESOLVED: '已处理',
  FROZEN: '已冻结',
  ARCHIVED: '已归档',
  READY: '已就绪',
  PENDING_EXAM: '待补考',
  PASSED: '已通过',
  ABSENT: '缺考',
  ENROLLING: '报名中',
  STUDYING: '修读中'
})

export const ACADEMIC_EXCHANGE_TYPE_LABELS = Object.freeze({
  ROSTER: '学籍名册',
  STUDENT_ROSTER: '学籍名册',
  REGISTRATION_ROSTER: '注册名册',
  GRADE: '成绩数据',
  GRADES: '成绩数据'
})

function hasChinese(value) {
  return /[\u4e00-\u9fff]/.test(String(value || ''))
}

export function academicStatusLabel(value, unknownLabel = '状态待确认') {
  if (hasChinese(value)) return String(value)
  return safeEnumLabel({ value, dictionary: ACADEMIC_STATUS_LABELS, unknownLabel })
}

export function academicExchangeTypeLabel(value) {
  if (hasChinese(value)) return String(value)
  return safeEnumLabel({ value, dictionary: ACADEMIC_EXCHANGE_TYPE_LABELS, unknownLabel: '教务数据' })
}
