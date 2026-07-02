/**
 * 学生主档 — 安全封装（脱敏 + 权限 + 数据范围）。
 * 脱敏：全部复用 @/security sensitive-mask（禁止本模块自造规则、禁止 console 输出敏感原文）。
 * 权限：统一入口 hasStudentPermission —— 先走 workflow permissionContext；
 *   mock 阶段 SCHOOL_ADMIN 对 student.* 默认放行（真实权限点配置在 P8 由权限中心下发，届时删除放行分支）。
 */
import { maskIdCard, maskPhone, maskAddress, maskName, maskEmail } from '@/security'
import {
  canClickButton,
  canAccessPage,
  hasRole,
  getDataScope
} from '@/modules/workflow/context/permission.context'
import { ROLE_CODE, DATA_SCOPE_LABELS } from '@/modules/workflow/constants/workflow.constants'

export { maskIdCard, maskPhone, maskAddress, maskName, maskEmail }

/** 列表/详情通用：返回脱敏后的展示对象（原对象不改） */
export function maskStudentForDisplay(s) {
  if (!s) return s
  return {
    ...s,
    idCard: s.idCard ? maskIdCard(s.idCard) : '',
    phone: s.phone ? maskPhone(s.phone) : '',
    email: s.email ? maskEmail(s.email) : '',
    homeAddress: s.homeAddress ? maskAddress(s.homeAddress) : '',
    currentAddress: s.currentAddress || ''
  }
}

export function maskGuardianForDisplay(g) {
  if (!g) return g
  return {
    ...g,
    guardianPhone: g.guardianPhone ? maskPhone(g.guardianPhone) : '',
    guardianIdCard: g.guardianIdCard ? maskIdCard(g.guardianIdCard) : '',
    guardianAddress: g.guardianAddress ? maskAddress(g.guardianAddress) : ''
  }
}

/**
 * 学生域权限判断唯一入口。
 * TODO(P8): 权限中心把 student.* 权限点按角色下发后，删除 SCHOOL_ADMIN 放行分支。
 */
export function hasStudentPermission(permissionKey) {
  if (canClickButton(permissionKey) || canAccessPage(permissionKey)) return true
  if (hasRole(ROLE_CODE.SCHOOL_ADMIN) && String(permissionKey).startsWith('student.')) return true
  return false
}

/** 当前数据范围提示（StudentDataScopeHint 消费） */
export function getStudentDataScopeHint() {
  const { scope } = getDataScope()
  return { scope, label: DATA_SCOPE_LABELS[scope] || scope }
}
