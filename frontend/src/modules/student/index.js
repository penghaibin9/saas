/**
 * 01 学生主档与身份中心 — 模块聚合出口。
 * 后续模块（迎新/实习/毕设/就业/驾驶舱/09A）统一从此处引用学生底座，禁止直引 mock。
 */
export * as studentProvider from './provider/student.provider'
export * from './constants/student.constants'
export * from './helpers/student-format.helper'
export * from './helpers/student-status.helper'
export {
  maskStudentForDisplay,
  maskGuardianForDisplay,
  hasStudentPermission,
  getStudentDataScopeHint,
  maskIdCard,
  maskPhone,
  maskAddress,
  maskName,
  maskEmail
} from './helpers/student-security.helper'
export { validateRejectReason, validateStatusChangeReason, validateGuardians } from './helpers/student-validate.helper'
export * from './rules/student.rules'
