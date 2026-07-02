/**
 * 00-SEC 前端安全基线 — 统一出口。
 * 声明：本目录为等保三级建设思路下的前端 mock/预留实现，不代表系统已通过等保测评。
 */
export * from './constants/security.constants'

export {
  getAuthContext,
  isAuthenticated,
  isSessionExpired,
  shouldForcePasswordChange,
  hasMfaEnabled,
  refreshLastActive,
  clearAuthContext
} from './auth/auth.context'

export {
  getSessionTimeoutMs,
  formatSessionRemainTime,
  createSessionWarningMessage
} from './auth/session.helper'

export {
  checkRouteAccess,
  resolveRouteFailure,
  getRouteRequiredPermission,
  getRouteSecurityMeta
} from './guards/route.guard'

export {
  getCurrentPermissionContext,
  canAccessSecurityPage,
  canClickSecurityButton,
  resolveSecurityDataScope,
  canShowMenu,
  filterMenusBySecurity
} from './guards/menu.guard'

export { canShowButton, canEnableButton, getDisabledReason } from './guards/button.guard'

export { checkRecordScope, filterRecordsByScope, getScopeDescription } from './guards/data-scope.guard'

export { canExport, validateExportRequest, createExportAuditEvent, getExportLimit } from './guards/export.guard'

export { canDownload, validateSignedUrl, createDownloadAuditEvent } from './guards/download.guard'

export { validateUploadFile, canUpload, getUploadPolicy } from './guards/upload.guard'

export {
  maskIdCard,
  maskPhone,
  maskName,
  maskAddress,
  maskBankCard,
  maskSalary,
  maskEmail,
  maskByLevel,
  maskStudentRecord
} from './helpers/sensitive-mask.helper'

export {
  createAuditEvent,
  createLoginAuditEvent,
  createPermissionAuditEvent,
  createApprovalAuditEvent,
  sanitizeAuditDetail,
  sendAuditEventToBackend,
  getPendingAuditEvents
} from './helpers/audit-event.helper'

export { getCsrfToken, attachCsrfHeader, validateCsrfRequired } from './helpers/csrf.helper'

export {
  getSafeMessage,
  getSecurityErrorRoute,
  isSecurityStatus,
  sanitizeErrorMessage
} from './helpers/security-error.helper'

export { secureRequest, handleSecurityError, createRequestId } from './request/secure-request.client'

export { default as SecurityWatermark } from './components/SecurityWatermark.vue'
