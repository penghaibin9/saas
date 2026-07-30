/**
 * 会话状态。
 * 统一维护当前登录用户、当前角色/身份与真实身份快照；具体业务权限由服务端上下文下发。
 */
import { defineStore } from 'pinia'
import { getRoleConfig, hasAction, ROLE } from '@/config/roles.config'
import { mockStudentUser, mockTeacherUser } from '@/mock/user'
import { switchRoleReal } from '@/services/realApi'
import { clearTokens, shouldTryReal } from '@/services/request'
import { useInternshipContextStore } from '@/stores/internshipContext'

const STORAGE_KEY = 'gx_session_v1'
const STUDENT_INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'

function neutralUser(side) {
  return side === 'teacher'
    ? { name: '', tenantName: '', identities: [] }
    : { name: '', studentNo: '', className: '', college: '', major: '', grade: '', tenantName: '' }
}

function initialUser(side) {
  if (import.meta.env && import.meta.env.PROD) return neutralUser(side)
  return side === 'teacher' ? { ...mockTeacherUser } : { ...mockStudentUser }
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    logged: false,
    realUser: null,
    currentRole: ROLE.STUDENT,
    mockUser: null,
    availableRoles: [],
    availableContexts: [],
    identity: {
      userId: null, studentId: null, studentNo: null, realName: null,
      roleCode: null, roleName: null
    }
  }),
  getters: {
    roleConfig: (s) => getRoleConfig(s.currentRole),
    side: (s) => getRoleConfig(s.currentRole).side,
    isTeacher: (s) => getRoleConfig(s.currentRole).side === 'teacher',
    dataScope: (s) => getRoleConfig(s.currentRole).dataScope,
    dataScopeText: (s) => getRoleConfig(s.currentRole).dataScopeText || '',
    permissionActions: (s) => getRoleConfig(s.currentRole).permissionActions || []
  },
  actions: {
    can(action) {
      return hasAction(this.currentRole, action)
    },
    clearBusinessContexts() {
      useInternshipContextStore().clear()
      try { uni.removeStorageSync(STUDENT_INTERNSHIP_BATCH_KEY) } catch (e) {}
    },
    async login(roleKey, { skipRealLogin = false } = {}) {
      if (!skipRealLogin) {
        throw { code: 'LOGIN_REQUIRED', biz: true, message: '请使用学校账号登录' }
      }
      this.clearBusinessContexts()
      const cfg = getRoleConfig(roleKey)
      this.currentRole = roleKey
      this.logged = true
      if (cfg.side === 'teacher') {
        this.mockUser = initialUser('teacher')
        this.availableRoles = this.mockUser.identities || []
      } else {
        this.mockUser = initialUser('student')
        this.availableRoles = [ROLE.STUDENT]
      }
      this.persist()
      return cfg.homeRoute
    },
    applyRealUser(d) {
      this.realUser = d || null
      if (!d) return
      const role = d.currentRole || {}
      this.availableContexts = d.availableContexts || d.contexts || []
      this.identity = {
        ...this.identity,
        userId: d.userId != null ? d.userId : this.identity.userId,
        realName: d.displayName || d.realName || this.identity.realName,
        roleCode: role.roleCode || this.identity.roleCode,
        roleName: role.roleName || this.identity.roleName
      }
      if (this.mockUser) {
        this.mockUser = {
          ...this.mockUser,
          name: d.displayName || d.realName || this.mockUser.name,
          tenantName: d.tenantName || this.mockUser.tenantName || ''
        }
        this.persist()
      }
    },
    setStudentIdentity(p) {
      if (!p) return
      this.identity = {
        ...this.identity,
        studentId: p.studentId != null ? p.studentId : this.identity.studentId,
        studentNo: p.studentNo || this.identity.studentNo,
        realName: p.name || this.identity.realName
      }
    },
    hydrateStudentProfile(p) {
      if (!p) return
      const base = p.base || {}
      const org = p.org || {}
      this.mockUser = {
        ...(this.mockUser || {}),
        name: base.name || (this.mockUser && this.mockUser.name) || '',
        studentNo: base.studentNo || '',
        className: org.className || '',
        college: org.college || '',
        major: org.major || '',
        grade: org.grade || ''
      }
      this.identity = {
        ...this.identity,
        studentNo: base.studentNo || this.identity.studentNo,
        realName: base.name || this.identity.realName
      }
      this.persist()
    },
    async switchRole(roleKey) {
      const previousRole = this.currentRole
      const previousIdentity = { ...this.identity }
      this.clearBusinessContexts()
      try {
        if (shouldTryReal()) {
          const cfg = getRoleConfig(roleKey)
          const ctx = this.availableContexts.find((item) =>
            item.roleCode === roleKey || item.roleCode === cfg.roleCode || item.contextType === roleKey)
          if (!ctx) throw { code: 'NO_CONTEXT', biz: true, message: '当前账号没有该身份' }
          const d = await switchRoleReal(ctx.contextId || ctx.id, 'MP')
          this.currentRole = roleKey
          this.applyRealUser(d)
        } else {
          this.currentRole = roleKey
        }
        this.persist()
      } catch (e) {
        this.currentRole = previousRole
        this.identity = previousIdentity
        this.persist()
        throw e
      }
    },
    logout() {
      this.clearBusinessContexts()
      this.logged = false
      this.mockUser = null
      this.availableRoles = []
      this.availableContexts = []
      this.realUser = null
      this.identity = { userId: null, studentId: null, studentNo: null, realName: null,
        roleCode: null, roleName: null }
      clearTokens()
      try { uni.removeStorageSync(STORAGE_KEY) } catch (e) {}
    },
    persist() {
      try {
        const u = this.mockUser || {}
        uni.setStorageSync(STORAGE_KEY, JSON.stringify({
          logged: this.logged,
          currentRole: this.currentRole,
          availableRoles: this.availableRoles,
          isTeacher: getRoleConfig(this.currentRole).side === 'teacher',
          user: {
            name: u.name, studentNo: u.studentNo, className: u.className,
            college: u.college, major: u.major, grade: u.grade, tenantName: u.tenantName
          }
        }))
      } catch (e) {}
    },
    restore() {
      try {
        const raw = uni.getStorageSync(STORAGE_KEY)
        if (!raw) return
        const s = JSON.parse(raw)
        if (s && s.logged) {
          this.currentRole = s.currentRole
          this.availableRoles = s.availableRoles || []
          this.logged = true
          const skeleton = initialUser(s.isTeacher ? 'teacher' : 'student')
          const saved = s.user || {}
          const overlay = {}
          Object.keys(saved).forEach((k) => { if (saved[k] !== undefined && saved[k] !== null) overlay[k] = saved[k] })
          this.mockUser = { ...skeleton, ...overlay }
        }
      } catch (e) {}
    }
  }
})

export default useSessionStore
