/**
 * SECURITY-P0 · 权限型脱敏（按 currentRole / dataScope / permissionActions 决定能否看明文）。
 *
 * 角色规则（docs/security/02-敏感字段脱敏规则.md §4，fail-closed：判断不出=脱敏）：
 *  - 学生本人：可看自己的完整手机号；证件号仍默认部分脱敏
 *  - 辅导员：可看所负责学生的必要联系方式（phone/emergencyPhone）
 *  - 指导教师：默认不看身份证、家庭住址
 *  - 就业老师：默认不看身份证、家庭住址
 *  - 学院管理员：按数据范围可看部分敏感信息（联系方式类）
 *  - 平台运营：默认不能看学校学生敏感明文（租户隔离）
 *  - 系统管理员：不能默认绕过业务数据脱敏（管系统不管业务明文）
 *
 * 注意：本模块只管"展示层"。真正的字段级授权必须由后端完成；
 * 后端返回明文≠前端必须展示明文，后端返回脱敏值时前端不做"还原"。
 */
import { maskByKind } from './mask'
import { getFieldKind } from './sensitive-fields'

/** 角色类别推断：兼容 roleType（SCHOOL_ADMIN…）与各模块 roleCode/roleName 习惯命名 */
export function resolveRoleCategory(ctx = {}) {
  const role = ctx.currentRole || {}
  const type = String(role.roleType || role.type || '').toUpperCase()
  const code = String(role.roleCode || role.roleId || '').toLowerCase()
  const name = String(role.roleName || '')
  if (type === 'PLATFORM' || code.includes('ops') || code.includes('platform') || name.includes('平台')) return 'platform'
  if (type === 'AUDITOR' || name.includes('审计')) return 'auditor'
  if (code.includes('sysadmin') || code.includes('system') || name.includes('系统管理')) return 'sysadmin'
  if (code.includes('counselor') || name.includes('辅导员')) return 'counselor'
  if (code.includes('advisor') || code.includes('mentor') || name.includes('导师') || name.includes('指导教师')) return 'advisor'
  if (code.includes('employ') || name.includes('就业')) return 'employment'
  if (type === 'SCHOOL_ADMIN' || code.includes('college') || code.includes('admin') || name.includes('管理员')) return 'collegeAdmin'
  if (type === 'ACADEMIC_STAFF' || name.includes('教务') || name.includes('学籍')) return 'academicStaff'
  if (code.includes('student') || name.includes('学生')) return 'student'
  return 'unknown'
}

/** 各角色可看明文的字段类别白名单（不在表内=脱敏；unknown 角色一律脱敏） */
const ROLE_PLAIN_ALLOW = Object.freeze({
  student: Object.freeze(['phone', 'email']), // 仅限本人记录，见 isSelf 判断
  counselor: Object.freeze(['phone', 'emergencyPhone', 'email']),
  advisor: Object.freeze(['phone']),
  employment: Object.freeze(['phone', 'email']),
  collegeAdmin: Object.freeze(['phone', 'emergencyPhone', 'email']),
  academicStaff: Object.freeze(['phone']),
  sysadmin: Object.freeze([]), // 系统管理员不默认绕过业务脱敏
  platform: Object.freeze([]), // 平台运营不看学校学生敏感明文
  auditor: Object.freeze([]),
  unknown: Object.freeze([])
})

/** 永远需要脱敏展示的类别（任何角色 UI 默认不展示完整值） */
const ALWAYS_MASK_KINDS = Object.freeze(['idCard', 'bankCard', 'secret'])

/**
 * 是否可看明文。
 * @param {string} kindOrField 字段类别（phone/idCard/…）或字段名（phone/parentPhone/…）
 * @param {object} ctx 模块上下文 { currentRole, dataScope, permissionActions }
 * @param {object} opts { isSelf: 记录是否属于当前用户本人, inScope: 记录是否在当前数据范围内（默认 true） }
 */
export function canViewPlainField(kindOrField, ctx = {}, opts = {}) {
  const kind = getFieldKind(kindOrField) || kindOrField
  if (ALWAYS_MASK_KINDS.includes(kind)) return false
  /* permissionActions 显式授权优先（如 viewSensitive.enabled），仍不放行 ALWAYS_MASK */
  const pa = ctx.permissionActions || {}
  if (pa.viewSensitive && (pa.viewSensitive.enabled === true || pa.viewSensitive.visible === true)) return true
  const category = resolveRoleCategory(ctx)
  if (category === 'student' && !opts.isSelf) return false
  if (opts.inScope === false) return false // 数据范围之外一律脱敏
  return (ROLE_PLAIN_ALLOW[category] || []).includes(kind)
}

/**
 * 权限型脱敏取值：可看明文返回原值，否则返回脱敏值。
 * 用法：maskFieldByRole(row.phone, 'phone', ctx, { isSelf: row.studentId === ctx.currentUser?.id })
 */
export function maskFieldByRole(value, kindOrField, ctx = {}, opts = {}) {
  if (value === undefined || value === null || value === '') return ''
  if (canViewPlainField(kindOrField, ctx, opts)) return String(value)
  const kind = getFieldKind(kindOrField) || kindOrField
  return maskByKind(value, kind)
}
