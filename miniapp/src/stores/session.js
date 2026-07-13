/**
 * 会话状态（mock）
 * ------------------------------------------------------------
 * 统一维护：当前登录用户、当前角色/身份、数据范围、权限按钮。
 * 页面通过本 store 读取 currentRole / dataScope / permissionActions，
 * 教师端支持多身份切换（08B 身份上下文）。
 */
import { defineStore } from 'pinia'
import { getRoleConfig, hasAction, ROLE } from '@/config/roles.config'
import { mockStudentUser, mockTeacherUser } from '@/mock/user'
import { switchRoleReal } from '@/services/realApi'
import { clearTokens, shouldTryReal } from '@/services/request'

const STORAGE_KEY = 'gx_session_v1'

export const useSessionStore = defineStore('session', {
  state: () => ({
    logged: false,
    // P3：真实后端登录返回（token 已存 storage；null=未连通，走 mock）
    realUser: null,
    // 当前角色 key（学生 / 各类教师）
    currentRole: ROLE.STUDENT,
    // 当前登录用户（mock）
    mockUser: null,
    // 教师多身份：可切换的身份 key 列表
    availableRoles: [],
    availableContexts: [],
    // 真实身份字段（登录响应 + /mobile/me/profile 回填），供页面自校验
    identity: {
      userId: null, studentId: null, studentNo: null, realName: null,
      roleCode: null, roleName: null
    }
  }),
  getters: {
    roleConfig: (s) => getRoleConfig(s.currentRole),
    side: (s) => getRoleConfig(s.currentRole).side, // 'student' | 'teacher'
    isTeacher: (s) => getRoleConfig(s.currentRole).side === 'teacher',
    dataScope: (s) => getRoleConfig(s.currentRole).dataScope,
    dataScopeText: (s) => getRoleConfig(s.currentRole).dataScopeText || '',
    permissionActions: (s) => getRoleConfig(s.currentRole).permissionActions || []
  },
  actions: {
    can(action) {
      return hasAction(this.currentRole, action)
    },
    /** 建立会话：根据角色进入学生端或教师端。
     * skipRealLogin=true（账号密码登录已持有真实 token）时只建 UI 会话，绝不覆盖令牌；
     * 否则用演示账号走真实 /api/v1/auth/login（P12：不再依赖 mock-login）。 */
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
    /** P9.2：把真实登录响应的身份字段落到 identity，供页面自校验 */
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
      // 用真实姓名覆盖 UI 展示对象，杜绝首页/工作台/个人中心显示 mock 姓名（学号/班级由 profile 回填）
      if (this.mockUser) {
        this.mockUser = {
          ...this.mockUser,
          name: d.displayName || d.realName || this.mockUser.name,
          tenantName: d.tenantName || this.mockUser.tenantName || ''
        }
        this.persist()
      }
    },
    /** /mobile/me/profile 回填 studentId/studentNo（登录响应里没有） */
    setStudentIdentity(p) {
      if (!p) return
      this.identity = {
        ...this.identity,
        studentId: p.studentId != null ? p.studentId : this.identity.studentId,
        studentNo: p.studentNo || this.identity.studentNo,
        realName: p.name || this.identity.realName
      }
    },
    /** 学生真实档案回填 UI 展示对象（姓名/学号/班级/学院/专业/年级），彻底替换 mock 假值。
     *  入参为 /mobile/me/profile 返回结构：{ base:{name,studentNo,...}, org:{className,college,major,grade} } */
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
    /** 教师端切换身份（08B 3.3）。返回 Promise：新 token 生效后才 resolve，
     * 调用方必须 await 后再刷新数据，避免旧角色 token 残留导致数据范围错乱。 */
    async switchRole(roleKey) {
      this.currentRole = roleKey
      this.persist()
      /* 正式环境按服务端签发的身份上下文切换；开发演示才允许演示账号重登。 */
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
          // 真实登录/档案回填后的展示快照，供 restart 后恢复真实身份，避免回落到 mock 姓名/学号
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
          const skeleton = s.isTeacher ? { ...mockTeacherUser } : { ...mockStudentUser }
          // 用持久化的真实展示快照覆盖 mock 骨架（仅覆盖已回填字段），避免 restart 后显示 mock 身份
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
