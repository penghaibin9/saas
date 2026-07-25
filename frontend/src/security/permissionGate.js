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
 *   4. 权限服务加载失败：不得伪装成「无权限」——走 permission-service 原因页。
 *   5. 后端仍是最终安全边界。
 */
import { matchPermission } from '../config/navPlan.js'

/** 纳入本门拦截的业务中心 moduleCode（与路由 meta.moduleCode 对齐）。 */
export const GUARDED_MODULES = new Set([
  'STUDENT',
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
let _moduleEntitlements = null // null=未知/未下发；数组=已知（含空数组=明确无授权）
let _moduleAccessHealthy = true
let _moduleAccessError = ''
let _rbacLoadFailed = false
let _rbacLoadError = ''
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

export function setModuleAccessHealth(healthy, error = '') {
  _moduleAccessHealthy = healthy !== false
  _moduleAccessError = error || ''
}

export function getModuleAccessHealth() {
  return { healthy: _moduleAccessHealthy, error: _moduleAccessError }
}

export function setRbacLoadFailed(failed, error = '') {
  _rbacLoadFailed = !!failed
  _rbacLoadError = failed ? (error || '权限服务加载失败') : ''
}

export function getRbacLoadFailed() {
  return _rbacLoadFailed ? (_rbacLoadError || '权限服务加载失败') : ''
}

/** 登出 / 强制重算时清空。 */
export function clearPermissionPatterns() {
  _patterns = null
  _moduleEntitlements = null
  _moduleAccessHealthy = true
  _moduleAccessError = ''
  _rbacLoadFailed = false
  _rbacLoadError = ''
  _ensurePromise = null
}

/**
 * 冷加载时拉取 /rbac/current-context 并落库 patterns，避免「先进页再 403」。
 * 失败时正式环境保持 patterns=null，并标记 rbacLoadFailed（不得伪装成无权限）。
 */
export async function ensurePermissionPatterns(requestFn) {
  if (Array.isArray(_patterns) && !_rbacLoadFailed) return _patterns
  if (_ensurePromise) return _ensurePromise
  if (typeof requestFn !== 'function') return null
  _ensurePromise = (async () => {
    try {
      const ctx = await requestFn('/rbac/current-context')
      setRbacLoadFailed(false)
      if (ctx && ctx.moduleAccessHealthy === false) {
        setModuleAccessHealth(false, ctx.moduleAccessError || '模块授权计算失败')
        setModuleEntitlements(null)
      } else {
        setModuleAccessHealth(true, '')
        if (Array.isArray(ctx?.moduleEntitlements)) {
          setModuleEntitlements(ctx.moduleEntitlements)
        }
      }
      if (Array.isArray(ctx?.permissionPatterns)) {
        setPermissionPatterns(ctx.permissionPatterns)
      }
      return _patterns
    } catch (e) {
      setRbacLoadFailed(true, e?.message || '权限服务加载失败')
      return null
    } finally {
      _ensurePromise = null
    }
  })()
  return _ensurePromise
}

const MODULE_CODE_TO_KEYS = {
  // 对齐 shared/contracts/module-manifest.json 的 studentProfile（别名 student360）
  STUDENT: ['studentProfile', 'student360', 'student', 'STUDENT'],
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
  // 授权计算失败：不得按「未购买」拦截；由布局展示服务错误，后端 require_module 仍是边界
  if (!_moduleAccessHealthy) return true
  if (!Array.isArray(_moduleEntitlements)) return true // 未下发时不在前端阻断
  if (_moduleEntitlements.includes('*')) return true
  const keys = MODULE_CODE_TO_KEYS[moduleCode] || [moduleCode, String(moduleCode || '').toLowerCase()]
  return keys.some((k) => _moduleEntitlements.includes(k))
}

/**
 * 路由守卫判定：是否允许进入该路由。
 * @param {object} meta 目标路由 to.meta（含 moduleCode / permissionKey）
 * @returns {boolean} false=拦截（跳 403；若权限服务失败见 getRbacLoadFailed）
 */
export function canEnterRoute(meta) {
  if (!meta || !GUARDED_MODULES.has(meta.moduleCode)) return true
  const key = meta.permissionKey
  const prod = _isProd()

  if (_rbacLoadFailed) {
    return false
  }

  if (!moduleEntitled(meta.moduleCode)) {
    return false
  }

  // permissionAny：任一命中即可进入（如导入导出同页，有 import 或 export 之一即可）
  // permissionAll：需全部命中。三者按 permissionKey → permissionAny → permissionAll 取第一个声明的。
  const anyKeys = Array.isArray(meta.permissionAny) ? meta.permissionAny.filter(Boolean) : []
  const allKeys = Array.isArray(meta.permissionAll) ? meta.permissionAll.filter(Boolean) : []

  if (!key && !anyKeys.length && !allKeys.length) {
    if (prod) return false
    return true
  }

  if (!Array.isArray(_patterns)) {
    if (prod) return false
    return true
  }

  if (key) return matchPermission(_patterns, key)
  if (anyKeys.length) return anyKeys.some((k) => matchPermission(_patterns, k))
  return allKeys.every((k) => matchPermission(_patterns, k))
}

export default {
  GUARDED_MODULES,
  setPermissionPatterns,
  getPermissionPatterns,
  setModuleEntitlements,
  getModuleEntitlements,
  setModuleAccessHealth,
  getModuleAccessHealth,
  setRbacLoadFailed,
  getRbacLoadFailed,
  clearPermissionPatterns,
  ensurePermissionPatterns,
  canEnterRoute,
}
