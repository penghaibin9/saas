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
import { loginReal } from '@/services/realApi'
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
    /** 演示登录：根据选择进入学生端或教师端。
     * 返回 Promise：真实 token 就绪（或确认拿不到）后才 resolve，
     * 避免"页面先加载、token 后到"导致首屏 401/回退。 */
    async login(roleKey) {
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
      /* 真实后端登录取 token（失败静默，页面走网络兜底骨架） */
      if (shouldTryReal()) {
        clearTokens() // 先清旧 token，防止旧角色残留
        try {
          const d = await loginReal(roleKey, cfg.side)
          this.applyRealUser(d)
        } catch (e) { /* 后端不可达：页面按网络失败兜底 */ }
      }
      return cfg.homeRoute
    },
    /** P9.2：把真实登录响应的身份字段落到 identity，供页面自校验 */
    applyRealUser(d) {
      this.realUser = d || null
      if (!d) return
      const role = d.currentRole || {}
      this.identity = {
        ...this.identity,
        userId: d.userId != null ? d.userId : this.identity.userId,
        realName: d.displayName || d.realName || this.identity.realName,
        roleCode: role.roleCode || this.identity.roleCode,
        roleName: role.roleName || this.identity.roleName
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
    /** 教师端切换身份（08B 3.3）。返回 Promise：新 token 生效后才 resolve，
     * 调用方必须 await 后再刷新数据，避免旧角色 token 残留导致数据范围错乱。 */
    async switchRole(roleKey) {
      this.currentRole = roleKey
      this.persist()
      /* 切换身份 = 重新用对应演示账号登录后端（数据范围随之变化） */
      if (shouldTryReal()) {
        clearTokens() // 旧角色 token 立即作废，绝不带着旧范围发请求
        try {
          const d = await loginReal(roleKey, getRoleConfig(roleKey).side)
          this.applyRealUser(d)
        } catch (e) { /* 后端不可达：页面按网络失败兜底 */ }
      }
    },
    logout() {
      this.logged = false
      this.mockUser = null
      this.availableRoles = []
      this.realUser = null
      this.identity = { userId: null, studentId: null, studentNo: null, realName: null,
        roleCode: null, roleName: null }
      clearTokens()
      try { uni.removeStorageSync(STORAGE_KEY) } catch (e) {}
    },
    persist() {
      try {
        uni.setStorageSync(STORAGE_KEY, JSON.stringify({
          logged: this.logged,
          currentRole: this.currentRole,
          availableRoles: this.availableRoles,
          isTeacher: getRoleConfig(this.currentRole).side === 'teacher'
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
          this.mockUser = s.isTeacher ? { ...mockTeacherUser } : { ...mockStudentUser }
        }
      } catch (e) {}
    }
  }
})

export default useSessionStore
