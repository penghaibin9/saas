/**
 * 02 数字迎新中心 — 前端展示层常量（状态码 → 语义色映射，文案以 mock/api 字典为准）。
 */

export const STAGE_TAG_TYPE = {
  ADMITTED: 'default',
  PRE_STUDENT_VERIFIED: 'processing',
  REGISTERED_PENDING_ENROLLMENT: 'success',
  ENROLLED: 'success',
  DEFERRED: 'warning',
  NO_SHOW: 'danger',
  CANCELLED: 'default'
}

export const REPORT_TAG_TYPE = {
  NOT_REPORTED: 'default',
  PREPARED: 'processing',
  CHECKED_IN: 'success',
  COLLEGE_CONFIRMED: 'success',
  DELAYED: 'warning',
  NO_SHOW: 'danger',
  ABNORMAL: 'danger'
}

export const PAYMENT_TAG_TYPE = {
  PAID: 'success',
  PARTIAL: 'warning',
  UNPAID: 'danger',
  DEFERRED: 'info',
  GREEN_CHANNEL: 'processing'
}

export const GREEN_TAG_TYPE = {
  NOT_APPLIED: 'default',
  SUBMITTED: 'warning',
  REVIEWING: 'processing',
  APPROVED: 'success',
  RETURNED: 'warning',
  REJECTED: 'danger',
  WITHDRAWN: 'default'
}

export const MATERIAL_TAG_TYPE = {
  NOT_UPLOADED: 'default',
  UPLOADED: 'warning',
  APPROVED: 'success',
  RETURNED: 'warning',
  REJECTED: 'danger'
}

export const DORM_TAG_TYPE = {
  UNASSIGNED: 'default',
  ASSIGNED: 'processing',
  CHECKED_IN: 'success',
  EXCEPTION: 'danger'
}

export const EXCEPTION_TAG_TYPE = {
  OPEN: 'warning',
  PROCESSING: 'processing',
  RESOLVED: 'success',
  ESCALATED: 'danger'
}

export const RECORD_TAG_TYPE = {
  ACTIVE: 'success',
  VOIDED: 'default'
}

/** 报到环节完成态 → 样式类语义 */
export const STEP_STATE_TYPE = {
  DONE: 'success',
  DOING: 'processing',
  BLOCKED: 'danger',
  TODO: 'default'
}

export const toLabelMap = (options = []) =>
  Object.fromEntries(options.map((o) => [o.value, o.label]))
