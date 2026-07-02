/**
 * authContext（mock）— 登录态/会话/强制改密/MFA 的统一前端入口。
 * 当前为纯前端 mock，不接真实认证后端；P11+ 替换 MOCK_AUTH 数据来源，函数签名冻结不变。
 * 与 workflow permissionContext 的分工：auth 管"你是谁/会话是否有效"，permission 管"你能做什么"。
 */
import { reactive, readonly } from 'vue'
import { SESSION_POLICY } from '../constants/security.constants'

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

/** 获取当前认证上下文（只读引用） */
export function getAuthContext() {
  return readonly(state.auth)
}

export function isAuthenticated() {
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
