/**
 * 07 就业服务中心 — 前端展示层常量（仅做“状态码 → 语义色”映射，文案以 mock/api 字典为准）。
 */

/** 就业去向 → 状态标签语义色 */
export const DESTINATION_TAG_TYPE = {
  SIGNED: 'success',
  FLEXIBLE: 'processing',
  FURTHER_STUDY: 'info',
  ENLISTED: 'info',
  STARTUP: 'processing',
  FREELANCE: 'processing',
  UNEMPLOYED: 'warning'
}

/** 核验状态 → 语义色 */
export const VERIFY_TAG_TYPE = {
  PENDING_VERIFY: 'warning',
  VERIFIED: 'success',
  RETURNED: 'danger'
}

/** 材料审核状态 → 语义色 */
export const MATERIAL_TAG_TYPE = {
  SUBMITTED: 'warning',
  REVIEWING: 'processing',
  APPROVED: 'success',
  RETURNED: 'warning',
  REJECTED: 'danger'
}

/** 帮扶级别 → 语义色 */
export const HELP_TAG_TYPE = {
  NORMAL: 'default',
  KEY_HELP: 'danger'
}

/** 记录状态 → 语义色 */
export const RECORD_TAG_TYPE = {
  ACTIVE: 'success',
  VOIDED: 'default'
}

/** 跟进状态 → 语义色 */
export const FOLLOWUP_TAG_TYPE = {
  OPEN: 'processing',
  CLOSED: 'success',
  VOIDED: 'default'
}

/** 企业/岗位状态 → 语义色 */
export const COMPANY_TAG_TYPE = {
  ACTIVE: 'success',
  DISABLED: 'default'
}
export const JOB_TAG_TYPE = {
  OPEN: 'success',
  CLOSED: 'default'
}

/** 字典数组 → { value: label } 映射 */
export const toLabelMap = (options = []) =>
  Object.fromEntries(options.map((o) => [o.value, o.label]))
