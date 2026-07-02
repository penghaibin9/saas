import { defineStore } from 'pinia'
import { getStudentDashboard } from '../services/mock'

/**
 * useStudentDashboardStore 学生 PC 首页数据
 * 契约：loading / error / data / refresh() / reset()
 * data 为 null 且 !loading && !error 时视为 empty
 */
export const useStudentDashboardStore = defineStore('studentDashboard', {
  state: () => ({
    loading: false,
    error: null,
    data: null
  }),
  getters: {
    /** 映射 AppGlobalState 的 state prop */
    viewState(s) {
      if (s.loading) return 'loading'
      if (s.error) return 'error'
      if (!s.data) return 'empty'
      return 'ready'
    }
  },
  actions: {
    async refresh(studentDbId) {
      this.loading = true
      this.error = null
      try {
        this.data = await getStudentDashboard(studentDbId)
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.loading = false
      this.error = null
      this.data = null
    }
  }
})
