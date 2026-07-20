/**
 * authContext（mock）— 登录态/会话/强制改密/MFA 的统一前端入口。
 * 当前为纯前端 mock，不接真实认证后端；P11+ 替换 MOCK_AUTH 数据来源，函数签名冻结不变。
 * 与 workflow permissionContext 的分工：auth 管"你是谁/会话是否有效"，permission 管"你能做什么"。
 *
 * SECURITY-P0 · token 存储安全（docs/security/05-token与会话安全建议.md）：
 * 当前为纯内存 mock（刷新即失），未把 token 写入 localStorage/sessionStorage —— 保持该约束。
 * TODO(P11+ 接真实认证时)：
 *  1. 生产环境优先使用 HttpOnly + Secure + SameSite=Lax/Strict Cookie 承载会话，前端 JS 不可读；
 *  2. 若必须前端持有 accessToken，只放内存并缩短有效期（≤30min），配合 refresh token 静默续期；
 *  3. 禁止将 token / refreshToken 写入 localStorage（XSS 即失守）；
 *  4. 登出与 401/419 必须清空内存态（clearAuthContext 已提供）。
 */
import { reactive, readonly } from 'vue'
import { SESSION_POLICY } from '../constants/security.constants'
import { currentUserFromToken, getToken } from '@/services/http/client'

function nowIso() {
  return new Date().toISOString()
}

/** mock 登录态（与 workflow currentPermissionContext 的学校管理员身份保持一致） */
const MOCK_AUTH = {
  userId: 'u-admin-001',
  username: 'school_admin',
  displayName: '学校管理员',
  roles: ['SCHOOL_ADMIN'],
  tenantId: 'tenant-demo-a',
  schoolId: 'tenant-demo-a',
  schoolName: '演示职业技术学院',
  collegeId: '',
  classId: '',
  loginAt: nowIso(),
  lastActiveAt: nowIso(),
  mfaEnabled: false, // MFA 预留：真实阶段由认证服务返回
  forcePasswordChange: false, // 首次登录强制改密预留
  sessionExpireAt: new Date(Date.now() + SESSION_POLICY.PC_TIMEOUT_MS).toISOString(),
  maxConcurrentSessions: SESSION_POLICY.MAX_CONCURRENT_SESSIONS,
  currentDevice: 'pc-web'
}

const state = reactive({ auth: { ...MOCK_AUTH } })

/**
 * 用真实登录 token 覆盖身份类字段（userId/username/displayName/roles/tenantId/schoolName）。
 * 此前这些字段固定为 MOCK_AUTH 常量，不随真实登录变化——不同账号登录后工作台问候语、
 * 顶栏水印(SecurityWatermark)、前端审计事件里的操作人始终显示同一个硬编码"学校管理员"，
 * 只有真实调用 loginWithPassword 后再切到别的账号才会发现（同一账号登录时刚好对不上）。
 * MFA/强制改密/会话超时时间等真实后端尚未提供的字段维持 mock 占位，不在此处伪造。
 * 挂在 getAuthContext() 里逐次同步，而不是要求 client.js 反向 import 本模块去主动通知——
 * 避免与 client.js 之间出现循环依赖，任何调用方读取时都能拿到当下 token 对应的身份。
 */
function syncAuthFromRealToken() {
  const token = getToken()
  const u = token ? currentUserFromToken() : null
  if (!u) {
    if (state.auth.userId) clearAuthContext()
    return
  }
  if (state.auth.userId === u.userId && state.auth.roles[0] === u.currentRoleCode) return
  state.auth.userId = u.userId || ''
  state.auth.username = u.loginName || ''
  state.auth.displayName = u.realName || u.loginName || ''
  state.auth.roles = u.currentRoleCode ? [u.currentRoleCode] : []
  state.auth.tenantId = u.tenantId || ''
  state.auth.schoolId = u.tenantId || ''
  state.auth.schoolName = u.tenantName || ''
  state.auth.loginAt = nowIso()
  state.auth.lastActiveAt = nowIso()
}

/** 获取当前认证上下文（只读引用，读取前先与真实 token 同步身份字段） */
export function getAuthContext() {
  syncAuthFromRealToken()
  return readonly(state.auth)
}

export function isAuthenticated() {
  syncAuthFromRealToken()
  return !!state.auth.userId && !isSessionExpired()
}

/** 会话是否过期（基于 lastActiveAt + 端超时策略） */
export function isSessionExpired() {
  const last = new Date(state.auth.lastActiveAt).getTime()
  const timeout =
    state.auth.currentDevice === 'pc-web' ? SESSION_POLICY.PC_TIMEOUT_MS : SESSION_POLICY.MOBILE_TIMEOUT_MS
  return Date.now() - last > timeout
}

export function shouldForcePasswordChange() {
  return !!state.auth.forcePasswordChange
}

export function hasMfaEnabled() {
  return !!state.auth.mfaEnabled
}

/** 用户有操作时刷新活跃时间（路由跳转/请求成功时调用） */
export function refreshLastActive() {
  state.auth.lastActiveAt = nowIso()
  const timeout =
    state.auth.currentDevice === 'pc-web' ? SESSION_POLICY.PC_TIMEOUT_MS : SESSION_POLICY.MOBILE_TIMEOUT_MS
  state.auth.sessionExpireAt = new Date(Date.now() + timeout).toISOString()
}

/** 登出/会话失效时清空（保留结构，字段置空） */
export function clearAuthContext() {
  Object.keys(state.auth).forEach((k) => {
    state.auth[k] = typeof state.auth[k] === 'number' ? 0 : typeof state.auth[k] === 'boolean' ? false : ''
  })
}

/** 仅供演示/测试：重置为 mock 登录态 */
export function resetAuthContextForDemo() {
  Object.assign(state.auth, { ...MOCK_AUTH, loginAt: nowIso(), lastActiveAt: nowIso() })
}
