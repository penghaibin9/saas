/** 学生主档 — 状态徽标类型与状态变更规则 */
import {
  STUDENT_STATUS,
  STUDENT_STATUS_BADGE,
  IDENTITY_VERIFY_BADGE,
  ACADEMIC_STATUS,
  ACCOUNT_BIND_STATUS
} from '../constants/student.constants'

export function getStudentStatusBadge(status) {
  return STUDENT_STATUS_BADGE[status] || 'neutral'
}

export function getIdentityBadge(status) {
  return IDENTITY_VERIFY_BADGE[status] || 'neutral'
}

export function getAcademicBadge(status) {
  return status === ACADEMIC_STATUS.WARNING ? 'danger' : status === ACADEMIC_STATUS.DELAYED ? 'warning' : 'success'
}

export function getBindBadge(status) {
  if (status === ACCOUNT_BIND_STATUS.BOUND) return 'success'
  if (status === ACCOUNT_BIND_STATUS.UNBOUND) return 'warning'
  return 'danger'
}

/** 允许的状态流转（终态 ARCHIVED 不允许再变更；GRADUATED 仅可归档） */
const TRANSITIONS = Object.freeze({
  ACTIVE: ['SUSPENDED', 'RETAINED', 'TRANSFERRED', 'DROPPED_OUT', 'GRADUATED'],
  SUSPENDED: ['ACTIVE', 'DROPPED_OUT'],
  RETAINED: ['ACTIVE', 'DROPPED_OUT'],
  TRANSFERRED: ['ARCHIVED'],
  DROPPED_OUT: ['ARCHIVED'],
  GRADUATED: ['ARCHIVED'],
  ARCHIVED: []
})

export function getAllowedNextStatuses(current) {
  return TRANSITIONS[current] || []
}

export function isFinalStatus(status) {
  return status === STUDENT_STATUS.ARCHIVED
}
