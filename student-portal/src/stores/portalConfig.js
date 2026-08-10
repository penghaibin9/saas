/**
 * 门户配置 store：消费后端 /mobile/me/portal-config 合并结果。
 * 负责总开关 enabled、模块开关 modules、功能开关 features、品牌 brand。
 * 切换账号/租户后必须 reset()，避免缓存错租户配置。
 */
import { defineStore } from 'pinia'
import { portalApi } from '../services/portalApi'
import { useSessionStore } from './session'

const SAFE_DEFAULT = {
  enabled: false, portalName: '学生服务门户', portalUrl: '/portal/',
  brand: { schoolName: '', platformName: '学生服务门户', logo: '', primaryColor: '#1677ff', watermark: '' },
  modules: {}, features: {}, package: { code: '', name: '' }, loginAccountTips: { enabled: false, accounts: [] }
}

export const usePortalConfigStore = defineStore('sp-portal-config', {
  state: () => ({
    config: null,
    loaded: false,
    error: ''
  }),
  getters: {
    enabled: (s) => !!s.config?.enabled,
    brand: (s) => s.config?.brand || SAFE_DEFAULT.brand,
    portalName: (s) => s.config?.portalName || SAFE_DEFAULT.portalName,
    modules: (s) => s.config?.modules || {},
    features: (s) => s.config?.features || {}
  },
  actions: {
    async load() {
      // 登录响应已明确要求首次改密时，不能先去调用 portal-config 等业务接口。
      // 状态单独持久化，刷新浏览器后也先进入改密恢复链；服务端 PASSWORD_CHANGE_REQUIRED 仍是最终真值。
      const session = useSessionStore()
      if (session.mustChangePassword || session.user?.mustChangePassword) {
        this.config = { ...SAFE_DEFAULT }
        this.error = ''
        this.loaded = true
        return this.config
      }
      try {
        this.config = await portalApi.portalConfig()
        this.error = ''
      } catch (e) {
        // 读取失败按未开通安全态处理，不白屏
        this.config = { ...SAFE_DEFAULT }
        this.error = e?.message || '门户配置读取失败'
      } finally {
        this.loaded = true
      }
      return this.config
    },
    isModuleEnabled(key) {
      return !!this.config?.enabled && !!this.config?.modules?.[key]
    },
    isFeatureEnabled(key) {
      return !!this.config?.enabled && !!this.config?.features?.[key]
    },
    reset() {
      this.config = null
      this.loaded = false
      this.error = ''
    }
  }
})