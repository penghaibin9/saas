import { defineStore } from 'pinia'
import { internshipApi } from '@/modules/internship/api/internship.api'

export const useInternshipDashboardStore = defineStore('internshipDashboard', {
  state: () => ({ loading: false, error: null, data: null }),
  getters: {
    viewState: (s) => s.loading ? 'loading' : s.error ? 'error' : s.data ? 'ready' : 'empty',
    metrics: (s) => s.data?.metrics || [],
    rows: (s) => s.data?.rows || [],
    riskRows: (s) => s.data?.riskRows || [],
    enterpriseTodos: (s) => s.data?.enterpriseTodos || []
  },
  actions: {
    async refresh(params = {}) {
      this.loading = true
      this.error = null
      try {
        const res = await internshipApi.getDashboardSummary(params)
        if (res?.code !== 0) throw new Error(res?.message || '岗位实习看板加载失败')
        this.data = res?.data || {}
      } catch (error) {
        this.error = error?.message || '岗位实习看板加载失败'
        throw error
      } finally {
        this.loading = false
      }
    },
    reset() { this.loading = false; this.error = null; this.data = null }
  }
})
