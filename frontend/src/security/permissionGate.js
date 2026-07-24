/**
 * 业务中心路由权限门（纵深防御 + UX）。
 *
 * ⚠️ 安全声明：这是前端纵深防御层，不是安全边界。真正越权拦截由后端
 *    require_permission（模块授权 + 角色 + 数据范围 + 业务关系）完成。
 *
 * 机制：各中心 getContext / 路由守卫 ensurePermissionPatterns 拿到 permissionPatterns 后
 *   调用 setPermissionPatterns；router.beforeEach 调用 canEnterRoute 消费 to.meta.permissionKey。
 *
 * 门禁口径：
 *   1. 拦截声明了 moduleCode∈GUARDED_MODULES 且带 permissionKey 的业务路由。
 *   2. patterns 未知时：守卫应先 await ensurePermissionPatterns；仍未知则正式环境 fail-closed。
 *   3. 缺少 permissionKey：正式环境 fail-closed；开发环境 warn 后放行。
 *   4. 后端仍是最终安全边界。
 */
import { matchPermission } from '../config/navPlan.js'

/** 纳入本门拦截的业务中心 moduleCode（与路由 meta.moduleCode 对齐）。 */
export const GUARDED_MODULES = new Set([
  'STUDENT_AFFAIRS',
  'INTERNSHIP',
  'GRADUATION',
  'ACADEMIC_AFFAIRS',
  'CAMPUS_SERVICE',
  'EMPLOYMENT',
  'ORIENTATION',
  'SYSTEM',
  'WORKBENCH',
  'PLATFORM',
])

let _patterns = null // null=未知；数组=已知
let _moduleEntitlements = null // null=未知；数组=已知
let _ensurePromise = null

function _isProd() {
  try {
    return !!(typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.PROD)
  } catch {
    return false
  }
}

/** 由 getContext 落库当前身份权限码模式集（与后端 enforce_permission 同一套码）。 */
export function setPermissionPatterns(patterns) {
  _patterns = Array.isArray(patterns) ? patterns : null
}

export function getPermissionPatterns() {
  return _patterns
}

/** 可选：模块授权集合（来自 current-context / 租户 entitlement）。null=未配置，不拦截模块。 */
export function setModuleEntitlements(codes) {
  if (codes == null) {
    _moduleEntitlements = null
    return
  }
  _moduleEntitlements = Array.isArray(codes) ? codes : Array.from(codes)
}

export function getModuleEntitlements() {
  return _moduleEntitlements
}

/** 登出 / 强制重算时清空。 */
export function clearPermissionPatterns() {
  _patterns = null
  _moduleEntitlements = null
  _ensurePromise = null
}

/**
 * 冷加载时拉取 /rbac/current-context 并落库 patterns，避免「先进页再 403」。
 * 失败时正式环境保持 patterns=null（随后 canEnterRoute fail-closed）。
 */
export async function ensurePermissionPatterns(requestFn) {
  if (Array.isArray(_patterns)) return _patterns
  if (_ensurePromise) return _ensurePromise
  if (typeof requestFn !== 'function') return null
  _ensurePromise = (async () => {
    try {
      const ctx = await requestFn('/rbac/current-context')
      if (Array.isArray(ctx?.permissionPatterns)) {
        setPermissionPatterns(ctx.permissionPatterns)
      }
      if (Array.isArray(ctx?.moduleEntitlements)) {
        setModuleEntitlements(ctx.moduleEntitlements)
      }
      return _patterns
    } catch {
      return null
    } finally {
      _ensurePromise = null
    }
  })()
  return _ensurePromise
}

const MODULE_CODE_TO_KEYS = {
  STUDENT_AFFAIRS: ['studentAffairs', 'STUDENT_AFFAIRS'],
  INTERNSHIP: ['internship', 'INTERNSHIP'],
  GRADUATION: ['graduation', 'graduationDesign', 'GRADUATION'],
  ACADEMIC_AFFAIRS: ['academicAffairs', 'academicLegacy', 'ACADEMIC_AFFAIRS'],
  CAMPUS_SERVICE: ['campusService', 'CAMPUS_SERVICE'],
  EMPLOYMENT: ['employment', 'EMPLOYMENT'],
  ORIENTATION: ['orientation', 'ORIENTATION'],
  SYSTEM: ['systemAdmin', 'system', 'SYSTEM', 'auditLog'],
  WORKBENCH: ['workbench', 'todoMessage', 'WORKBENCH', 'approval'],
  PLATFORM: ['platform', 'PLATFORM', 'apiAccess'],
}

function moduleEntitled(moduleCode) {
  if (!Array.isArray(_moduleEntitlements)) return true // 未下发时不在前端阻断（后端仍是边界）
  if (_moduleEntitlements.includes('*')) return true
  const keys = MODULE_CODE_TO_KEYS[moduleCode] || [moduleCode, String(moduleCode || '').toLowerCase()]
  return keys.some((k) => _moduleEntitlements.includes(k))
}

/**
 * 路由守卫判定：是否允许进入该路由。
 * @param {object} meta 目标路由 to.meta（含 moduleCode / permissionKey）
 * @returns {boolean} false=拦截（跳 403）
 */
export function canEnterRoute(meta) {
  if (!meta || !GUARDED_MODULES.has(meta.moduleCode)) return true
  const key = meta.permissionKey
  const prod = _isProd()

  if (!moduleEntitled(meta.moduleCode)) {
    return false
  }

  if (!key) {
    if (prod) return false
    // DEV only: missing key is not silently treated as authorized in production.
    return true
  }

  if (!Array.isArray(_patterns)) {
    if (prod) return false
    return true
  }

  return matchPermission(_patterns, key)
}

export default {
  GUARDED_MODULES,
  setPermissionPatterns,
  getPermissionPatterns,
  setModuleEntitlements,
  getModuleEntitlements,
  clearPermissionPatterns,
  ensurePermissionPatterns,
  canEnterRoute,
}
