/**
 * 会话状态。
 * 统一维护当前登录用户、当前角色/身份与真实身份快照；具体业务权限由服务端上下文下发。
 */
import { defineStore } from 'pinia'
import { getRoleConfig, hasAction, roleKeyFromBackendRole, ROLE } from '@/config/roles.config'
import { switchRoleReal } from '@/services/realApi'
import { realRequest, getToken, getRefreshToken, clearTokens, registerForceLogoutHandler, shouldTryReal } from '@/services/request'
import { ENV } from '@/config/env'
import { setForcePasswordChange } from '@/security/passwordChangeGate'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { clearSensitiveLocalDrafts } from '@/services/sensitiveDraftStorage'

const STORAGE_KEY = 'gx_session_v1'
const STUDENT_INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'
const TEACHER_GRADUATION_BATCH_KEY = 'gx_gd_teacher_batch_v1'
// H5 浏览器的 HttpOnly 会话恢复只拥有这个非机密哨兵，尚未由服务端确认当前用户。
// 此时绝不能将上次写入的姓名、学号、班级等投影盖回页面。
const H5_BROWSER_REFRESH_SENTINEL = '__HTTPONLY_BROWSER_REFRESH__'

function freshIdentity() {
  return {
    userId: null, studentId: null, studentNo: null, realName: null,
    roleCode: null, roleName: null
  }
}

function neutralUser(side) {
  return side === 'teacher'
    ? { name: '', tenantName: '', identities: [] }
    : { name: '', studentNo: '', className: '', college: '', major: '', grade: '', tenantName: '' }
}

// 登录成功前、账号切换中以及个人资料读取失败时只允许渲染空骨架。
// 绝不能用演示姓名、学号或班级填充真实会话页面，否则会把错误/离线状态伪装成另一名学生的数据。
function initialUser(side) { return neutralUser(side) }

export const useSessionStore = defineStore('session', {
  state: () => ({
    logged: false,
    realUser: null,
    currentRole: ROLE.STUDENT,
    mockUser: null,
    availableRoles: [],
    availableContexts: [],
    mustChangePassword: false,
    identity: freshIdentity(),
    // 仅代表本次冷启动是否拥有可核验的原生 token/refresh。它不持久化，
    // H5 HttpOnly cookie 哨兵必须等 /auth/me 成功后才能恢复身份投影。
    persistedIdentityVerified: false
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
      // 不在本地留下上一账号可见的敏感草稿、消息摘要或已选择的业务上下文。
      // 教务未确定写操作使用带真实身份摘要的独立恢复账本，不能在此粗暴删除，
      // 由其 owner/context 校验决定是否可读、是否可继续。
      clearSensitiveLocalDrafts()
      try { uni.removeStorageSync(STUDENT_INTERNSHIP_BATCH_KEY) } catch (e) {}
      try { uni.removeStorageSync(TEACHER_GRADUATION_BATCH_KEY) } catch (e) {}
    },
    resetAuthenticatedProjection() {
      this.realUser = null
      this.mockUser = null
      this.availableRoles = []
      this.availableContexts = []
      this.mustChangePassword = false
      setForcePasswordChange(false)
      this.identity = freshIdentity()
      this.persistedIdentityVerified = false
    },
    async login(roleKey, { skipRealLogin = false } = {}) {
      if (!skipRealLogin) {
        throw { code: 'LOGIN_REQUIRED', biz: true, message: '请使用学校账号登录' }
      }
      this.clearBusinessContexts()
      // 先清投影，后写入新身份。任何在途旧请求都会由 request/session generation 拦下；
      // 即使新的 profile 请求失败，页面也只能看到空态，绝不能露出上一个账号资料。
      this.resetAuthenticatedProjection()
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
      // /auth/me omits the school name. Retain the verified login name only
      // within the same tenant; never carry it into a different school's session.
      const tenantName = d?.tenantName || (d?.tenantId != null &&
        String(d.tenantId) === String(this.realUser?.tenantId) && this.persistedIdentityVerified
        ? this.mockUser?.tenantName || '' : '')
      this.realUser = d || null
      if (!d) return
      const role = d.currentRole || {}
      this.availableContexts = d.availableContexts || d.contexts || []
      this.availableRoles = [...new Set(this.availableContexts
        .map((item) => roleKeyFromBackendRole(item.roleCode || item.contextType))
        .filter(Boolean))]
      const currentRoleKey = roleKeyFromBackendRole(role.roleCode || role.contextType)
      if (currentRoleKey) this.currentRole = currentRoleKey
      this.mustChangePassword = !!(d.user && d.user.mustChangePassword)
      setForcePasswordChange(this.mustChangePassword)
      this.identity = {
        ...freshIdentity(),
        userId: d.userId != null ? d.userId : (d.user?.userId ?? d.user?.id ?? null),
        studentId: d.studentId != null ? d.studentId : (d.student?.studentId ?? d.student?.id ?? null),
        studentNo: d.studentNo || d.student?.studentNo || null,
        realName: d.displayName || d.realName || d.user?.realName || d.user?.name || null,
        roleCode: role.roleCode || role.contextType || null,
        roleName: role.roleName || null
      }
      this.persistedIdentityVerified = true
      const side = getRoleConfig(this.currentRole).side
      this.mockUser = {
        ...initialUser(side),
        name: d.displayName || d.realName || d.user?.realName || d.user?.name || '',
        tenantName
      }
      this.persist()
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
      try {
        if (shouldTryReal()) {
          const ctx = this.availableContexts.find((item) =>
            roleKeyFromBackendRole(item.roleCode || item.contextType) === roleKey)
          if (!ctx) throw { code: 'NO_CONTEXT', biz: true, message: '当前账号没有该身份' }
          const clientType = getRoleConfig(roleKey).side === 'teacher' ? 'TEACHER_MINI' : 'STUDENT_MINI'
          // 等服务端确认新会话后才清除旧业务投影；失败时原身份及其正在办理的草稿仍可继续。
          // 成功路径由新 token 的 session generation 阻止一切旧请求写回。
          const d = await switchRoleReal(ctx.contextId || ctx.id, clientType)
          this.clearBusinessContexts()
          this.currentRole = roleKey
          this.applyRealUser(d)
        } else if (ENV.allowMockFallback) {
          this.clearBusinessContexts()
          this.currentRole = roleKey
        } else {
          throw { code: 'NETWORK', message: '网络不可用，无法安全切换身份' }
        }
        this.persist()
      } catch (e) {
        this.currentRole = previousRole
        this.identity = previousIdentity
        this.persist()
        throw e
      }
    },
    async logoutCurrentSession() {
      // H5 由浏览器适配器撤销 HttpOnly 会话；原生端必须等待当前会话撤销结果。
      // #ifndef H5
      if (getToken() || getRefreshToken()) {
        const result = await realRequest('/auth/logout?scope=current', { method: 'POST', data: { refreshToken: getRefreshToken() || undefined } })
        if (!result?.tokenInvalidated) throw { message: '服务端会话未完全撤销，请重试退出' }
      }
      // #endif
      this.logout()
    },
    logout() {
      this.clearBusinessContexts()
      this.logged = false
      this.mockUser = null
      this.availableRoles = []
      this.availableContexts = []
      this.realUser = null
      this.mustChangePassword = false
      setForcePasswordChange(false)
      this.identity = freshIdentity()
      this.persistedIdentityVerified = false
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
          mustChangePassword: this.mustChangePassword,
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
        this.persistedIdentityVerified = false
        // 没有可用于刷新/验证的会话凭据时，不恢复任何上一账号展示投影。
        // 这避免了被系统清 token 后仍在冷启动首页短暂显示旧姓名、班级或学生号。
        const token = getToken()
        const refresh = getRefreshToken()
        if (!token && !refresh) {
          this.resetAuthenticatedProjection()
          try { uni.removeStorageSync(STORAGE_KEY) } catch (e) {}
          return
        }
        const raw = uni.getStorageSync(STORAGE_KEY)
        if (!raw) return
        const s = JSON.parse(raw)
        if (s && s.logged) {
          this.resetAuthenticatedProjection()
          this.currentRole = s.currentRole
          this.availableRoles = s.availableRoles || []
          this.mustChangePassword = !!s.mustChangePassword
          setForcePasswordChange(this.mustChangePassword)
          this.logged = true
          const skeleton = initialUser(s.isTeacher ? 'teacher' : 'student')
          // F5 后 H5 只有 HttpOnly cookie 的恢复哨兵，旧的 gx_session_v1 不能证明
          // cookie 仍属于同一账号。只保留不含个人资料的角色骨架，等 browser-refresh
          // 与 /auth/me 成功后由 applyRealUser 写入当前真实身份。
          const h5UnverifiedBrowserSession = !token && refresh === H5_BROWSER_REFRESH_SENTINEL
          this.persistedIdentityVerified = !h5UnverifiedBrowserSession
          if (h5UnverifiedBrowserSession) {
            this.mockUser = skeleton
          } else {
            const saved = s.user || {}
            const overlay = {}
            Object.keys(saved).forEach((k) => { if (saved[k] !== undefined && saved[k] !== null) overlay[k] = saved[k] })
            this.mockUser = { ...skeleton, ...overlay }
          }
        }
      } catch (e) {}
    }
  }
})

// 401 刷新失败时 request.js 需要做完整登出（清业务上下文 + gx_session_v1 + token），
// 但 request.js 不能反向 import 本文件（本文件已 import request.js，会形成模块循环）。
// 改为在此注册回调，调用时机在运行时（登录后才会触发 401），届时 pinia 必已激活。
registerForceLogoutHandler(() => useSessionStore().logout())

export default useSessionStore
