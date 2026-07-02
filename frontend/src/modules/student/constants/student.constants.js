/**
 * 01 学生主档与身份中心 — 集中枚举（全系统学生数据底座）
 * 依据：docs/source-design/01-学生主档与身份中心深化设计（student_id 主线/数据范围/脱敏审计）
 * 页面禁止散写字符串；展示文案经 helper 映射。
 */

export const STUDENT_MODULE_CODE = 'STUDENT'

export const GENDER = Object.freeze({ MALE: 'MALE', FEMALE: 'FEMALE', UNKNOWN: 'UNKNOWN' })
export const GENDER_LABELS = Object.freeze({ MALE: '男', FEMALE: '女', UNKNOWN: '未知' })

export const EDUCATION_LEVEL = Object.freeze({
  SECONDARY: 'SECONDARY',
  HIGHER_VOCATIONAL: 'HIGHER_VOCATIONAL',
  UNDERGRADUATE: 'UNDERGRADUATE',
  OTHER: 'OTHER'
})
export const EDUCATION_LEVEL_LABELS = Object.freeze({
  SECONDARY: '中职',
  HIGHER_VOCATIONAL: '高职',
  UNDERGRADUATE: '本科',
  OTHER: '其他'
})

export const STUDENT_TYPE = Object.freeze({
  FULL_TIME: 'FULL_TIME',
  PART_TIME: 'PART_TIME',
  TRANSFER: 'TRANSFER',
  EXCHANGE: 'EXCHANGE',
  OTHER: 'OTHER'
})
export const STUDENT_TYPE_LABELS = Object.freeze({
  FULL_TIME: '全日制',
  PART_TIME: '非全日制',
  TRANSFER: '转入',
  EXCHANGE: '交流',
  OTHER: '其他'
})

export const STUDENT_STATUS = Object.freeze({
  ACTIVE: 'ACTIVE',
  SUSPENDED: 'SUSPENDED',
  RETAINED: 'RETAINED',
  TRANSFERRED: 'TRANSFERRED',
  DROPPED_OUT: 'DROPPED_OUT',
  GRADUATED: 'GRADUATED',
  ARCHIVED: 'ARCHIVED'
})
export const STUDENT_STATUS_LABELS = Object.freeze({
  ACTIVE: '在校',
  SUSPENDED: '休学',
  RETAINED: '保留学籍',
  TRANSFERRED: '转学',
  DROPPED_OUT: '退学',
  GRADUATED: '已毕业',
  ARCHIVED: '已归档'
})
/** 状态 → AppBadge type */
export const STUDENT_STATUS_BADGE = Object.freeze({
  ACTIVE: 'success',
  SUSPENDED: 'warning',
  RETAINED: 'warning',
  TRANSFERRED: 'neutral',
  DROPPED_OUT: 'danger',
  GRADUATED: 'info',
  ARCHIVED: 'neutral'
})

export const ACADEMIC_STATUS = Object.freeze({
  NORMAL: 'NORMAL',
  WARNING: 'WARNING',
  DELAYED: 'DELAYED',
  COMPLETED: 'COMPLETED'
})
export const ACADEMIC_STATUS_LABELS = Object.freeze({
  NORMAL: '正常',
  WARNING: '学业预警',
  DELAYED: '延期',
  COMPLETED: '已完成'
})

export const IDENTITY_VERIFY_STATUS = Object.freeze({
  UNVERIFIED: 'UNVERIFIED',
  PENDING: 'PENDING',
  VERIFIED: 'VERIFIED',
  REJECTED: 'REJECTED',
  EXPIRED: 'EXPIRED'
})
export const IDENTITY_VERIFY_STATUS_LABELS = Object.freeze({
  UNVERIFIED: '未认证',
  PENDING: '待核验',
  VERIFIED: '已认证',
  REJECTED: '认证退回',
  EXPIRED: '证件过期'
})
export const IDENTITY_VERIFY_BADGE = Object.freeze({
  UNVERIFIED: 'neutral',
  PENDING: 'warning',
  VERIFIED: 'success',
  REJECTED: 'danger',
  EXPIRED: 'danger'
})

export const ACCOUNT_STATUS = Object.freeze({
  NORMAL: 'NORMAL',
  UNBOUND: 'UNBOUND',
  BOUND: 'BOUND',
  DISABLED: 'DISABLED',
  LOCKED: 'LOCKED'
})
export const ACCOUNT_STATUS_LABELS = Object.freeze({
  NORMAL: '正常',
  UNBOUND: '未绑定',
  BOUND: '已绑定',
  DISABLED: '已禁用',
  LOCKED: '已锁定'
})

export const ACCOUNT_BIND_STATUS = Object.freeze({
  UNBOUND: 'UNBOUND',
  BOUND: 'BOUND',
  DISABLED: 'DISABLED',
  LOCKED: 'LOCKED'
})
export const ACCOUNT_BIND_STATUS_LABELS = Object.freeze({
  UNBOUND: '未绑定',
  BOUND: '已绑定',
  DISABLED: '已禁用',
  LOCKED: '已锁定'
})

export const REGISTRATION_STATUS = Object.freeze({
  NOT_REGISTERED: 'NOT_REGISTERED',
  REGISTERED: 'REGISTERED',
  DELAYED: 'DELAYED'
})
export const REGISTRATION_STATUS_LABELS = Object.freeze({
  NOT_REGISTERED: '未注册',
  REGISTERED: '已注册',
  DELAYED: '延迟注册'
})

export const DATA_QUALITY_STATUS = Object.freeze({
  COMPLETE: 'COMPLETE',
  MISSING_REQUIRED: 'MISSING_REQUIRED',
  NEED_REVIEW: 'NEED_REVIEW',
  CONFLICT: 'CONFLICT'
})
export const DATA_QUALITY_STATUS_LABELS = Object.freeze({
  COMPLETE: '完整',
  MISSING_REQUIRED: '缺必填',
  NEED_REVIEW: '需复核',
  CONFLICT: '冲突'
})

export const RISK_FLAG = Object.freeze({
  ACADEMIC_WARNING: 'ACADEMIC_WARNING',
  DATA_MISSING: 'DATA_MISSING',
  ID_EXPIRED: 'ID_EXPIRED',
  NEED_REVIEW: 'NEED_REVIEW',
  ACCOUNT_UNBOUND: 'ACCOUNT_UNBOUND'
})
export const RISK_FLAG_LABELS = Object.freeze({
  ACADEMIC_WARNING: '学业预警',
  DATA_MISSING: '资料缺失',
  ID_EXPIRED: '证件过期',
  NEED_REVIEW: '需复核',
  ACCOUNT_UNBOUND: '账号未绑定'
})

/** 权限点（module.resource.action，注册进 workflow 权限点管理） */
export const STUDENT_PERMISSION = Object.freeze({
  PROFILE_VIEW: 'student.profile.view',
  PROFILE_CREATE: 'student.profile.create',
  PROFILE_UPDATE: 'student.profile.update',
  PROFILE_DELETE: 'student.profile.delete',
  IDENTITY_VIEW: 'student.identity.view',
  IDENTITY_VERIFY: 'student.identity.verify',
  CONTACT_VIEW: 'student.contact.view',
  CONTACT_UPDATE: 'student.contact.update',
  GUARDIAN_VIEW: 'student.guardian.view',
  GUARDIAN_UPDATE: 'student.guardian.update',
  STATUS_UPDATE: 'student.status.update',
  IMPORT: 'student.import',
  EXPORT: 'student.export',
  AUDIT_VIEW: 'student.audit.view'
})

/** 状态变更原因最小字数（与退回原因同规格） */
export const STATUS_CHANGE_REASON_MIN_LENGTH = 5
