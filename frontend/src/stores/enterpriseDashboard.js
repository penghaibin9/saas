import { defineStore } from 'pinia'
import { getEnterpriseDashboard } from '../services/mock'

/**
 * useEnterpriseDashboardStore 企业导师首页数据
 * 契约：loading / error / data / refresh() / reset()
 * 注意：data.students 仅为授权学生，页面展示敏感字段必须走 AppSensitiveText
 */
export const useEnterpriseDashboardStore = defineStore('enterpriseDashboard', {
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
    }
  },
  actions: {
    async refresh(enterpriseId) {
      this.loading = true
      this.error = null
      try {
        this.data = await getEnterpriseDashboard(enterpriseId)
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
