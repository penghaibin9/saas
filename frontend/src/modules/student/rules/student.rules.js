/**
 * 学生主档 — 风险与质量规则（唯一口径，页面与概览统计共用）。
 */
import { RISK_FLAG, DATA_QUALITY_STATUS, ACADEMIC_STATUS, ACCOUNT_BIND_STATUS, IDENTITY_VERIFY_STATUS } from '../constants/student.constants'

/** 由学生对象推导风险标记（与 mock 预置 riskFlags 同一规则） */
export function deriveRiskFlags(s) {
  const flags = []
  if (s.academicStatus === ACADEMIC_STATUS.WARNING) flags.push(RISK_FLAG.ACADEMIC_WARNING)
  if ((s.dataQualityTags || []).includes(DATA_QUALITY_STATUS.MISSING_REQUIRED)) flags.push(RISK_FLAG.DATA_MISSING)
  if (s.identityVerifyStatus === IDENTITY_VERIFY_STATUS.EXPIRED) flags.push(RISK_FLAG.ID_EXPIRED)
  if ((s.dataQualityTags || []).some((t) => t === DATA_QUALITY_STATUS.NEED_REVIEW || t === DATA_QUALITY_STATUS.CONFLICT)) {
    flags.push(RISK_FLAG.NEED_REVIEW)
  }
  if (s.bindStatus === ACCOUNT_BIND_STATUS.UNBOUND) flags.push(RISK_FLAG.ACCOUNT_UNBOUND)
  return flags
}

export function hasAnyRisk(s) {
  return deriveRiskFlags(s).length > 0
}

/** 风险标记 → 徽标 type */
export function riskFlagBadge(flag) {
  if (flag === RISK_FLAG.ACADEMIC_WARNING || flag === RISK_FLAG.ID_EXPIRED) return 'danger'
  return 'warning'
}
