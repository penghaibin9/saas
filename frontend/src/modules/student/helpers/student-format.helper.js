/** 学生主档 — 展示文案映射（枚举 → 中文，页面禁止自行映射） */
import {
  GENDER_LABELS,
  EDUCATION_LEVEL_LABELS,
  STUDENT_TYPE_LABELS,
  STUDENT_STATUS_LABELS,
  ACADEMIC_STATUS_LABELS,
  IDENTITY_VERIFY_STATUS_LABELS,
  ACCOUNT_STATUS_LABELS,
  ACCOUNT_BIND_STATUS_LABELS,
  REGISTRATION_STATUS_LABELS,
  DATA_QUALITY_STATUS_LABELS,
  RISK_FLAG_LABELS
} from '../constants/student.constants'

const pick = (map) => (v) => map[v] || v || '—'

export const formatGender = pick(GENDER_LABELS)
export const formatEducationLevel = pick(EDUCATION_LEVEL_LABELS)
export const formatStudentType = pick(STUDENT_TYPE_LABELS)
export const formatStudentStatus = pick(STUDENT_STATUS_LABELS)
export const formatAcademicStatus = pick(ACADEMIC_STATUS_LABELS)
export const formatIdentityVerifyStatus = pick(IDENTITY_VERIFY_STATUS_LABELS)
export const formatAccountStatus = pick(ACCOUNT_STATUS_LABELS)
export const formatBindStatus = pick(ACCOUNT_BIND_STATUS_LABELS)
export const formatRegistrationStatus = pick(REGISTRATION_STATUS_LABELS)
export const formatDataQuality = pick(DATA_QUALITY_STATUS_LABELS)
export const formatRiskFlag = pick(RISK_FLAG_LABELS)

/** 组织归属一行文案：学院 / 专业 / 班级 */
export function formatOrg(s) {
  return [s.collegeName, s.majorName, s.className].filter(Boolean).join(' / ')
}
