/**
 * 会话 store（学生 PC 门户）。accessToken 仅内存；仅 STUDENT 可进入。
 * 登出会先请求 browser-logout 清除/吊销 HttpOnly refresh cookie，再清理本地门户状态。
 */
import { defineStore } from 'pinia'
import { portalApi } from '../services/portalApi'
import { clearSession, getToken, request, setRefreshToken, setToken } from '../services/request'

const FORCE_PASSWORD_CHANGE_KEY = 'sp_force_password_change_v1'

function readForcePasswordChange() {
  try { return localStorage.getItem(FORCE_PASSWORD_CHANGE_KEY) === '1' } catch { return false }
}

function writeForcePasswordChange(required) {
  try {
    if (required) localStorage.setItem(FORCE_PASSWORD_CHANGE_KEY, '1')
    else localStorage.removeItem(FORCE_PASSWORD_CHANGE_KEY)
  } catch { /* 服务端门禁仍是最终真值 */ }
}

export const useSessionStore = defineStore('sp-session', {
  state: () => ({
    user: null,          // { userId, realName, userType, roleCode, studentNo, mustChangePassword }
    ready: false,
    mustChangePassword: readForcePasswordChange(),
    token: getToken()    // accessToken 的响应式内存镜像；浏览器刷新由 HttpOnly cookie 静默恢复。
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isStudent: (s) => (s.user?.userType || '').toUpperCase() === 'STUDENT'
  },
  actions: {
    /** 账号密码登录。非 STUDENT 一律拒绝并清理 token。tenantCode 多校同账号时必填。 */
    async login(loginName, password, tenantCode, challenge = {}) {
      const data = await portalApi.login(loginName, password, tenantCode, challenge)
      const u = data.user || {}
      const roleCode = data.currentRole?.roleCode || u.roleCode || ''
      const userType = (u.userType || '').toUpperCase()
      if (userType !== 'STUDENT' && roleCode.toUpperCase() !== 'STUDENT') {
        clearSession()
        writeForcePasswordChange(false)
        this.user = null
        this.mustChangePassword = false
        this.token = ''
        const e = new Error('请使用学生账号登录学生门户')
        e.notStudent = true
        throw e
      }
      setToken(data.accessToken || '')
      setRefreshToken(data.refreshToken || '')
      this.token = data.accessToken || ''
      this.mustChangePassword = !!u.mustChangePassword
      writeForcePasswordChange(this.mustChangePassword)
      this.user = {
        userId: u.userId, realName: u.realName, userType,
        roleCode: roleCode || 'STUDENT', studentNo: u.studentNo || data.studentNo || null,
        mustChangePassword: this.mustChangePassword
      }
      this.ready = true
      return this.user
    },
    async logout() {
      try {
        // auth=false prevents a logout attempt from first refreshing/reviving the session.
        await request('/auth/browser-logout', { method: 'POST', auth: false })
      } catch {
        // Local logout still wins. The backend endpoint also expires the cookie before reporting
        // fail-closed store errors, so shared-PC sessions cannot silently resurrect on refresh.
      } finally {
        clearSession()
        writeForcePasswordChange(false)
        this.user = null
        this.mustChangePassword = false
        this.token = ''
        this.ready = false
      }
    }
  }
})