import { defineStore } from 'pinia'
import { getGraduationDesignMetrics } from '../services/mock'

/**
 * useGdDashboardStore 毕业设计管理驾驶舱数据
 * 契约：loading / error / data / refresh() / reset()
 * data.metrics 由 aggregate 层计算；data.rows 为底层数据关联出的学生进度行
 */
export const useGdDashboardStore = defineStore('gdDashboard', {
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
    overdueRows: (s) => (s.data ? s.data.overdueRows : []),
    excellentRows: (s) => (s.data ? s.data.excellentRows : [])
  },
  actions: {
    async refresh() {
      this.loading = true
      this.error = null
      try {
        this.data = await getGraduationDesignMetrics()
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
