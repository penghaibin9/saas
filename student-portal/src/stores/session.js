/**
 * 会话 store（学生 PC 门户）。token 独立 sp_token_v1；仅 STUDENT 可进入。
 * 登出只清理 sp_token_v1，不影响 miniapp / frontend 管理端登录态。
 */
import { defineStore } from 'pinia'
import { portalApi } from '../services/portalApi'
import { clearSession, getToken, setRefreshToken, setToken } from '../services/request'

export const useSessionStore = defineStore('sp-session', {
  state: () => ({
    user: null,          // { userId, realName, userType, roleCode, studentNo }
    ready: false,
    token: getToken()    // 响应式镜像 localStorage 令牌：isLoggedIn 若直接读 getToken() 是无响应式依赖的 getter，
                         // 会缓存应用初始化时的首值（未登录=false），登录后置入令牌也不重算 → 守卫永远判未登录。
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isStudent: (s) => (s.user?.userType || '').toUpperCase() === 'STUDENT'
  },
  actions: {
    /** 账号密码登录。非 STUDENT 一律拒绝并清理 token。 */
    async login(loginName, password) {
      const data = await portalApi.login(loginName, password)
      const u = data.user || {}
      const roleCode = data.currentRole?.roleCode || u.roleCode || ''
      const userType = (u.userType || '').toUpperCase()
      if (userType !== 'STUDENT' && roleCode.toUpperCase() !== 'STUDENT') {
        clearSession()
        this.user = null
        this.token = ''
        const e = new Error('请使用学生账号登录学生门户')
        e.notStudent = true
        throw e
      }
      setToken(data.accessToken || '')
      setRefreshToken(data.refreshToken || '')
      this.token = data.accessToken || ''
      this.user = {
        userId: u.userId, realName: u.realName, userType,
        roleCode: roleCode || 'STUDENT', studentNo: u.studentNo || data.studentNo || null
      }
      this.ready = true
      return this.user
    },
    logout() {
      clearSession()
      this.user = null
      this.token = ''
      this.ready = false
    }
  }
})
