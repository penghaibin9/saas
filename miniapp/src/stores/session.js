/**
 * 会话状态
 * ------------------------------------------------------------
 * 统一维护：当前登录用户、当前角色/身份、数据范围、权限按钮。
 * 教师端支持多身份切换；真实身份快照只保存非敏感标识，不保存令牌。
 */
import { defineStore } from 'pinia'
import { getRoleConfig, hasAction, ROLE } from '@/config/roles.config'
import { mockStudentUser, mockTeacherUser } from '@/mock/user'
import { switchRoleReal } from '@/services/realApi'
import { clearTokens, shouldTryReal } from '@/services/request'
import { clearSensitiveLocalDrafts } from '@/services/sensitiveDraftStorage'

const STORAGE_KEY = 'gx_session_v1'

const emptyIdentity = () => ({
  tenantId: null,
  userId: null,
  activeContextId: null,
  studentId: null,
  studentNo: null,
  realName: null,
  roleCode: null,
  roleName: null
})

export const useSessionStore = defineStore('session', {
  state: () => ({
    logged: false,
    // 真实后端登录返回（token 已由 request 层单独保存）
    realUser: null,
    currentRole: ROLE.STUDENT,
    // 展示对象仍兼容旧页面结构，但真实登录后必须由服务端字段覆盖。
    mockUser: null,
    availableRoles: [],
    availableContexts: [],
    identity: emptyIdentity()
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
    /** 建立会话。账号密码/微信登录已持有真实 token 时只建立 UI 会话，绝不覆盖令牌。 */
    async login(roleKey, { skipRealLogin = false } = {}) {
      if (!skipRealLogin) {
        throw { code: 'LOGIN_REQUIRED', biz: true, message: '请使用学校账号登录' }
      }
      const cfg = getRoleConfig(roleKey)
      this.currentRole = roleKey
      this.logged = true
      if (cfg.side === 'teacher') {
        this.mockUser = { ...mockTeacherUser }
        this.availableRoles = this.mockUser.identities || []
      } else {
        this.mockUser = { ...mockStudentUser }
        this.availableRoles = [ROLE.STUDENT]
      }
      this.persist()
      return cfg.homeRoute
    },
    /** 把真实登录响应的身份字段落到稳定 identity，供页面自校验和本机敏感草稿隔离。 */
    applyRealUser(d) {
      this.realUser = d || null
      if (!d) return
      const role = d.currentRole || {}
      this.availableContexts = d.availableContexts || d.contexts || []
      this.identity = {
        ...this.identity,
        tenantId: d.tenantId != null ? d.tenantId : this.identity.tenantId,
        userId: d.userId != null ? d.userId : this.identity.userId,
        activeContextId: d.activeContextId || role.contextId || this.identity.activeContextId,
        realName: d.displayName || d.realName || this.identity.realName,
        roleCode: role.roleCode || this.identity.roleCode,
        roleName: role.roleName || this.identity.roleName
      }
      // 用真实姓名覆盖 UI 展示对象，杜绝首页/工作台/个人中心显示演示姓名。
      if (this.mockUser) {
        this.mockUser = {
          ...this.mockUser,
          name: d.displayName || d.realName || this.mockUser.name,
          tenantName: d.tenantName || this.mockUser.tenantName || ''
        }
      }
      this.persist()
    },
    /** /mobile/me/profile 回填 studentId/studentNo。 */
    setStudentIdentity(p) {
      if (!p) return
      this.identity = {
        ...this.identity,
        studentId: p.studentId != null ? p.studentId : this.identity.studentId,
        studentNo: p.studentNo || this.identity.studentNo,
        realName: p.name || this.identity.realName
      }
      this.persist()
    },
    /** 学生真实档案回填 UI 展示对象。 */
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
        studentId: base.studentId != null ? base.studentId : this.identity.studentId,
        studentNo: base.studentNo || this.identity.studentNo,
        realName: base.name || this.identity.realName
      }
      this.persist()
    },
    /** 教师端切换身份。新 token 生效后才 resolve，调用方必须 await 后再刷新数据。 */
    async switchRole(roleKey) {
      this.currentRole = roleKey
      this.persist()
      if (shouldTryReal()) {
        const cfg = getRoleConfig(roleKey)
        const ctx = this.availableContexts.find((item) =>
          item.roleCode === roleKey || item.roleCode === cfg.roleCode || item.contextType === roleKey)
        if (!ctx) throw { code: 'NO_CONTEXT', biz: true, message: '当前账号没有该身份' }
        const d = await switchRoleReal(ctx.contextId || ctx.id, 'MP')
        this.applyRealUser(d)
      }
    },
    logout() {
      this.logged = false
      this.mockUser = null
      this.availableRoles = []
      this.availableContexts = []
      this.realUser = null
      this.identity = emptyIdentity()
      // 成绩草稿含学生姓名与分数，共用设备退出时必须清除，禁止被下一账号恢复。
      clearSensitiveLocalDrafts()
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
          identity: {
            tenantId: this.identity.tenantId,
            userId: this.identity.userId,
            activeContextId: this.identity.activeContextId,
            studentId: this.identity.studentId,
            studentNo: this.identity.studentNo,
            realName: this.identity.realName,
            roleCode: this.identity.roleCode,
            roleName: this.identity.roleName
          },
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
          this.identity = { ...emptyIdentity(), ...(s.identity || {}) }
          const skeleton = s.isTeacher ? { ...mockTeacherUser } : { ...mockStudentUser }
          const saved = s.user || {}
          const overlay = {}
          Object.keys(saved).forEach((key) => {
            if (saved[key] !== undefined && saved[key] !== null) overlay[key] = saved[key]
          })
          this.mockUser = { ...skeleton, ...overlay }
        }
      } catch (e) {}
    }
  }
})

export default useSessionStore
