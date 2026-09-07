import { request } from '@/services/http/client'
import { toast } from '@/utils/toast'

/**
 * System-management compatibility bridge for the hardened school Authority.
 *
 * The system pages historically called a few mutation helpers without carrying
 * expectedVersion because the old endpoints did not require it. The control
 * plane hardening makes object versions and post-commit cache receipts explicit.
 * This module upgrades those calls inside /admin/system only:
 * - remember versions from authoritative reads;
 * - send expectedVersion on account/role/brand mutations;
 * - if a durable write committed but auth-cache invalidation failed, run the
 *   cache-only recovery endpoint and NEVER replay the business mutation.
 */

const VERSION_MISSING = '未取得当前版本，请刷新页面后再操作'
const state = {
  installed: false,
  brandVersion: null,
  userVersions: new Map(),
  roleVersions: new Map()
}

function validVersion(value) {
  return Number.isInteger(value) && value >= 0
}

function rememberVersion(map, id, value) {
  if (id == null || !validVersion(value)) return
  map.set(String(id), value)
}

function rememberUsers(data) {
  if (Array.isArray(data?.list)) data.list.forEach((row) => rememberVersion(state.userVersions, row?.id, row?.version))
  if (data?.id != null) rememberVersion(state.userVersions, data.id, data.version)
}

function rememberRoles(data) {
  if (Array.isArray(data?.list)) data.list.forEach((row) => rememberVersion(state.roleVersions, row?.id, row?.version))
  if (data?.id != null) rememberVersion(state.roleVersions, data.id, data.version)
}

function rememberBrand(data) {
  if (validVersion(data?.version)) state.brandVersion = data.version
}

function fail(message = VERSION_MISSING) {
  return Promise.resolve({ code: 1, data: null, message })
}

function apiError(error) {
  return {
    code: error?.code || 1,
    data: null,
    message: error?.message || '请求失败',
    bizCode: error?.bizCode || '',
    details: error?.details
  }
}

async function authorityRequest(path, { method = 'POST', body } = {}) {
  try {
    const data = await request(path, { method, ...(body === undefined ? {} : { body }) })
    return { code: 0, data, message: 'ok' }
  } catch (error) {
    return apiError(error)
  }
}

async function recoverSubject(userId) {
  return authorityRequest(`/system/users/${encodeURIComponent(userId)}/auth-cache/recover`, { method: 'POST' })
}

async function recoverTenant() {
  return authorityRequest('/system/auth-cache/recover', { method: 'POST' })
}

async function settleCommittedReceipt(result, { label, recover, remember } = {}) {
  if (!result || result.code !== 0) return result
  if (typeof remember === 'function') remember(result.data)
  if (result.data?.cacheRecoveryRequired !== true) return result

  // The database mutation is already durable. Only the idempotent cache-recovery
  // command is allowed here; replaying the original write can duplicate effects.
  const recovery = await recover()
  if (recovery.code === 0 && recovery.data?.cacheRecoveryRequired !== true && recovery.data?.cacheInvalidated !== false) {
    if (typeof remember === 'function') remember(recovery.data)
    toast.warning(`${label}已提交；权限缓存曾刷新失败，现已执行缓存恢复。原业务操作没有重放。`)
    return {
      ...result,
      data: {
        ...result.data,
        cacheInvalidated: true,
        cacheRecoveryRequired: false,
        cacheRecovered: true,
        originalCacheWarning: result.data?.warning || ''
      }
    }
  }

  toast.error(`${label}已提交，但权限缓存恢复仍失败。请不要重复提交原操作，刷新后从系统治理入口继续处理缓存。`)
  return {
    ...result,
    data: {
      ...result.data,
      cacheRecoveryRequired: true,
      cacheRecoveryAttempted: true,
      cacheRecoveryError: recovery.message || '缓存恢复失败'
    }
  }
}

function expectedVersion(explicit, cached) {
  if (validVersion(explicit)) return explicit
  return validVersion(cached) ? cached : null
}

function normalizeAssignments(roleAssignments) {
  if (!Array.isArray(roleAssignments)) return undefined
  return roleAssignments.map((item) => ({
    roleCode: item.roleCode,
    scopeType: item.scopeType,
    scopeIds: item.scopeIds || []
  }))
}

export function installSystemAuthorityCompatibility(systemApi) {
  if (state.installed) return systemApi
  if (!systemApi || typeof systemApi !== 'object') throw new Error('systemApi 不可用，无法安装系统管理 Authority 兼容层')
  state.installed = true

  const original = {
    getUsers: systemApi.getUsers.bind(systemApi),
    getUserDetail: systemApi.getUserDetail.bind(systemApi),
    updateUser: systemApi.updateUser.bind(systemApi),
    setUserStatus: systemApi.setUserStatus.bind(systemApi),
    resetUserPassword: systemApi.resetUserPassword.bind(systemApi),
    getRoles: systemApi.getRoles.bind(systemApi),
    getBrandConfig: systemApi.getBrandConfig.bind(systemApi),
    saveBrandConfig: systemApi.saveBrandConfig.bind(systemApi),
    batchDisableUsers: systemApi.batchDisableUsers.bind(systemApi)
  }

  systemApi.getUsers = async (...args) => {
    const result = await original.getUsers(...args)
    if (result.code === 0) rememberUsers(result.data)
    return result
  }

  systemApi.getUserDetail = async (...args) => {
    const result = await original.getUserDetail(...args)
    if (result.code === 0) rememberUsers(result.data)
    return result
  }

  systemApi.updateUser = async (id, payload = {}) => {
    const version = expectedVersion(payload.expectedVersion, state.userVersions.get(String(id)))
    if (version == null) return fail('未取得账号版本，已阻止无乐观锁的账号编辑')
    const result = await original.updateUser(id, { ...payload, expectedVersion: version })
    if (result.code === 0) rememberUsers(result.data)
    return result
  }

  systemApi.setUserStatus = async (id, options = {}) => {
    const version = expectedVersion(options.expectedVersion, state.userVersions.get(String(id)))
    if (version == null) return fail('未取得账号版本，已阻止无乐观锁的状态变更')
    const result = await original.setUserStatus(id, { ...options, expectedVersion: version })
    return settleCommittedReceipt(result, {
      label: options.action === 'DISABLE' ? '账号停用' : '账号状态变更',
      recover: () => recoverSubject(id),
      remember: rememberUsers
    })
  }

  systemApi.resetUserPassword = async (id, options = {}) => {
    const version = expectedVersion(options.expectedVersion, state.userVersions.get(String(id)))
    if (version == null) return fail('未取得账号版本，已阻止无乐观锁的密码重置')
    const result = await original.resetUserPassword(id, { ...options, expectedVersion: version })
    return settleCommittedReceipt(result, {
      label: '密码重置',
      recover: () => recoverSubject(id),
      remember: rememberUsers
    })
  }

  systemApi.assignUserRoles = async (id, roleCodes = [], roleAssignments, options = {}) => {
    const version = expectedVersion(options?.expectedVersion, state.userVersions.get(String(id)))
    if (version == null) return fail('未取得账号版本，已阻止无乐观锁的角色分配')
    const assignments = normalizeAssignments(roleAssignments)
    const result = await authorityRequest(`/system/users/${encodeURIComponent(id)}/roles`, {
      method: 'PUT',
      body: {
        roleCodes,
        ...(assignments ? { roleAssignments: assignments } : {}),
        expectedVersion: version
      }
    })
    return settleCommittedReceipt(result, {
      label: '账号角色分配',
      recover: () => recoverSubject(id),
      remember: rememberUsers
    })
  }

  systemApi.getRoles = async (...args) => {
    const result = await original.getRoles(...args)
    if (result.code === 0) rememberRoles(result.data)
    return result
  }

  systemApi.deprecateRole = async (id, { reason, expectedVersion: explicitVersion } = {}) => {
    const version = expectedVersion(explicitVersion, state.roleVersions.get(String(id)))
    if (version == null) return fail('未取得角色版本，已阻止无乐观锁的角色停用')
    const result = await authorityRequest(`/system/roles/${encodeURIComponent(id)}/status`, {
      method: 'PUT',
      body: { action: 'DISABLE', reason, expectedVersion: version }
    })
    return settleCommittedReceipt(result, {
      label: '角色停用',
      recover: recoverTenant,
      remember: rememberRoles
    })
  }

  systemApi.getBrandConfig = async (...args) => {
    const result = await original.getBrandConfig(...args)
    if (result.code === 0) rememberBrand(result.data)
    return result
  }

  systemApi.saveBrandConfig = async (payload = {}, options = {}) => {
    const version = expectedVersion(payload.expectedVersion ?? payload.version, state.brandVersion)
    if (version == null) return fail('未取得品牌版本，已阻止无乐观锁的品牌保存')
    const result = await original.saveBrandConfig({ ...payload, expectedVersion: version }, options)
    if (result.code === 0) rememberBrand(result.data)
    return result
  }

  systemApi.resetBrandConfig = async ({ reason, expectedVersion: explicitVersion } = {}) => {
    const version = expectedVersion(explicitVersion, state.brandVersion)
    if (version == null) return fail('未取得品牌版本，已阻止无乐观锁的恢复默认')
    const result = await authorityRequest('/system/brand/reset', {
      method: 'POST', body: { reason, expectedVersion: version }
    })
    if (result.code === 0) rememberBrand(result.data)
    return result
  }

  systemApi.batchDisableUsers = async (...args) => {
    const result = await original.batchDisableUsers(...args)
    if (result.code !== 0 || result.data?.cacheRecoveryRequired !== true) return result
    return settleCommittedReceipt(result, {
      label: '批量账号状态变更',
      recover: recoverTenant,
      remember: () => state.userVersions.clear()
    })
  }

  return systemApi
}

export const __authorityCompatibilityTest = {
  validVersion,
  expectedVersion,
  normalizeAssignments,
  rememberUsers,
  rememberRoles,
  rememberBrand,
  state
}
