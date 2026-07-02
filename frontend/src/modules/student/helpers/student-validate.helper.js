/**
 * 学生主档 — 校验规则。
 * 身份核验退回：直接复用 workflow validateRejectReason（≥5 字，单一实现，不写第二套）。
 */
import { validateRejectReason } from '@/modules/workflow/helpers/approval.helpers'
import { STATUS_CHANGE_REASON_MIN_LENGTH } from '../constants/student.constants'

export { validateRejectReason }

/** 状态变更原因：必填（≥STATUS_CHANGE_REASON_MIN_LENGTH 字，与退回同规格） */
export function validateStatusChangeReason(reason) {
  const trimmed = String(reason || '').trim()
  const valid = trimmed.length >= STATUS_CHANGE_REASON_MIN_LENGTH
  return {
    valid,
    length: trimmed.length,
    minLength: STATUS_CHANGE_REASON_MIN_LENGTH,
    message: valid ? '' : `变更原因不能少于 ${STATUS_CHANGE_REASON_MIN_LENGTH} 个字（当前 ${trimmed.length} 字）`
  }
}

/** 监护人保存前校验：至少一位、姓名与关系必填、需一位紧急联系人 */
export function validateGuardians(list = []) {
  if (!Array.isArray(list) || !list.length) return { valid: false, message: '至少保留一位监护人/联系人' }
  for (const g of list) {
    if (!String(g.guardianName || '').trim()) return { valid: false, message: '监护人姓名必填' }
    if (!String(g.relationship || '').trim()) return { valid: false, message: '与学生关系必填' }
  }
  if (!list.some((g) => g.isEmergencyContact)) return { valid: false, message: '需指定一位紧急联系人' }
  return { valid: true, message: '' }
}
