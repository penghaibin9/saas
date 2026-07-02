import { defineStore } from 'pinia'
import { getPracticeTeachingOverview } from '../services/mock'

/**
 * @deprecated 请使用 @/modules/dashboard 的 useDashboardStore（首页）
 * usePracticeOverviewStore 实践教学总览（旧版独立 store）
 */
export const usePracticeOverviewStore = defineStore('practice-overview', {
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
    overviewMetrics: (s) => (s.data ? s.data.overview : []),
    gdMetrics: (s) => (s.data ? s.data.graduationDesign : []),
    internshipMetrics: (s) => (s.data ? s.data.internship : []),
    employmentMetrics: (s) => (s.data ? s.data.employment : []),
    riskStudents: (s) => (s.data ? s.data.riskStudents : [])
  },
  actions: {
    async refresh() {
      this.loading = true
      this.error = null
      try {
        this.data = await getPracticeTeachingOverview()
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
