import { currentUserFromToken, request } from '@/services/http/client'
import {
  getPermissionPatterns,
  setModuleAccessHealth,
  setModuleEntitlements,
  setPermissionPatterns,
  setRbacLoadFailed
} from '@/security/permissionGate'

const ROOT_ROLES = new Set(['PLATFORM_OWNER', 'PLATFORM_SUPER_ADMIN'])
let cachedSubjectId = ''
let cachedAt = 0
let cachedContext = null
const CACHE_MS = 15000

function identity() {
  const user = currentUserFromToken() || {}
  return {
    userId: String(user.userId || ''),
    loginName: String(user.loginName || ''),
    realName: String(user.realName || ''),
    userType: String(user.userType || '').trim().toUpperCase(),
    roleCode: String(user.currentRoleCode || '').trim().toUpperCase()
  }
}

export function isPlatformPrincipal() {
  const user = identity()
  return !!user.userId && (
    user.userType.startsWith('PLATFORM_') || user.roleCode.startsWith('PLATFORM_')
  )
}

export function isPlatformRoot() {
  const user = identity()
  return ROOT_ROLES.has(user.userType) || ROOT_ROLES.has(user.roleCode)
}

export function platformDutyPatterns(duties) {
  const normalized = new Set(
    (Array.isArray(duties) ? duties : [])
      .map((item) => String(item || '').trim())
      .filter(Boolean)
  )
  if (normalized.has('*')) return ['platform.*']

  const patterns = new Set(Array.from(normalized, (duty) => `platform.${duty}`))
  // Frozen page keys predate delegated duties. These aliases are UI-only mirrors
  // of the exact backend read capabilities; they do not create new authority.
  if (normalized.has('commercial.view')) {
    patterns.add('platform.package.view')
    patterns.add('platform.order.view')
  }
  return Array.from(patterns).sort()
}

export function resolvePlatformHome(context = cachedContext) {
  if (isPlatformRoot()) return '/admin/platform/overview'
  const duties = new Set(Array.isArray(context?.duties) ? context.duties : [])
  if (duties.has('access.review')) return '/admin/platform/access'
  if (duties.has('commercial.view')) return '/admin/platform/orders'
  if (duties.has('audit.view')) return '/admin/platform/audit'
  if (duties.has('tenant.view')) return '/admin/platform/tenants'
  return '/security/403'
}

export function toPlatformUiContext(context = cachedContext) {
  if (!context) return null
  const user = identity()
  const duties = Array.isArray(context.duties) ? context.duties : []
  const root = duties.includes('*')
  const roleCode = String(context.roleCode || user.roleCode || user.userType || 'PLATFORM').toUpperCase()
  const operatorName = user.realName || user.loginName || roleCode
  return {
    tenantBrandConfig: {
      tenantId: '0',
      operatorName,
      schoolName: '',
      platformDisplayName: '高校学生全生命周期管理平台',
      schoolLogo: '',
      schoolBadge: '',
      brandColor: '#2563eb',
      watermarkText: '平台运营数据 · 严禁外传'
    },
    currentRole: {
      userId: String(context.subjectId || user.userId),
      userName: operatorName,
      roleCode,
      roleName: roleCode
    },
    dataScope: {
      scopeCode: root ? 'PLATFORM_ALL' : 'PLATFORM_CAPABILITY',
      scopeName: root ? '全平台控制面' : `平台主管职责：${duties.join('、') || '无已授权能力'}`
    },
    platformAccessContext: context,
    permissionPatterns: platformDutyPatterns(duties)
  }
}

export async function ensurePlatformAccessContext({ force = false } = {}) {
  if (!isPlatformPrincipal()) {
    cachedSubjectId = ''
    cachedAt = 0
    cachedContext = null
    return null
  }

  const subjectId = identity().userId
  const patterns = getPermissionPatterns()
  if (
    !force && cachedContext && cachedSubjectId === subjectId &&
    Date.now() - cachedAt < CACHE_MS && Array.isArray(patterns) &&
    patterns.some((item) => String(item).startsWith('platform.'))
  ) {
    return cachedContext
  }

  try {
    const context = await request('/platform/context', { forceProbe: true })
    if (String(context?.principalPlane || '').toUpperCase() !== 'PLATFORM') {
      throw new Error('平台上下文 principalPlane 非 PLATFORM，拒绝进入控制面')
    }
    if (String(context?.subjectId || '') !== subjectId) {
      throw new Error('平台上下文主体与当前 access token 不一致')
    }
    setPermissionPatterns(platformDutyPatterns(context?.duties))
    setModuleEntitlements(null)
    setModuleAccessHealth(true, '')
    setRbacLoadFailed(false)
    cachedSubjectId = subjectId
    cachedAt = Date.now()
    cachedContext = context
    return context
  } catch (error) {
    cachedSubjectId = ''
    cachedAt = 0
    cachedContext = null
    setPermissionPatterns(null)
    setRbacLoadFailed(true, error?.message || '平台主管能力上下文加载失败')
    return null
  }
}

export function clearPlatformAccessCache() {
  cachedSubjectId = ''
  cachedAt = 0
  cachedContext = null
}