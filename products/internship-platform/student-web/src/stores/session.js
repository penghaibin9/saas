import { defineStore } from 'pinia'
import { portalApi } from '../services/portalApi'
import { clearSession, getToken, request, setRefreshToken, setToken } from '../services/request'

function normalizeUser(data = {}) {
  const raw = data.user || data
  const currentRole = data.currentRole || raw.currentRole || {}
  return {
    userId: raw.userId || raw.id || data.userId || null,
    realName: raw.realName || raw.name || '',
    userType: String(raw.userType || '').toUpperCase(),
    roleCode: currentRole.roleCode || raw.roleCode || '',
    studentNo: raw.studentNo || data.studentNo || null,
    tenantId: data.tenantId ?? raw.tenantId ?? null
  }
}

function assertStudent(user) {
  if (user.userType !== 'STUDENT' && String(user.roleCode || '').toUpperCase() !== 'STUDENT') {
    const error = new Error('请使用学生账号登录岗位实习学生端')
    error.notStudent = true
    throw error
  }
  return user
}

export const useSessionStore = defineStore('internship-student-session', {
  state: () => ({
    user: null,
    token: getToken(),
    ready: false
  }),
  getters: {
    isLoggedIn: (state) => !!state.token && !!state.user
  },
  actions: {
    async login(loginName, password, tenantCode = '') {
      const data = await portalApi.login(loginName, password, tenantCode)
      const user = assertStudent(normalizeUser(data))
      setToken(data.accessToken || '')
      setRefreshToken(data.refreshToken || '')
      this.token = data.accessToken || ''
      this.user = user
      this.ready = true
      return user
    },
    async restore() {
      if (this.ready) return this.user
      try {
        const data = await portalApi.me()
        const user = assertStudent(normalizeUser(data))
        this.token = getToken()
        this.user = user
        return user
      } catch {
        clearSession()
        this.token = ''
        this.user = null
        return null
      } finally {
        this.ready = true
      }
    },
    async logout() {
      try { await request('/auth/browser-logout', { method: 'POST', auth: true }) } catch {}
      clearSession()
      this.user = null
      this.token = ''
      this.ready = true
    }
  }
})
