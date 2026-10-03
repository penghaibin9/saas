import { defineStore } from 'pinia'
import { portalApi } from '../services/portalApi'

const fallback = {
  enabled: true,
  brand: {
    schoolName: '',
    platformName: '跃科岗位实习管理平台',
    primaryColor: '#2f6bff'
  }
}

export const usePortalConfigStore = defineStore('internship-student-config', {
  state: () => ({ config: fallback, loaded: false, error: '' }),
  getters: {
    brand: (state) => state.config?.brand || fallback.brand
  },
  actions: {
    async load() {
      if (this.loaded) return this.config
      try {
        const value = await portalApi.portalConfig()
        this.config = {
          ...fallback,
          ...(value || {}),
          brand: { ...fallback.brand, ...(value?.brand || {}) }
        }
        this.error = ''
      } catch (error) {
        this.config = fallback
        this.error = error?.message || '门户配置读取失败'
      } finally {
        this.loaded = true
      }
      return this.config
    }
  }
})
