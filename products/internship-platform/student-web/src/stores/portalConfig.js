import { defineStore } from 'pinia'
import { portalApi } from '../services/portalApi'
import { currentSessionGeneration } from '../services/request'
import { useSessionStore } from './session'

const fallback = {
  enabled: true,
  brand: {
    schoolName: '',
    platformName: '跃科岗位实习管理平台',
    primaryColor: '#2f6bff'
  }
}

function configScope() {
  const user=useSessionStore().user
  return user?.tenantId && user?.userId ? JSON.stringify([String(user.tenantId),String(user.userId),user.roleCode || '']) : ''
}
export const usePortalConfigStore = defineStore('internship-student-config', {
  state: () => ({ config: fallback, loaded: false, error: '', scope: '', sequence: 0 }),
  getters: {
    visibleConfig: (state) => state.scope===configScope() ? state.config : fallback,
    brand() { return this.visibleConfig?.brand || fallback.brand }
  },
  actions: {
    async load() {
      const scope=configScope(),generation=currentSessionGeneration()
      if (scope && this.loaded && this.scope===scope) return this.config
      const sequence=++this.sequence
      this.scope=scope;this.config=fallback;this.loaded=false;this.error=''
      if(!scope)return this.config
      const current=()=>this.sequence===sequence && scope===configScope() && generation===currentSessionGeneration()
      try {
        const value = await portalApi.portalConfig()
        if(!current())return this.visibleConfig
        this.config = {
          ...fallback,
          ...(value || {}),
          brand: { ...fallback.brand, ...(value?.brand || {}) }
        }
        this.error = ''
      } catch (error) {
        if(!current())return this.visibleConfig
        this.config = fallback
        this.error = error?.message || '门户配置读取失败'
      } finally {
        if(current())this.loaded = true
      }
      return this.config
    }
  }
})
