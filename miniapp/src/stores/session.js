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

const STORAGE_KEY = 'gx_session_v1'

export const useSessionStore = defineStore('session', {
  state: () => ({
    logged: false,
    // 当前角色 key（学生 / 各类教师）
    currentRole: ROLE.STUDENT,
    // 当前登录用户（mock）
    mockUser: null,
    // 教师多身份：可切换的身份 key 列表
    availableRoles: []
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
    /** mock 登录：根据选择进入学生端或教师端 */
    login(roleKey) {
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
    /** 教师端切换身份（08B 3.3：切换后需刷新数据） */
    switchRole(roleKey) {
      this.currentRole = roleKey
      this.persist()
    },
    logout() {
      this.logged = false
      this.mockUser = null
      this.availableRoles = []
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
