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
import { moduleEntitled } from './moduleEntitlement.js'

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
  'APPROVAL',
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

function _isRetryablePermissionAbort(error) {
  const name = String(error?.name || '').toLowerCase()
  const code = String(error?.code || '').toLowerCase()
  const message = String(error?.message || '').toLowerCase()
  return name === 'aborterror' ||
    code === 'abort_err' ||
    code === 'err_canceled' ||
    message.includes('signal is aborted') ||
    message.includes('aborted without reason') ||
    message.includes('the user aborted a request')
}

function _retryDelay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function _loadPermissionContext(requestFn) {
  const maxAttempts = 3
  let lastError = null
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      return await requestFn('/rbac/current-context', { forceProbe: true })
    } catch (error) {
      lastError = error
      if (!_isRetryablePermissionAbort(error) || attempt === maxAttempts - 1) throw error
      await _retryDelay(90 * (attempt + 1))
    }
  }
  throw lastError
}

export function setPermissionPatterns(patterns) {
  _patterns = Array.isArray(patterns) ? patterns : null
}

export function getPermissionPatterns() {
  return _patterns
}

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

export function clearPermissionPatterns() {
  _patterns = null
  _moduleEntitlements = null
  _moduleAccessHealthy = true
  _moduleAccessError = ''
  _rbacLoadFailed = false
  _rbacLoadError = ''
  _ensurePromise = null
}

export async function ensurePermissionPatterns(requestFn) {
  if (Array.isArray(_patterns) && !_rbacLoadFailed) return _patterns
  if (_ensurePromise) return _ensurePromise
  if (typeof requestFn !== 'function') return null
  _ensurePromise = (async () => {
    try {
      const ctx = await _loadPermissionContext(requestFn)
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

function currentModuleEntitled(moduleCode) {
  return moduleEntitled(moduleCode, _moduleEntitlements, _moduleAccessHealthy)
}

export function canEnterRoute(meta) {
  if (!meta || !GUARDED_MODULES.has(meta.moduleCode)) return true
  const key = meta.permissionKey
  const prod = _isProd()

  if (_rbacLoadFailed) return false
  if (!currentModuleEntitled(meta.moduleCode)) return false

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

  if (anyKeys.length) return anyKeys.some((k) => matchPermission(_patterns, k))
  if (key) return matchPermission(_patterns, key)
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
