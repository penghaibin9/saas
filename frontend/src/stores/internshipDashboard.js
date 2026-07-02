import { defineStore } from 'pinia'
import { getInternshipMetrics } from '../services/mock'

/**
 * useInternshipDashboardStore 岗位实习管理驾驶舱数据
 * 契约：loading / error / data / refresh() / reset()
 * data.metrics 由 aggregate 层计算；data.rows / riskRows 为底层数据关联出的明细行
 */
export const useInternshipDashboardStore = defineStore('internshipDashboard', {
  state: () => ({
    loading: false,
    error: null,
    data: null
  }),
  getters: {
    viewState(s) {
      if (s.loading) return 'loading'
      if (s.error) return 'error'
      if (!s.data) return 'empty'
      return 'ready'
    },
    metrics: (s) => (s.data ? s.data.metrics : []),
    rows: (s) => (s.data ? s.data.rows : []),
    riskRows: (s) => (s.data ? s.data.riskRows : []),
    enterpriseTodos: (s) => (s.data ? s.data.enterpriseTodos : [])
  },
  actions: {
    async refresh() {
      this.loading = true
      this.error = null
      try {
        this.data = await getInternshipMetrics()
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
