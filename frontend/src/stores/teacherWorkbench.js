/**
 * 已废弃：旧 mock 教师工作台 store。
 * 生产入口为 `/` → AdminWorkbenchView → modules/workbench/WorkbenchView（真实待办）。
 * 保留空导出仅为避免历史动态 import 崩；勿再接入页面。
 */
import { defineStore } from 'pinia'

export const useTeacherWorkbenchStore = defineStore('teacherWorkbench', {
  state: () => ({
    loading: false,
    error: '已废弃：请使用管理端工作台 /',
    data: null
  }),
  getters: {
    viewState: () => 'error',
    todos: () => [],
    riskStudents: () => []
  },
  actions: {
    async refresh() {
      this.error = '已废弃：请使用管理端工作台 /'
      this.data = null
    },
    reset() {
      this.loading = false
      this.error = null
      this.data = null
    }
  }
})
